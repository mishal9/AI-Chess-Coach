"""Engine-backed tests for the game analyzer.

These require Stockfish on PATH (CI installs it; locally `brew install stockfish`).
A shallow search depth keeps them fast while still catching obvious blunders.
"""

import io
import shutil

import chess.pgn
import pytest

from engine.analyzer import analyze_game
from engine.scoring import MoveQuality

pytestmark = pytest.mark.skipif(
    shutil.which("stockfish") is None, reason="Stockfish not installed"
)

# Scholar's mate: 3...Nf6?? walks into 4.Qxf7#. Black's 3rd move is the blunder.
SCHOLARS_MATE = """[Event "Test"]
[White "Attacker"]
[Black "Victim"]
[Result "1-0"]

1. e4 e5 2. Qh5 Nc6 3. Bc4 Nf6 4. Qxf7# 1-0
"""

TEST_DEPTH = 12


def _load(pgn_text: str) -> chess.pgn.Game:
    return chess.pgn.read_game(io.StringIO(pgn_text))


def test_detects_the_blunder():
    report = analyze_game(_load(SCHOLARS_MATE), depth=TEST_DEPTH)
    assert report.summary["blunders"] >= 1


def test_worst_move_is_blacks_walk_into_mate():
    report = analyze_game(_load(SCHOLARS_MATE), depth=TEST_DEPTH)
    worst = report.summary["worst_move"]
    assert worst is not None
    assert worst["side"] == "black"
    assert worst["played"] == "Nf6"


def test_every_move_is_analyzed():
    game = _load(SCHOLARS_MATE)
    n_moves = len(list(game.mainline_moves()))
    report = analyze_game(game, depth=TEST_DEPTH)
    assert len(report.moves) == n_moves
    # Quality labels are always assigned.
    assert all(isinstance(m.quality, MoveQuality) for m in report.moves)


def test_cp_loss_never_negative():
    report = analyze_game(_load(SCHOLARS_MATE), depth=TEST_DEPTH)
    assert all(m.cp_loss >= 0 for m in report.moves)
