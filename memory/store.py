"""Persistent record of what a player keeps getting wrong.

One SQLite file per player-history. Three tables — games, their flagged mistakes, and the
motifs tagged on each mistake — because the questions this has to answer are aggregations
("which mistake costs me the most?", "am I improving?", "is this the fourth time?") and
those are ``GROUP BY``, not similarity search.

Ingest is **idempotent on the game's movetext hash**. That is not a nicety: the coach is
going to say "the fourth time in thirty games" out loud, so a game counted twice makes it
state a false number with total confidence.

Usage:
    python -m memory.store --user mishal9 games.pgn        # analyze + store
    python -m memory.store --user mishal9 --stats          # what's in there
"""

from __future__ import annotations

import argparse
import io
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import chess.pgn

from coach.prompts import choose_coached_side
from memory.motifs import game_phase, tag_report
from training.corpus import movetext_hash

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "memory.db"

# Qualities worth remembering. Mirrors coach.prompts._MISTAKE_QUALITIES — a "good" move
# has nothing to teach and would drown the profile in rows.
_MISTAKE_QUALITIES = ("blunder", "mistake", "inaccuracy")

SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    id             INTEGER PRIMARY KEY,
    movetext_hash  TEXT NOT NULL UNIQUE,
    game_key       TEXT NOT NULL,
    user_name      TEXT NOT NULL,
    user_side      TEXT NOT NULL CHECK (user_side IN ('white', 'black')),
    white          TEXT,
    black          TEXT,
    result         TEXT,
    eco            TEXT,
    opening        TEXT,
    played_at      TEXT,
    acpl           REAL,
    blunders       INTEGER NOT NULL DEFAULT 0,
    mistakes       INTEGER NOT NULL DEFAULT 0,
    inaccuracies   INTEGER NOT NULL DEFAULT 0,
    depth          INTEGER,
    analyzed_at    TEXT NOT NULL,
    pgn            TEXT
);

CREATE TABLE IF NOT EXISTS mistakes (
    id             INTEGER PRIMARY KEY,
    game_id        INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    ply            INTEGER NOT NULL,
    move_number    INTEGER NOT NULL,
    san            TEXT NOT NULL,
    best_san       TEXT,
    quality        TEXT NOT NULL,
    cp_loss        INTEGER NOT NULL,
    win_prob_loss  REAL NOT NULL,
    phase          TEXT NOT NULL,
    fen_before     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS motifs (
    mistake_id     INTEGER NOT NULL REFERENCES mistakes(id) ON DELETE CASCADE,
    motif          TEXT NOT NULL,
    detail         TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_games_user ON games(user_name);
CREATE INDEX IF NOT EXISTS idx_mistakes_game ON mistakes(game_id);
CREATE INDEX IF NOT EXISTS idx_motifs_mistake ON motifs(mistake_id);
"""


# Columns added after the schema shipped. `CREATE TABLE IF NOT EXISTS` cannot add a column
# to a database that already has the table, and real databases already do.
_ADDED_COLUMNS = {"games": {"pgn": "TEXT"}}


def _migrate(conn: sqlite3.Connection) -> None:
    """Add any columns a later version introduced to an existing database."""
    for table, columns in _ADDED_COLUMNS.items():
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        for column, definition in columns.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def connect(path: Path | str = DEFAULT_DB) -> sqlite3.Connection:
    """Open (creating if needed) a memory database with the schema applied."""
    path = Path(path)
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if str(path) != ":memory:":
        # A sync writes for minutes while the dashboard reads; WAL lets those overlap
        # instead of the reader blocking. Not available for in-memory databases.
        conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _played_at(pgn: str) -> str | None:
    """Best available date for a game, from its PGN headers.

    Read through ``chess.pgn`` rather than a private regex so unusual-but-valid headers
    are somebody else's problem.
    """
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        return None
    headers = game.headers
    date = headers.get("UTCDate") or headers.get("Date") or ""
    date = date.replace(".", "-")
    if not date or date.startswith("?"):
        return None
    time = headers.get("UTCTime") or headers.get("Time") or ""
    return f"{date} {time}".strip()


def _side_counts(report: dict, side: str) -> dict[str, int]:
    """Per-quality counts for one side.

    The report's own summary counts *both* players together, which would make a profile
    of your mistakes include your opponent's.
    """
    counts = dict.fromkeys(_MISTAKE_QUALITIES, 0)
    for move in report.get("moves", []):
        if move["side"] == side and move["quality"] in counts:
            counts[move["quality"]] += 1
    return counts


def resolve_side(report: dict, user: str, side: str | None = None) -> str:
    """Which side the profile should be built from.

    An explicit ``side`` wins. Otherwise prefer the side ``user`` actually played, matched
    against the PGN's player names — a memory of *your* weaknesses must not absorb your
    opponents' mistakes. Only when the name matches neither (an arbitrary PGN, not the
    player's own games) do we fall back to the worse-playing side.
    """
    if side is not None:
        return side
    handle = user.strip().casefold()
    if handle and report.get("white", "").strip().casefold() == handle:
        return "white"
    if handle and report.get("black", "").strip().casefold() == handle:
        return "black"
    return choose_coached_side(report)


def backfill_pgn(conn: sqlite3.Connection, pgn: str) -> bool:
    """Fill in a stored game's text if it was ingested before we kept it.

    Returns whether a row was updated. Lets a re-sync heal an old database in passing,
    rather than needing a migration script nobody would remember to run.
    """
    with conn:
        cursor = conn.execute(
            "UPDATE games SET pgn = ? WHERE movetext_hash = ? AND pgn IS NULL",
            (pgn, movetext_hash(pgn)),
        )
    return cursor.rowcount > 0


def already_stored(conn: sqlite3.Connection, pgn: str) -> bool:
    """Has this exact game (by movetext) been ingested before?"""
    row = conn.execute(
        "SELECT 1 FROM games WHERE movetext_hash = ?", (movetext_hash(pgn),)
    ).fetchone()
    return row is not None


def ingest_game(
    conn: sqlite3.Connection,
    pgn: str,
    report: dict,
    user: str,
    *,
    side: str | None = None,
    depth: int | None = None,
) -> int | None:
    """Store one analyzed game and its tagged mistakes.

    Returns the new game's row id, or ``None`` if the game was already stored — callers
    can treat that as "nothing to do", which is what makes re-running a fetch safe.
    """
    from training.corpus import game_key  # local: only needed at ingest

    if already_stored(conn, pgn):
        backfill_pgn(conn, pgn)
        return None

    side = resolve_side(report, user, side)
    counts = _side_counts(report, side)

    with conn:  # one transaction: a half-stored game would skew every later count
        cursor = conn.execute(
            """
            INSERT INTO games (movetext_hash, game_key, user_name, user_side, white,
                               black, result, eco, opening, played_at, acpl, blunders,
                               mistakes, inaccuracies, depth, analyzed_at, pgn)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                movetext_hash(pgn),
                game_key(pgn),
                user,
                side,
                report.get("white"),
                report.get("black"),
                report.get("result"),
                report.get("eco"),
                report.get("opening"),
                _played_at(pgn),
                report.get("summary", {}).get(f"acpl_{side}"),
                counts["blunder"],
                counts["mistake"],
                counts["inaccuracy"],
                depth,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                pgn,
            ),
        )
        game_id = cursor.lastrowid

        tags_by_ply = tag_report(report, side)
        by_ply = {m["ply"]: m for m in report.get("moves", [])}
        for ply, tags in sorted(tags_by_ply.items()):
            move = by_ply[ply]
            mistake_cursor = conn.execute(
                """
                INSERT INTO mistakes (game_id, ply, move_number, san, best_san, quality,
                                      cp_loss, win_prob_loss, phase, fen_before)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    game_id,
                    ply,
                    move["move_number"],
                    move["san"],
                    move.get("best_san"),
                    move["quality"],
                    move["cp_loss"],
                    move["win_prob_loss"],
                    game_phase(move["fen_before"], ply),
                    move["fen_before"],
                ),
            )
            conn.executemany(
                "INSERT INTO motifs (mistake_id, motif, detail) VALUES (?, ?, ?)",
                [(mistake_cursor.lastrowid, t.motif, t.detail) for t in tags],
            )
    return game_id


def list_games(
    conn: sqlite3.Connection, user: str, limit: int | None = None
) -> list[dict]:
    """A player's stored games, newest first, with their per-game mistake counts."""
    rows = conn.execute(
        """
        SELECT id, white, black, result, eco, opening, played_at, user_side, acpl,
               blunders, mistakes, inaccuracies,
               blunders + mistakes + inaccuracies AS total_mistakes
        FROM games WHERE user_name = ?
        ORDER BY COALESCE(played_at, '') DESC, id DESC
        """
        + ("LIMIT ?" if limit else ""),
        (user, limit) if limit else (user,),
    ).fetchall()
    return [dict(row) for row in rows]


def game_row(conn: sqlite3.Connection, game_id: int, user: str | None = None) -> dict | None:
    """One stored game. ``user`` scopes the lookup so ids can't be walked across players."""
    sql = "SELECT * FROM games WHERE id = ?"
    params: list = [game_id]
    if user is not None:
        sql += " AND user_name = ?"
        params.append(user)
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def game_mistakes(conn: sqlite3.Connection, game_id: int) -> list[dict]:
    """Every flagged mistake in a game, in the order they were played.

    Chronological rather than worst-first: this is for reading a game through. Each
    mistake carries its motifs, whose ``detail`` quotes the engine line that produced the
    tag — which is the closest thing to an explanation available without an LLM.
    """
    rows = conn.execute(
        """
        SELECT id, ply, move_number, san, best_san, quality, cp_loss, win_prob_loss,
               phase, fen_before
        FROM mistakes WHERE game_id = ? ORDER BY ply
        """,
        (game_id,),
    ).fetchall()
    mistakes = [dict(row) for row in rows]
    if not mistakes:
        return []

    placeholders = ",".join("?" * len(mistakes))
    tags = conn.execute(
        f"""
        SELECT mistake_id, motif, detail FROM motifs
        WHERE mistake_id IN ({placeholders}) ORDER BY rowid
        """,
        [m["id"] for m in mistakes],
    ).fetchall()
    by_mistake: dict[int, list[dict]] = {}
    for tag in tags:
        by_mistake.setdefault(tag["mistake_id"], []).append(
            {"motif": tag["motif"], "detail": tag["detail"]}
        )
    for mistake in mistakes:
        mistake["motifs"] = by_mistake.get(mistake["id"], [])
    return mistakes


def stats(conn: sqlite3.Connection, user: str) -> dict:
    """Row counts for one player — enough to see that ingest did something."""
    row = conn.execute(
        """
        SELECT COUNT(*) AS games,
               COALESCE(SUM(blunders), 0) AS blunders,
               COALESCE(SUM(mistakes), 0) AS mistakes,
               COALESCE(SUM(inaccuracies), 0) AS inaccuracies
        FROM games WHERE user_name = ?
        """,
        (user,),
    ).fetchone()
    tagged = conn.execute(
        """
        SELECT COUNT(*) FROM motifs
        JOIN mistakes ON mistakes.id = motifs.mistake_id
        JOIN games ON games.id = mistakes.game_id
        WHERE games.user_name = ?
        """,
        (user,),
    ).fetchone()[0]
    return {**dict(row), "motif_tags": tagged}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze games and store them in the player's memory."
    )
    parser.add_argument("pgn", nargs="?", help="path to a .pgn file (one or many games)")
    parser.add_argument("--user", required=True, help="whose memory this is")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="path to the memory database")
    parser.add_argument(
        "--side",
        choices=("white", "black"),
        help="which side is the student (default: the worse-playing side, per game)",
    )
    parser.add_argument("--depth", type=int, default=12, help="Stockfish search depth")
    parser.add_argument("--max", type=int, help="stop after this many games")
    parser.add_argument(
        "--stats", action="store_true", help="just report what is already stored"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    conn = connect(args.db)

    if args.stats:
        info = stats(conn, args.user)
        print(
            f"{args.user}: {info['games']} games, {info['blunders']} blunders, "
            f"{info['mistakes']} mistakes, {info['inaccuracies']} inaccuracies, "
            f"{info['motif_tags']} motif tags"
        )
        return 0

    if not args.pgn:
        print("Nothing to do: pass a PGN file, or --stats.", file=sys.stderr)
        return 1

    path = Path(args.pgn)
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        return 1

    # Imported here so --stats stays instant and engine-free.
    from engine.analyzer import analyze_game
    from training.corpus import split_pgn

    games = split_pgn(path.read_text(encoding="utf-8"))
    if args.max:
        games = games[: args.max]

    stored = skipped = 0
    for i, pgn in enumerate(games, 1):
        if already_stored(conn, pgn):
            skipped += 1
            continue
        game = chess.pgn.read_game(io.StringIO(pgn))
        if game is None or not game.mainline_moves():
            skipped += 1
            continue
        print(f"[{i}/{len(games)}] analyzing...", end="\r", file=sys.stderr, flush=True)
        report = analyze_game(game, depth=args.depth).to_dict()
        if ingest_game(conn, pgn, report, args.user, side=args.side, depth=args.depth):
            stored += 1

    info = stats(conn, args.user)
    print(
        f"Stored {stored} new game(s), skipped {skipped} already-known. "
        f"{args.user} now has {info['games']} games and {info['motif_tags']} motif tags."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
