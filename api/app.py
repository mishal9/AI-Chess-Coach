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

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from memory.jobs import USERNAME_RE, active_job, latest_job, start_sync
from memory.profile import PlayerProfile, build_profile
from memory.store import DEFAULT_DB, connect, game_mistakes, game_row, list_games

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

app = FastAPI(title="Chess coach — memory")


def database_path() -> Path:
    """Where to read memory from. ``DB`` env var wins, so tests can point elsewhere."""
    return Path(os.environ.get("DB") or DEFAULT_DB)


def open_db(create: bool = False) -> sqlite3.Connection:
    """Open the memory database, or 503 if it isn't there yet.

    A missing database is an ordinary state — nobody has synced yet — so it gets a clear
    instruction rather than a stack trace. ``create=True`` for the sync endpoint, which
    is precisely the thing that makes the database exist.
    """
    path = database_path()
    if not create and not path.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                f"No memory database at {path}. Sync a chess.com username from the "
                "home page, or run: python -m memory.store --user <name> games.pgn"
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
    """Straight to the dashboard when there's only one player, else offer a choice.

    Tolerates a missing database so a first-time visitor gets the sync form rather than a
    503 telling them to go and use the CLI.
    """
    path = database_path()
    players = []
    if path.exists():
        conn = connect(path)
        players = known_players(conn)
        if len(players) == 1:
            return dashboard(request, players[0]["user_name"])
    return TEMPLATES.TemplateResponse(
        request=request, name="index.html", context={"players": players}
    )


@app.post("/sync")
def sync(user: str = Form(...), max_games: int = Form(20)):
    """Start a background sync of a chess.com account, then show its dashboard.

    Refuses a second concurrent sync for the same player: two workers analyzing the same
    fetch would duplicate minutes of Stockfish for nothing, and the ingest would discard
    one side's results anyway.
    """
    user = user.strip()
    if not USERNAME_RE.match(user):
        raise HTTPException(
            status_code=400,
            detail=(
                "That doesn't look like a chess.com username — letters, digits, "
                "underscore and hyphen only, 3 to 25 characters."
            ),
        )
    max_games = max(1, min(max_games, 100))

    conn = open_db(create=True)
    if active_job(conn, user) is None:
        start_sync(database_path(), user, max_games=max_games)
    return RedirectResponse(f"/player/{user}", status_code=303)


@app.get("/player/{user}", response_class=HTMLResponse)
def dashboard(request: Request, user: str, last: int | None = None):
    """One player's recurring weaknesses. ``?last=N`` narrows to recent games.

    A player with no games but a job in flight is not a 404 — that is the ordinary state
    for the first thirty seconds after someone types their username in.
    """
    conn = open_db()
    job = latest_job(conn, user)
    profile: PlayerProfile = build_profile(conn, user, last)
    if profile.is_empty and job is None:
        raise HTTPException(status_code=404, detail=f"No stored games for {user!r}.")
    return TEMPLATES.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "profile": profile,
            "job": job,
            "window": last,
            "total_games": _total_games(conn, user),
        },
    )


@app.get("/player/{user}/games", response_class=HTMLResponse)
def games(request: Request, user: str):
    """Every stored game for a player, newest first — the way into a single game."""
    conn = open_db()
    rows = list_games(conn, user)
    if not rows:
        raise HTTPException(status_code=404, detail=f"No stored games for {user!r}.")
    return TEMPLATES.TemplateResponse(
        request=request, name="games.html", context={"user": user, "games": rows}
    )


@app.get("/player/{user}/game/{game_id}", response_class=HTMLResponse)
def game(request: Request, user: str, game_id: int):
    """One game's mistakes, in the order they were played.

    Scoped by user as well as id so a game id can't be walked across players.
    """
    conn = open_db()
    row = game_row(conn, game_id, user)
    if row is None:
        raise HTTPException(status_code=404, detail="No such game for this player.")
    return TEMPLATES.TemplateResponse(
        request=request,
        name="game.html",
        context={
            "user": user,
            "game": row,
            "mistakes": game_mistakes(conn, game_id),
        },
    )


def _total_games(conn: sqlite3.Connection, user: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM games WHERE user_name = ?", (user,)
    ).fetchone()
    return row["n"]
