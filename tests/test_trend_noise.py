"""The trend must not name a direction the sample cannot support.

This project has been fooled by exactly this size of sample twice: the "concentrated
weakness in one_blunder/inaccuracies" reading that turned out to be noise, and the 6-game
held-out set that had to grow to 29 because proportion metrics swung ~17 points per game.
A profile that tells a player they are declining, on the strength of three extra mistakes
across seven games, is both wrong and discouraging.
"""

from __future__ import annotations

import pytest

from memory.profile import build_profile, format_profile
from memory.store import connect, ingest_game
from tests.test_memory_store import HANG_FEN, move, pgn
from tests.test_memory_store import report as _base_report


def report_with(mistakes: int) -> dict:
    """A report where the white player made exactly ``mistakes`` flagged blunders."""
    moves = [
        move(ply=i * 2 + 1, side="white", quality="blunder", fen_before=HANG_FEN)
        for i in range(mistakes)
    ]
    return _base_report(moves=moves)


def ingest_series(conn, counts: list[int], user: str = "alice") -> None:
    """Store one game per entry in ``counts``, in order, each with that many mistakes."""
    for i, mistakes in enumerate(counts):
        ingest_game(
            conn,
            pgn(moves=f"1. e4 e5 {i} 1-0", date=f"2026.01.{i + 1:02d}"),
            report_with(mistakes),
            user,
        )


@pytest.fixture
def conn():
    connection = connect(":memory:")
    yield connection
    connection.close()


class TestNoiseFloor:
    def test_a_small_gap_between_noisy_halves_is_unclear(self, conn):
        # The real maia1 shape: means 2.14 vs 2.57, but the spread swamps the gap.
        ingest_series(conn, [1, 3, 4, 1, 5, 1, 0] + [1, 1, 4, 3, 3, 1, 5])
        trend = build_profile(conn, "alice").trend
        assert trend.direction == "unclear"
        assert abs(trend.mistakes_delta) < trend.noise_floor

    def test_a_large_consistent_drop_is_improvement(self, conn):
        ingest_series(conn, [5, 6, 5, 6, 5, 6] + [0, 1, 0, 1, 0, 1])
        trend = build_profile(conn, "alice").trend
        assert trend.direction == "improving"
        assert trend.mistakes_delta < 0

    def test_a_large_consistent_rise_is_decline(self, conn):
        ingest_series(conn, [0, 1, 0, 1, 0, 1] + [5, 6, 5, 6, 5, 6])
        assert build_profile(conn, "alice").trend.direction == "declining"

    def test_one_game_per_half_has_no_computable_spread(self, conn):
        """With no variance estimate the floor is infinite, so nothing is ever claimed."""
        from memory.profile import Trend

        trend = Trend(
            earlier_games=1, later_games=1,
            earlier_mistakes_per_game=0.0, later_mistakes_per_game=9.0,
            earlier_acpl=10.0, later_acpl=90.0,
            earlier_damage_per_game=0.0, later_damage_per_game=1.0,
            earlier_counts=(0,), later_counts=(9,),
        )
        assert trend.noise_floor == float("inf")
        assert trend.direction == "unclear"


class TestRendering:
    def test_unclear_says_so_instead_of_leaving_numbers_to_imply_it(self, conn):
        ingest_series(conn, [1, 3, 4, 1, 5, 1, 0] + [1, 1, 4, 3, 3, 1, 5])
        text = format_profile(build_profile(conn, "alice"))
        assert "| unclear" in text
        # The renderer states the verdict; the prompt forbids describing a direction.
        from coach.prompts import SYSTEM_PROMPT
        assert "must NOT tell the student they" in SYSTEM_PROMPT

    def test_the_old_unconditional_verdict_is_gone(self, conn):
        """The bug this PR fixes: 'more mistakes lately' stated flatly off noise."""
        ingest_series(conn, [1, 3, 4, 1, 5, 1, 0] + [1, 1, 4, 3, 3, 1, 5])
        text = format_profile(build_profile(conn, "alice"))
        assert "more mistakes lately" not in text
        assert "fewer mistakes lately" not in text

    def test_a_real_change_is_reported_with_severity_weighting(self, conn):
        ingest_series(conn, [5, 6, 5, 6, 5, 6] + [0, 1, 0, 1, 0, 1])
        text = format_profile(build_profile(conn, "alice"))
        assert "| improving" in text
        assert "damage_per_game" in text

    def test_the_raw_numbers_are_always_shown(self, conn):
        """Gating the verdict must not hide the data behind it."""
        ingest_series(conn, [1, 3, 4, 1, 5, 1, 0] + [1, 1, 4, 3, 3, 1, 5])
        text = format_profile(build_profile(conn, "alice"))
        assert "mistakes_per_game" in text
        assert "centipawn_loss" in text
        assert "normal_variation" in text


class TestDamageWeighting:
    def test_damage_separates_a_blunder_from_an_inaccuracy(self, conn):
        """Counting alone calls these equal; damage does not."""
        severe = _base_report(moves=[
            move(ply=1, side="white", quality="blunder", win_prob_loss=0.40),
        ])
        mild = _base_report(moves=[
            move(ply=1, side="white", quality="inaccuracy", win_prob_loss=0.10),
        ])
        for i in range(3):
            ingest_game(conn, pgn(moves=f"1. e4 e5 {i} 1-0", date=f"2026.01.0{i + 1}"),
                        severe, "alice")
        for i in range(3, 6):
            ingest_game(conn, pgn(moves=f"1. e4 e5 {i} 1-0", date=f"2026.01.0{i + 1}"),
                        mild, "alice")
        trend = build_profile(conn, "alice").trend
        # Same mistake count in both halves, very different damage.
        assert trend.earlier_mistakes_per_game == trend.later_mistakes_per_game
        assert trend.earlier_damage_per_game > trend.later_damage_per_game
        assert trend.damage_delta < 0
