"""Fetch a player's games as PGN text from public APIs, no auth required.

- **chess.com** — a user's most recent standard games via the Published-Data API. This is
  what the app syncs.
- **Lichess** — a user's games (with server-side ``%eval`` annotations). Used by the
  research code that builds the training corpus and the held-out set.

The analyzer runs its own Stockfish pass, so games needn't come pre-annotated.

Usage:
    python -m engine.fetch_data --user mshah509 --max 20
    python -m engine.fetch_data --source lichess --user DrNykterstein --max 20
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
LICHESS_API = "https://lichess.org/api/games/user/{user}"
CHESSCOM_ARCHIVES = "https://api.chess.com/pub/player/{user}/games/archives"

# chess.com's Published-Data API rejects requests without a User-Agent (HTTP 403).
CHESSCOM_HEADERS = {"User-Agent": "chess-analyzer (github.com/mishal9/chess-analyzer)"}


def fetch_lichess_games(
    user: str, max_games: int, perf_type: str | None = None
) -> str:
    """Up to ``max_games`` of ``user``'s Lichess games as one PGN string (evals + openings).

    ``perf_type`` optionally restricts to Lichess speed categories (comma-separated, e.g.
    ``"rapid,classical"``) — slower time controls where clean, low-ACPL play is common.
    """
    params = {
        "max": max_games,
        "evals": "true",
        "opening": "true",
        "clocks": "false",
        "moves": "true",
    }
    if perf_type:
        params["perfType"] = perf_type
    headers = {"Accept": "application/x-chess-pgn"}
    url = LICHESS_API.format(user=user)
    print(f"Fetching up to {max_games} games for '{user}' from Lichess...", file=sys.stderr)
    resp = requests.get(url, params=params, headers=headers, timeout=60)
    resp.raise_for_status()
    text = resp.text.strip()
    if not text:
        raise RuntimeError("Lichess returned no games.")
    return text + "\n"


def fetch_chesscom_games(user: str, max_games: int) -> str:
    """A chess.com user's ``max_games`` most recent *standard* games as one PGN string.

    chess.com groups games into monthly archives. We walk the archive list newest-first
    and, within each month, take games newest-first (the API lists them oldest-first),
    skipping non-standard variants (Chess960, bughouse, …) that the analyzer can't parse.
    """
    arch_url = CHESSCOM_ARCHIVES.format(user=user)
    resp = requests.get(arch_url, headers=CHESSCOM_HEADERS, timeout=60)
    resp.raise_for_status()
    archives = resp.json().get("archives", [])

    collected: list[str] = []
    for month_url in reversed(archives):  # newest month first
        month = requests.get(month_url, headers=CHESSCOM_HEADERS, timeout=60)
        month.raise_for_status()
        for game in reversed(month.json().get("games", [])):  # newest game first
            if game.get("rules") != "chess":
                continue  # skip variants the standard engine can't analyze
            pgn = (game.get("pgn") or "").strip()
            if pgn:
                collected.append(pgn)
            if len(collected) >= max_games:
                break
        if len(collected) >= max_games:
            break

    if not collected:
        raise RuntimeError(f"No standard chess games found for '{user}'.")
    return "\n\n".join(collected) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch a player's games as PGN.")
    parser.add_argument(
        "--source",
        choices=["chesscom", "lichess"],
        default="chesscom",
        help="which public API to fetch from (default: chesscom)",
    )
    parser.add_argument("--user", required=True, help="username on the chosen source")
    parser.add_argument("--max", type=int, default=20, help="number of games")
    parser.add_argument("--out", default=None, help="output .pgn path")
    args = parser.parse_args(argv)

    out = Path(args.out) if args.out else DATA_DIR / f"{args.user}.pgn"
    fetch = fetch_chesscom_games if args.source == "chesscom" else fetch_lichess_games
    try:
        text = fetch(args.user, args.max)
    except Exception as exc:  # noqa: BLE001 - surface the error to the terminal
        print(f"{args.source} fetch failed ({exc}).", file=sys.stderr)
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"Saved games to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
