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

from memory.store import already_stored, backfill_pgn, connect, ingest_game

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
    updated_at  TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'sync',
    game_id     INTEGER
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
    kind: str = "sync"
    game_id: int | None = None

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


# Columns added after the jobs table shipped. `CREATE TABLE IF NOT EXISTS` will not add a
# column to a database that already has the table, and real databases already do.
_ADDED_COLUMNS = {
    "kind": "TEXT NOT NULL DEFAULT 'sync'",
    "game_id": "INTEGER",
}


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create the jobs table if absent, and add any columns a later version introduced."""
    conn.executescript(JOBS_SCHEMA)
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)")}
    for column, definition in _ADDED_COLUMNS.items():
        if column not in existing:
            with conn:
                conn.execute(f"ALTER TABLE jobs ADD COLUMN {column} {definition}")


def create_job(
    conn: sqlite3.Connection,
    user: str,
    kind: str = "sync",
    game_id: int | None = None,
    message: str = "Fetching games…",
) -> int:
    ensure_schema(conn)
    with conn:
        cursor = conn.execute(
            """
            INSERT INTO jobs (user_name, status, message, started_at, updated_at,
                              kind, game_id)
            VALUES (?, 'running', ?, ?, ?, ?, ?)
            """,
            (user, message, _now(), _now(), kind, game_id),
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


def latest_job(
    conn: sqlite3.Connection,
    user: str,
    kind: str | None = None,
    game_id: int | None = None,
) -> Job | None:
    """The most recent job for a player, whatever its state.

    ``kind``/``game_id`` narrow it, so a running sync is not mistaken for a running coach
    job — they appear on different pages and must not drive each other's spinners.
    """
    ensure_schema(conn)
    sql = "SELECT * FROM jobs WHERE user_name = ?"
    params: list = [user]
    if kind is not None:
        sql += " AND kind = ?"
        params.append(kind)
    if game_id is not None:
        sql += " AND game_id = ?"
        params.append(game_id)
    row = conn.execute(sql + " ORDER BY id DESC LIMIT 1", params).fetchone()
    return _row_to_job(row) if row else None


def active_job(
    conn: sqlite3.Connection,
    user: str,
    kind: str | None = None,
    game_id: int | None = None,
) -> Job | None:
    """The player's currently-running job, if any — used to refuse a second one."""
    job = latest_job(conn, user, kind, game_id)
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

        # Every fetched game is an opportunity to fill in text we didn't store on an
        # earlier version — cheap, and it happens before the filter below discards the
        # games we already have, which is the only time we hold their PGN.
        for pgn in games:
            backfill_pgn(conn, pgn)

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


def run_coach(
    db_path: Path | str,
    user: str,
    job_id: int,
    game_id: int,
    *,
    model: str | None = None,
    chat_fn=None,
    analyze_fn=None,
) -> None:
    """Generate coaching for one stored game and save it with the facts it was given.

    Re-analyzes the game from its stored PGN **at the depth it was originally analyzed
    at**, so the facts block the coach sees matches what the game page shows. Stockfish is
    deterministic at a fixed depth, so this reproduces the original report rather than
    approximating it — which is why the PGN is worth storing.

    The player profile deliberately **excludes this game**, so "the fourth time" counts
    four *previous* occurrences rather than including the one being discussed.
    """
    import io

    import chess.pgn

    from coach import client, prompts
    from memory.coaching import save
    from memory.profile import build_profile, format_profile
    from memory.store import game_row

    if chat_fn is None:
        chat_fn = client.chat
    model = model or client.DEFAULT_MODEL

    conn = connect(db_path)
    try:
        row = game_row(conn, game_id, user)
        if row is None:
            update_job(conn, job_id, status="failed", message="No such game.")
            return
        if not row.get("pgn"):
            update_job(
                conn,
                job_id,
                status="failed",
                message="This game was analyzed before the game text was stored. "
                "Sync again to fill it in, then coaching will work.",
            )
            return

        update_job(conn, job_id, total=2, done=0, message="Re-analyzing the position…")
        game = chess.pgn.read_game(io.StringIO(row["pgn"]))
        if game is None:
            update_job(conn, job_id, status="failed", message="Could not read the game.")
            return

        if analyze_fn is None:
            from engine.analyzer import analyze_game

            report = analyze_game(game, depth=row["depth"] or 12).to_dict()
        else:
            report = analyze_fn(game)

        side = row["user_side"]
        profile = build_profile(conn, user, exclude_game_id=game_id)
        profile_text = None if profile.is_empty else format_profile(profile)

        facts = prompts.format_report_facts(report, side, profile=profile_text)
        messages = prompts.build_messages(report, side, profile=profile_text)

        update_job(conn, job_id, done=1, message=f"Asking {model} for coaching…")
        text = chat_fn(messages, model=model)

        save(conn, game_id, side, model, text, facts, used_profile=profile_text is not None)
        update_job(conn, job_id, status="done", done=2, message="Coaching ready.")
    except Exception as exc:  # noqa: BLE001 - the failure must reach the page
        update_job(conn, job_id, status="failed", message=f"{type(exc).__name__}: {exc}")
        traceback.print_exc()
    finally:
        conn.close()


def start_coach(db_path: Path | str, user: str, game_id: int, **kwargs) -> int:
    """Create a coaching job and run it on a daemon thread. Returns the job id."""
    conn = connect(db_path)
    try:
        job_id = create_job(
            conn, user, kind="coach", game_id=game_id, message="Starting…"
        )
    finally:
        conn.close()
    thread = threading.Thread(
        target=run_coach,
        args=(db_path, user, job_id, game_id),
        kwargs=kwargs,
        daemon=True,
    )
    thread.start()
    return job_id
