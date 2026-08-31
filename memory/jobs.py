"""Long-running ingests, tracked so a web page can watch them.

Analyzing a game is ~10 seconds of Stockfish, so a 40-game sync is minutes — far too long
to hold a request open. The work runs on a daemon thread and reports progress through a
row in the same SQLite database, which means progress survives a page reload and needs no
queue, broker, or extra process. For one person syncing their own games that is the whole
requirement; anything more would be infrastructure with no one to serve.

The honest limitation: a job is only alive while the process is. If the server dies
mid-sync its row stays ``running`` forever, so :func:`read_job` reports a job that has
stopped reporting progress as ``stalled`` rather than pretending it is still working.
Nothing is lost either way — ingest is idempotent, so a re-run picks up where it stopped.
"""

from __future__ import annotations

import re
import sqlite3
import threading
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from memory.store import already_stored, connect, ingest_game

# chess.com handles: letters, digits, underscore and hyphen. Validated because the name is
# interpolated into an API URL, and because a typo should fail here with a clear message
# rather than as a confusing 404 from someone else's server.
USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{3,25}$")

# A running job that hasn't reported progress for this long is presumed dead.
STALE_AFTER = timedelta(minutes=10)

JOBS_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id          INTEGER PRIMARY KEY,
    user_name   TEXT NOT NULL,
    status      TEXT NOT NULL CHECK (status IN ('running', 'done', 'failed')),
    total       INTEGER NOT NULL DEFAULT 0,
    done        INTEGER NOT NULL DEFAULT 0,
    added       INTEGER NOT NULL DEFAULT 0,
    message     TEXT NOT NULL DEFAULT '',
    started_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs(user_name, id DESC);
"""


@dataclass(frozen=True)
class Job:
    id: int
    user_name: str
    status: str
    total: int
    done: int
    added: int
    message: str
    started_at: str
    updated_at: str

    @property
    def is_active(self) -> bool:
        """Still working, as far as anyone can tell."""
        return self.status == "running"

    @property
    def percent(self) -> int:
        if self.status == "done":
            return 100
        return round(100 * self.done / self.total) if self.total else 0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create the jobs table if it isn't there yet."""
    conn.executescript(JOBS_SCHEMA)


def create_job(conn: sqlite3.Connection, user: str) -> int:
    ensure_schema(conn)
    with conn:
        cursor = conn.execute(
            """
            INSERT INTO jobs (user_name, status, message, started_at, updated_at)
            VALUES (?, 'running', 'Fetching games…', ?, ?)
            """,
            (user, _now(), _now()),
        )
    return cursor.lastrowid


def update_job(conn: sqlite3.Connection, job_id: int, **fields) -> None:
    """Patch a job row. Always touches ``updated_at`` — that is the liveness signal."""
    fields["updated_at"] = _now()
    assignments = ", ".join(f"{key} = ?" for key in fields)
    with conn:
        conn.execute(
            f"UPDATE jobs SET {assignments} WHERE id = ?", [*fields.values(), job_id]
        )


def _row_to_job(row: sqlite3.Row) -> Job:
    job = Job(**dict(row))
    if not job.is_active:
        return job
    try:
        updated = datetime.fromisoformat(job.updated_at)
    except ValueError:  # pragma: no cover - defensive
        return job
    if datetime.now(timezone.utc) - updated <= STALE_AFTER:
        return job
    # Reported as failed rather than silently spinning: the row cannot tell us whether the
    # worker died, but it can tell us it stopped saying anything.
    return Job(
        **{
            **dict(row),
            "status": "failed",
            "message": "Stopped reporting progress — the server may have restarted. "
            "Syncing again is safe; finished games are not re-analyzed.",
        }
    )


def read_job(conn: sqlite3.Connection, job_id: int) -> Job | None:
    ensure_schema(conn)
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _row_to_job(row) if row else None


def latest_job(conn: sqlite3.Connection, user: str) -> Job | None:
    """The most recent job for a player, whatever its state."""
    ensure_schema(conn)
    row = conn.execute(
        "SELECT * FROM jobs WHERE user_name = ? ORDER BY id DESC LIMIT 1", (user,)
    ).fetchone()
    return _row_to_job(row) if row else None


def active_job(conn: sqlite3.Connection, user: str) -> Job | None:
    """The player's currently-running job, if any — used to refuse a second one."""
    job = latest_job(conn, user)
    return job if job and job.is_active else None


def _default_fetch(user: str, max_games: int) -> str:
    """Fetch a chess.com user's recent games as PGN text."""
    import tempfile

    from engine.fetch_data import fetch_chesscom_games

    with tempfile.NamedTemporaryFile("r", suffix=".pgn") as tmp:
        fetch_chesscom_games(user, max_games, Path(tmp.name))
        return Path(tmp.name).read_text(encoding="utf-8")


def run_sync(
    db_path: Path | str,
    user: str,
    job_id: int,
    *,
    max_games: int = 20,
    depth: int = 12,
    fetch_fn=_default_fetch,
    analyze_fn=None,
) -> None:
    """Fetch, analyze and store a player's new games, reporting progress as it goes.

    Opens its own connection: this runs on a worker thread, and a SQLite connection
    belongs to the thread that made it. Both callables are injectable so the whole loop
    is testable with neither network nor engine.
    """
    if analyze_fn is None:  # imported lazily — the engine is not needed to define a job
        from engine.analyzer import analyze_game

        def analyze_fn(game):
            return analyze_game(game, depth=depth).to_dict()

    import io

    import chess.pgn

    from training.corpus import split_pgn

    conn = connect(db_path)
    try:
        pgn_text = fetch_fn(user, max_games)
        games = split_pgn(pgn_text)

        # Only the games we haven't already analyzed — this is what makes re-syncing
        # cheap, and it is why an interrupted sync can simply be run again.
        fresh = [g for g in games if not already_stored(conn, g)]
        update_job(
            conn,
            job_id,
            total=len(fresh),
            message=(
                f"{len(games)} games fetched, {len(fresh)} new to analyze."
                if fresh
                else f"{len(games)} games fetched — all already analyzed."
            ),
        )

        added = 0
        for i, pgn in enumerate(fresh, 1):
            game = chess.pgn.read_game(io.StringIO(pgn))
            if game is None or not game.mainline_moves():
                update_job(conn, job_id, done=i)
                continue
            report = analyze_fn(game)
            if ingest_game(conn, pgn, report, user, depth=depth):
                added += 1
            update_job(
                conn, job_id, done=i, added=added,
                message=f"Analyzed {i} of {len(fresh)}…",
            )

        update_job(
            conn,
            job_id,
            status="done",
            done=len(fresh),
            added=added,
            message=(
                f"Added {added} new game{'' if added == 1 else 's'}."
                if added
                else "Already up to date — nothing new to analyze."
            ),
        )
    except Exception as exc:  # noqa: BLE001 - the failure must reach the page, not a log
        update_job(
            conn,
            job_id,
            status="failed",
            message=f"{type(exc).__name__}: {exc}",
        )
        traceback.print_exc()
    finally:
        conn.close()


def start_sync(db_path: Path | str, user: str, **kwargs) -> int:
    """Create a job and run it on a daemon thread. Returns the job id."""
    conn = connect(db_path)
    try:
        job_id = create_job(conn, user)
    finally:
        conn.close()
    thread = threading.Thread(
        target=run_sync, args=(db_path, user, job_id), kwargs=kwargs, daemon=True
    )
    thread.start()
    return job_id
