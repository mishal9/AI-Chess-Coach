"""Unit tests for the pure scoring logic."""

from engine.scoring import (
    BLUNDER_THRESHOLD,
    INACCURACY_THRESHOLD,
    MATE_CP,
    MISTAKE_THRESHOLD,
    MoveQuality,
    centipawn_loss,
    classify,
    mate_to_cp,
)


class TestClassify:
    def test_buckets_at_thresholds(self):
        assert classify(BLUNDER_THRESHOLD) is MoveQuality.BLUNDER
        assert classify(MISTAKE_THRESHOLD) is MoveQuality.MISTAKE
        assert classify(INACCURACY_THRESHOLD) is MoveQuality.INACCURACY

    def test_just_below_thresholds(self):
        assert classify(BLUNDER_THRESHOLD - 1) is MoveQuality.MISTAKE
        assert classify(MISTAKE_THRESHOLD - 1) is MoveQuality.INACCURACY
        assert classify(INACCURACY_THRESHOLD - 1) is MoveQuality.GOOD

    def test_perfect_move_is_best(self):
        assert classify(0) is MoveQuality.BEST

    def test_large_loss_is_blunder(self):
        assert classify(1500) is MoveQuality.BLUNDER

    def test_symbols(self):
        assert MoveQuality.BLUNDER.symbol == "??"
        assert MoveQuality.MISTAKE.symbol == "?"
        assert MoveQuality.INACCURACY.symbol == "?!"
        assert MoveQuality.BEST.symbol == ""


class TestCentipawnLoss:
    def test_white_losing_value(self):
        # White was +50 best, ended at -300 → gave up 350.
        assert centipawn_loss(eval_before_best=50, eval_after=-300, mover_is_white=True) == 350

    def test_black_losing_value(self):
        # White-POV: Black was at -50 (good for Black), blundered to +300.
        # From Black's perspective that's a 350cp loss.
        assert centipawn_loss(eval_before_best=-50, eval_after=300, mover_is_white=False) == 350

    def test_best_move_zero_loss(self):
        assert centipawn_loss(eval_before_best=120, eval_after=120, mover_is_white=True) == 0

    def test_negative_loss_clamped_to_zero(self):
        # Played move looks "better than best" due to search noise → clamp to 0.
        assert centipawn_loss(eval_before_best=100, eval_after=150, mover_is_white=True) == 0
        assert centipawn_loss(eval_before_best=100, eval_after=50, mover_is_white=False) == 0


class TestMateToCp:
    def test_sign(self):
        assert mate_to_cp(3) > 0       # we are mating
        assert mate_to_cp(-3) < 0      # we are getting mated

    def test_closer_mate_scores_higher(self):
        assert mate_to_cp(1) > mate_to_cp(5)
        assert mate_to_cp(-1) < mate_to_cp(-5)

    def test_beyond_material_range(self):
        # Even a distant mate outweighs being up a queen (~900cp).
        assert mate_to_cp(40) > 900
        assert abs(mate_to_cp(5)) < MATE_CP  # but still capped below the ceiling
