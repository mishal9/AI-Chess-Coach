"""Download a small slice of public chess game data.

Supports two public sources, no auth required:
- **Lichess** — a user's games as PGN (with server-side ``%eval`` annotations).
- **chess.com** — a user's most recent standard games via the Published-Data API.

The analyzer runs its own Stockfish pass, so games needn't come pre-annotated; any
legal standard-chess PGN works.

Usage:
    python -m engine.fetch_data --sample
    python -m engine.fetch_data --user DrNykterstein --max 20
    python -m engine.fetch_data --source chesscom --user hikaru --max 20
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

# A strong public account; their games carry server-side engine evals.
DEFAULT_USER = "DrNykterstein"  # Magnus Carlsen's main Lichess account

# Offline fallback so the loader can be validated without a network:
# Morphy's "Opera Game" (1858), a famous miniature.
OPERA_GAME = """[Event "Paris Opera"]
[Site "Paris FRA"]
[Date "1858.??.??"]
[White "Paul Morphy"]
[Black "Duke Karl / Count Isouard"]
[Result "1-0"]
[ECO "C41"]

1. e4 e5 2. Nf3 d6 3. d4 Bg4 4. dxe5 Bxf3 5. Qxf3 dxe5 6. Bc4 Nf6 7. Qb3 Qe7
8. Nc3 c6 9. Bg5 b5 10. Nxb5 cxb5 11. Bxb5+ Nbd7 12. O-O-O Rd8 13. Rxd7 Rxd7
14. Rd1 Qe6 15. Bxd7+ Nxd7 16. Qb8+ Nxb8 17. Rd8# 1-0
"""


def fetch_lichess_games(user: str, max_games: int, out: Path) -> int:
    """Fetch ``max_games`` of ``user`` as PGN (with evals + openings). Returns count."""
    params = {
        "max": max_games,
        "evals": "true",
        "opening": "true",
        "clocks": "false",
        "moves": "true",
    }
    headers = {"Accept": "application/x-chess-pgn"}
    url = LICHESS_API.format(user=user)
    print(f"Fetching up to {max_games} games for '{user}' from Lichess...")
    resp = requests.get(url, params=params, headers=headers, timeout=60)
    resp.raise_for_status()
    text = resp.text.strip()
    if not text:
        raise RuntimeError("Lichess returned no games.")
    out.write_text(text + "\n")
    # Each game's PGN starts with an [Event ...] tag.
    return text.count("[Event ")


def fetch_chesscom_games(user: str, max_games: int, out: Path) -> int:
    """Fetch a chess.com user's ``max_games`` most recent *standard* games as PGN.

    chess.com groups games into monthly archives. We walk the archive list newest-first
    and, within each month, take games newest-first (the API lists them oldest-first),
    skipping non-standard variants (Chess960, bughouse, …) that the analyzer can't parse.
    Returns the number of games written.
    """
    arch_url = CHESSCOM_ARCHIVES.format(user=user)
    print(f"Fetching up to {max_games} recent games for '{user}' from chess.com...")
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
    out.write_text("\n\n".join(collected) + "\n")
    return len(collected)


def write_fallback(out: Path) -> int:
    out.write_text(OPERA_GAME)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch a small chess PGN sample.")
    parser.add_argument(
        "--source",
        choices=["lichess", "chesscom"],
        default="lichess",
        help="which public API to fetch from (default: lichess)",
    )
    parser.add_argument("--user", default=None, help="username on the chosen source")
    parser.add_argument("--max", type=int, default=10, help="number of games")
    parser.add_argument(
        "--sample",
        action="store_true",
        help="shorthand: fetch the default Lichess sample into data/raw/sample.pgn",
    )
    parser.add_argument("--out", default=None, help="output .pgn path")
    args = parser.parse_args(argv)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = Path(args.out) if args.out else DATA_DIR / "sample.pgn"

    if args.source == "chesscom":
        if not args.user:
            parser.error("--user is required with --source chesscom")
        try:
            n = fetch_chesscom_games(args.user, args.max, out)
        except Exception as exc:  # noqa: BLE001 - surface the error, no fallback
            print(f"chess.com fetch failed ({exc}).", file=sys.stderr)
            return 1
        print(f"Saved {n} games to {out}")
        return 0

    # Lichess (default) — best-effort with an offline fallback game.
    user = args.user or DEFAULT_USER
    try:
        n = fetch_lichess_games(user, args.max, out)
        print(f"Saved {n} games to {out}")
    except Exception as exc:  # noqa: BLE001 - network is best-effort in Phase 0
        print(f"Network fetch failed ({exc}). Writing offline fallback game.", file=sys.stderr)
        n = write_fallback(out)
        print(f"Saved {n} fallback game to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
