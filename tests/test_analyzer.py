"""Engine-backed tests for the game analyzer.

These require Stockfish on PATH (CI installs it; locally `brew install stockfish`).
A shallow search depth keeps them fast while still catching obvious blunders.
"""

import io
import shutil

import chess.pgn
import pytest

from engine.analyzer import GameReport, MoveAnalysis, analyze_game
from engine.scoring import MATE_CP, MoveQuality, classify, win_prob_loss

requires_stockfish = pytest.mark.skipif(
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


@requires_stockfish
def test_detects_the_blunder():
    report = analyze_game(_load(SCHOLARS_MATE), depth=TEST_DEPTH)
    assert report.summary["blunders"] >= 1


@requires_stockfish
def test_worst_move_is_blacks_walk_into_mate():
    report = analyze_game(_load(SCHOLARS_MATE), depth=TEST_DEPTH)
    worst = report.summary["worst_move"]
    assert worst is not None
    assert worst["side"] == "black"
    assert worst["played"] == "Nf6"


@requires_stockfish
def test_every_move_is_analyzed():
    game = _load(SCHOLARS_MATE)
    n_moves = len(list(game.mainline_moves()))
    report = analyze_game(game, depth=TEST_DEPTH)
    assert len(report.moves) == n_moves
    # Quality labels are always assigned.
    assert all(isinstance(m.quality, MoveQuality) for m in report.moves)


@requires_stockfish
def test_cp_loss_never_negative():
    report = analyze_game(_load(SCHOLARS_MATE), depth=TEST_DEPTH)
    assert all(m.cp_loss >= 0 for m in report.moves)


def _move(side, san, eval_before, eval_after, *, ply=1, best_san="best") -> MoveAnalysis:
    """Build a MoveAnalysis with quality/win-prob derived from the evals (no engine)."""
    wp_loss = win_prob_loss(eval_before, eval_after, mover_is_white=(side == "white"))
    return MoveAnalysis(
        ply=ply,
        move_number=(ply + 1) // 2,
        side=side,
        san=san,
        best_san=best_san,
        eval_before=eval_before,
        eval_after=eval_after,
        cp_loss=max(0, (eval_before - eval_after) if side == "white" else (eval_after - eval_before)),
        win_prob_loss=wp_loss,
        quality=classify(wp_loss),
        fen_before="",
    )


def _decided_report() -> GameReport:
    report = GameReport(white="W", black="B", result="1-0", eco="?", opening="?")
    report.moves = [
        _move("white", "Bd3", 900, 600, ply=1),      # still crushing → not a blunder
        _move("white", "Qxb7", 50, -300, ply=3),     # the real blunder (win-prob collapse)
        _move("white", "Rxf7", MATE_CP, 500, ply=5),  # let a forced mate slip, still winning
    ]
    return report


def test_decided_position_move_is_not_a_blunder():
    # A move that keeps a won position won must not be labeled a blunder.
    m = _decided_report().moves[0]
    assert m.win_prob_loss < 0.10
    assert m.quality in (MoveQuality.BEST, MoveQuality.GOOD)


def test_worst_ranks_by_win_probability_not_raw_cp():
    # The mate-slip move has a huge *raw* cp_loss but is still winning; the true blunder is
    # the +50 → -300 collapse. Worst-move must pick the latter.
    worst = _decided_report().summary["worst_move"]
    assert worst["played"] == "Qxb7"


def test_acpl_is_capped_for_decided_positions():
    # Without capping, the mate-slip move alone would push ACPL into the thousands.
    assert _decided_report().summary["acpl_white"] < 1000
