"""Parse PGN files into games and print a human-readable summary.

Usage:
    python -m engine.loader data/raw/sample.pgn
    python -m engine.loader data/raw/sample.pgn --moves   # also print the moves
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterator

import chess
import chess.pgn


def iter_games(pgn_path: Path) -> Iterator[chess.pgn.Game]:
    """Yield each game in a PGN file."""
    with pgn_path.open(encoding="utf-8") as fh:
        while (game := chess.pgn.read_game(fh)) is not None:
            yield game


def game_summary(game: chess.pgn.Game) -> dict:
    """Extract a compact summary dict from a parsed game."""
    headers = game.headers
    moves = list(game.mainline_moves())
    has_evals = any(node.eval() is not None for node in game.mainline())
    return {
        "white": headers.get("White", "?"),
        "black": headers.get("Black", "?"),
        "result": headers.get("Result", "*"),
        "eco": headers.get("ECO", "?"),
        "opening": headers.get("Opening", headers.get("Event", "?")),
        "plies": len(moves),       # half-moves
        "full_moves": (len(moves) + 1) // 2,
        "has_evals": has_evals,    # server-side engine annotations present?
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load and summarize a PGN file.")
    parser.add_argument("pgn", help="path to a .pgn file")
    parser.add_argument("--moves", action="store_true", help="print SAN move list")
    parser.add_argument("--limit", type=int, default=None, help="max games to show")
    args = parser.parse_args(argv)

    path = Path(args.pgn)
    if not path.exists():
        print(f"File not found: {path}")
        print("Tip: run `python -m engine.fetch_data --sample` first.")
        return 1

    count = 0
    for i, game in enumerate(iter_games(path), start=1):
        if args.limit and i > args.limit:
            break
        s = game_summary(game)
        evals = "evals✓" if s["has_evals"] else "evals✗"
        print(
            f"[{i}] {s['white']} vs {s['black']}  {s['result']}  "
            f"| {s['eco']} {s['opening']} | {s['full_moves']} moves | {evals}"
        )
        if args.moves:
            board = game.board()
            sans = []
            for mv in game.mainline_moves():
                sans.append(board.san(mv))
                board.push(mv)
            print("    " + " ".join(sans))
        count += 1

    print(f"\nParsed {count} game(s) from {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
