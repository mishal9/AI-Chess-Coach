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
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from engine.fetch_data import fetch_chesscom_games
from engine.pgn import read_game
from memory.coaching import save
from memory.profile import profile_text
from memory.store import (
    SYNC_DEPTH,
    analyze,
    analyze_and_ingest,
    connect,
    game_row,
    unstored_games,
)

# chess.com handles: letters, digits, underscore and hyphen. Validated because the name is
# interpolated into an API URL, and because a typo should fail here with a clear message
# rather than as a confusing 404 from someone else's server.
USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{3,25}$")

# A running job that hasn't reported progress for this long is presumed dead.
STALE_AFTER = timedelta(minutes=10)


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


def create_job(
    conn: sqlite3.Connection,
    user: str,
    kind: str = "sync",
    game_id: int | None = None,
    message: str = "Fetching games…",
) -> int:
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


@contextmanager
def _worker_job(db_path: Path | str, job_id: int):
    """A connection for a worker thread, and a job that fails loudly.

    The worker opens its own connection because a SQLite connection belongs to the thread
    that made it. Any exception is written onto the job row rather than raised: nobody is
    waiting on the thread, so the page is the only place a failure can be seen.
    """
    conn = connect(db_path)
    try:
        yield conn
    except Exception as exc:  # noqa: BLE001 - the failure must reach the page, not a log
        update_job(conn, job_id, status="failed", message=f"{type(exc).__name__}: {exc}")
        traceback.print_exc()
    finally:
        conn.close()


def _start(db_path: Path | str, user: str, run, *run_args, job: dict, **run_kwargs) -> int:
    """Create a job row, then run ``run(db_path, user, job_id, *run_args)`` on a daemon thread."""
    with closing(connect(db_path)) as conn:
        job_id = create_job(conn, user, **job)
    threading.Thread(
        target=run,
        args=(db_path, user, job_id, *run_args),
        kwargs=run_kwargs,
        daemon=True,
    ).start()
    return job_id


def run_sync(
    db_path: Path | str,
    user: str,
    job_id: int,
    *,
    max_games: int = 20,
    depth: int = SYNC_DEPTH,
    fetch_fn=fetch_chesscom_games,
    analyze_fn=None,
) -> None:
    """Fetch, analyze and store a player's new games, reporting progress as it goes.

    ``fetch_fn`` and ``analyze_fn`` are injectable so the whole loop is testable with
    neither network nor engine.
    """
    with _worker_job(db_path, job_id) as conn:
        # Only the games we haven't already analyzed — this is what makes re-syncing
        # cheap, and it is why an interrupted sync can simply be run again.
        games, fresh = unstored_games(conn, fetch_fn(user, max_games))
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
            if analyze_and_ingest(conn, pgn, user, depth=depth, analyze_fn=analyze_fn):
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


def start_sync(db_path: Path | str, user: str, **kwargs) -> int:
    """Create a sync job and run it on a daemon thread. Returns the job id."""
    return _start(db_path, user, run_sync, job={}, **kwargs)


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
    from coach import client, prompts  # lazily: needs the optional `ollama` package

    chat_fn = chat_fn or client.chat
    model = model or client.DEFAULT_MODEL

    with _worker_job(db_path, job_id) as conn:
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
        game = read_game(row["pgn"])
        if game is None:
            update_job(conn, job_id, status="failed", message="Could not read the game.")
            return
        report = analyze_fn(game) if analyze_fn else analyze(game, row["depth"] or SYNC_DEPTH)

        side = row["user_side"]
        profile = profile_text(conn, user, exclude_game_id=game_id)
        facts = prompts.format_report_facts(report, side, profile=profile)
        messages = prompts.build_messages(report, side, profile=profile)

        update_job(conn, job_id, done=1, message=f"Asking {model} for coaching…")
        text = chat_fn(messages, model=model)

        save(conn, game_id, side, model, text, facts, used_profile=profile is not None)
        update_job(conn, job_id, status="done", done=2, message="Coaching ready.")


def start_coach(db_path: Path | str, user: str, game_id: int, **kwargs) -> int:
    """Create a coaching job and run it on a daemon thread. Returns the job id."""
    job = {"kind": "coach", "game_id": game_id, "message": "Starting…"}
    return _start(db_path, user, run_coach, game_id, job=job, **kwargs)
