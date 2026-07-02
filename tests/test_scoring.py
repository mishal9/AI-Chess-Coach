"""Unit tests for the pure scoring logic."""

import math

from engine.scoring import (
    BLUNDER_WP,
    INACCURACY_WP,
    MATE_CP,
    MISTAKE_WP,
    MoveQuality,
    capped_centipawn_loss,
    centipawn_loss,
    classify,
    mate_to_cp,
    win_prob,
    win_prob_loss,
)


class TestClassify:
    def test_buckets_at_thresholds(self):
        assert classify(BLUNDER_WP) is MoveQuality.BLUNDER
        assert classify(MISTAKE_WP) is MoveQuality.MISTAKE
        assert classify(INACCURACY_WP) is MoveQuality.INACCURACY

    def test_just_below_thresholds(self):
        assert classify(BLUNDER_WP - 0.01) is MoveQuality.MISTAKE
        assert classify(MISTAKE_WP - 0.01) is MoveQuality.INACCURACY
        assert classify(INACCURACY_WP - 0.01) is MoveQuality.GOOD

    def test_perfect_move_is_best(self):
        assert classify(0.0) is MoveQuality.BEST

    def test_large_loss_is_blunder(self):
        assert classify(0.9) is MoveQuality.BLUNDER

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


class TestWinProb:
    def test_even_position_is_half(self):
        assert win_prob(0) == 0.5

    def test_monotonic_in_white_favor(self):
        assert win_prob(-500) < win_prob(0) < win_prob(500)

    def test_saturates_at_mate(self):
        assert win_prob(MATE_CP) > 0.999
        assert win_prob(-MATE_CP) < 0.001


class TestWinProbLoss:
    def test_white_swing_is_positive(self):
        # White drops from +50 to -300 → a real loss of win probability.
        loss = win_prob_loss(eval_before_best=50, eval_after=-300, mover_is_white=True)
        assert loss > 0

    def test_black_mover_is_mirrored(self):
        # Same eval swing, opposite movers → symmetric win-prob loss.
        white = win_prob_loss(50, -300, mover_is_white=True)
        black = win_prob_loss(-50, 300, mover_is_white=False)
        assert math.isclose(white, black, abs_tol=1e-9)

    def test_negative_swing_clamped_to_zero(self):
        assert win_prob_loss(100, 400, mover_is_white=True) == 0.0

    def test_decided_position_barely_moves(self):
        # Already crushing (+900 → +600): still winning, so tiny win-prob loss, not a blunder.
        loss = win_prob_loss(900, 600, mover_is_white=True)
        assert loss < INACCURACY_WP
        assert classify(loss) in (MoveQuality.BEST, MoveQuality.GOOD)

    def test_slower_forced_mate_is_not_a_blunder(self):
        # mate-in-3 (≈MATE_CP) → mate-in-8 is still 100% winning.
        loss = win_prob_loss(mate_to_cp(3), mate_to_cp(8), mover_is_white=True)
        assert classify(loss) in (MoveQuality.BEST, MoveQuality.GOOD)


class TestCappedCentipawnLoss:
    def test_caps_decided_swing(self):
        # A mate (±MATE_CP) collapsing to a mere +500 would be a ~9500 raw loss…
        assert centipawn_loss(MATE_CP, 500, mover_is_white=True) > 9000
        # …but capped it is bounded by the ±EVAL_CAP window.
        assert capped_centipawn_loss(MATE_CP, 500, mover_is_white=True) == 500

    def test_matches_plain_loss_within_cap(self):
        assert capped_centipawn_loss(50, -300, mover_is_white=True) == 350


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
