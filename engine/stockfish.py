"""Locate and talk to the Stockfish engine via python-chess.

Phase 0: just enough to confirm the engine is reachable and returns evaluations.
Phase 1 will build the per-move analysis (centipawn loss, mistake tagging) on top
of ``analyse``.

Usage (smoke test):
    python -m engine.stockfish
"""

from __future__ import annotations

import os
import shutil

import chess
import chess.engine


def find_stockfish() -> str:
    """Return a path to the Stockfish binary or raise a helpful error."""
    path = os.environ.get("STOCKFISH_PATH") or shutil.which("stockfish")
    if not path:
        raise FileNotFoundError(
            "Stockfish not found. Install it (`brew install stockfish`) or set "
            "STOCKFISH_PATH to the binary."
        )
    return path


def smoke_test() -> None:
    """Open the engine, analyze the start position, and print the top move + eval."""
    path = find_stockfish()
    print(f"Using Stockfish at: {path}")
    with chess.engine.SimpleEngine.popen_uci(path) as engine:
        board = chess.Board()  # standard start position
        info = engine.analyse(board, chess.engine.Limit(depth=15))
        score = info["score"].white()
        best = board.san(info["pv"][0]) if info.get("pv") else "?"
        print(f"Start position eval (White POV): {score}")
        print(f"Best move suggested: {best}")
    print("Stockfish smoke test OK ✓")


if __name__ == "__main__":
    smoke_test()
