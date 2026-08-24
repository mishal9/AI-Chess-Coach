"""A read-only dashboard over the player's stored memory.

Phase 6, first milestone: render what :mod:`memory.profile` already computes. There is no
upload, no analysis-on-request and no auth here, deliberately — this is a *view*, so it
cannot corrupt the pipeline that feeds it, and every number on the page is the same number
the CLI prints.

It renders the :class:`~memory.profile.PlayerProfile` **dataclass**, not the text from
:func:`memory.profile.format_profile`. That text is model-facing: pipe-delimited rows sized
for a prompt. People get HTML. Same data, two audiences, one source of truth.

Usage:
    uvicorn api.app:app --reload
    DB=/path/to/memory.db uvicorn api.app:app
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from memory.profile import PlayerProfile, build_profile
from memory.store import DEFAULT_DB, connect

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

app = FastAPI(title="Chess coach — memory")


def database_path() -> Path:
    """Where to read memory from. ``DB`` env var wins, so tests can point elsewhere."""
    return Path(os.environ.get("DB") or DEFAULT_DB)


def open_db() -> sqlite3.Connection:
    """Open the memory database, or 503 if it isn't there yet.

    A missing database is an ordinary state — nobody has run the ingest — so it gets a
    clear instruction rather than a stack trace.
    """
    path = database_path()
    if not path.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                f"No memory database at {path}. Create one with: "
                "python -m memory.store --user <name> games.pgn"
            ),
        )
    return connect(path)


def known_players(conn: sqlite3.Connection) -> list[dict]:
    """Every player with stored games, most games first."""
    rows = conn.execute(
        """
        SELECT user_name, COUNT(*) AS games, MAX(played_at) AS latest
        FROM games GROUP BY user_name ORDER BY games DESC
        """
    ).fetchall()
    return [dict(row) for row in rows]


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    """Straight to the dashboard when there's only one player, else offer a choice."""
    conn = open_db()
    players = known_players(conn)
    if len(players) == 1:
        return dashboard(request, players[0]["user_name"])
    return TEMPLATES.TemplateResponse(
        request=request, name="index.html", context={"players": players}
    )


@app.get("/player/{user}", response_class=HTMLResponse)
def dashboard(request: Request, user: str, last: int | None = None):
    """One player's recurring weaknesses. ``?last=N`` narrows to recent games."""
    conn = open_db()
    profile: PlayerProfile = build_profile(conn, user, last)
    if profile.is_empty:
        raise HTTPException(status_code=404, detail=f"No stored games for {user!r}.")
    return TEMPLATES.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "profile": profile,
            "window": last,
            "total_games": len(known_players(conn)) and _total_games(conn, user),
        },
    )


def _total_games(conn: sqlite3.Connection, user: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM games WHERE user_name = ?", (user,)
    ).fetchone()
    return row["n"]
