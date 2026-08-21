"""Storing games and aggregating them into a player profile.

All offline: an in-memory database and hand-built report dicts, no Stockfish. The point of
these tests is the bookkeeping — that a game counted once stays counted once, and that a
profile of *your* mistakes never absorbs your opponent's.
"""

from __future__ import annotations

import pytest

from memory.profile import (
    MIN_GAMES_FOR_TREND,
    MIN_OCCURRENCES_FOR_PATTERN,
    build_profile,
    format_profile,
)
from memory.store import (
    _side_counts,
    already_stored,
    connect,
    ingest_game,
    resolve_side,
    stats,
)

# White plays Nxe5??; Black's Nxe5 wins a knight — the one motif fixture these tests need.
HANG_FEN = "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 1"
HANG_REPLY_FEN = "r1bqkbnr/pppp1ppp/2n5/4N3/2B1P3/8/PPPP1PPP/RNBQK2R b KQkq - 0 1"


def pgn(moves: str = "1. e4 e5 2. Nf3 Nc6 1-0", white="alice", black="bob",
        date="2026.01.05") -> str:
    return (
        f'[Event "Test"]\n[White "{white}"]\n[Black "{black}"]\n'
        f'[Result "1-0"]\n[UTCDate "{date}"]\n[ECO "C50"]\n'
        f'[Opening "Italian Game"]\n\n{moves}\n'
    )


def move(**overrides) -> dict:
    base = {
        "ply": 1, "move_number": 1, "side": "white", "san": "Nxe5", "best_san": "d3",
        "eval_before": 0, "eval_after": -300, "cp_loss": 300, "win_prob_loss": 0.25,
        "quality": "blunder", "fen_before": HANG_FEN, "pv": [],
    }
    return {**base, **overrides}


def report(moves=None, white="alice", black="bob", acpl_white=60.0, acpl_black=20.0) -> dict:
    return {
        "white": white, "black": black, "result": "1-0",
        "eco": "C50", "opening": "Italian Game",
        "summary": {"acpl_white": acpl_white, "acpl_black": acpl_black},
        "moves": moves if moves is not None else [
            move(),
            move(ply=2, side="black", quality="good", fen_before=HANG_REPLY_FEN,
                 san="Nxe5", pv=["Nxe5"]),
        ],
    }


@pytest.fixture
def conn():
    connection = connect(":memory:")
    yield connection
    connection.close()


class TestResolveSide:
    def test_explicit_side_wins(self):
        assert resolve_side(report(), "alice", "black") == "black"

    def test_matches_the_players_own_name(self):
        assert resolve_side(report(), "alice") == "white"
        assert resolve_side(report(), "bob") == "black"

    def test_name_matching_ignores_case_and_padding(self):
        assert resolve_side(report(), "  ALICE ") == "white"

    def test_falls_back_to_the_worse_side_for_a_stranger(self):
        # Neither player is "carol", so coach whoever played worse (white, acpl 60).
        assert resolve_side(report(), "carol") == "white"


class TestSideCounts:
    def test_counts_only_the_named_side(self):
        moves = [
            move(ply=1, side="white", quality="blunder"),
            move(ply=2, side="black", quality="blunder"),
            move(ply=3, side="black", quality="mistake"),
        ]
        assert _side_counts(report(moves), "white") == {
            "blunder": 1, "mistake": 0, "inaccuracy": 0,
        }
        assert _side_counts(report(moves), "black") == {
            "blunder": 1, "mistake": 1, "inaccuracy": 0,
        }

    def test_good_moves_are_not_counted(self):
        moves = [move(ply=1, side="white", quality="best")]
        assert sum(_side_counts(report(moves), "white").values()) == 0


class TestIngest:
    def test_stores_a_game_and_its_motifs(self, conn):
        game_id = ingest_game(conn, pgn(), report(), "alice", depth=12)
        assert game_id is not None
        info = stats(conn, "alice")
        assert info["games"] == 1
        assert info["blunders"] == 1
        assert info["motif_tags"] == 1  # the hung knight

    def test_the_same_game_is_never_counted_twice(self, conn):
        assert ingest_game(conn, pgn(), report(), "alice") is not None
        assert ingest_game(conn, pgn(), report(), "alice") is None
        assert stats(conn, "alice")["games"] == 1

    def test_retagging_the_same_moves_from_a_different_export_is_still_one_game(self, conn):
        """Identity is the movetext, so re-downloading with different tags is a no-op."""
        ingest_game(conn, pgn(), report(), "alice")
        restaged = pgn(date="2026.02.09").replace('[Event "Test"]', '[Event "Rematch"]')
        assert ingest_game(conn, restaged, report(), "alice") is None
        assert stats(conn, "alice")["games"] == 1

    def test_different_games_both_land(self, conn):
        ingest_game(conn, pgn(), report(), "alice")
        ingest_game(conn, pgn(moves="1. d4 d5 2. c4 e6 1-0"), report(), "alice")
        assert stats(conn, "alice")["games"] == 2

    def test_already_stored_reports_membership(self, conn):
        assert not already_stored(conn, pgn())
        ingest_game(conn, pgn(), report(), "alice")
        assert already_stored(conn, pgn())

    def test_players_do_not_share_a_profile(self, conn):
        ingest_game(conn, pgn(), report(), "alice")
        assert stats(conn, "bob")["games"] == 0


class TestProfile:
    def test_empty_profile_says_so(self, conn):
        profile = build_profile(conn, "nobody")
        assert profile.is_empty
        assert "No games stored" in format_profile(profile)

    def test_a_single_occurrence_is_not_yet_a_pattern(self, conn):
        ingest_game(conn, pgn(), report(), "alice")
        profile = build_profile(conn, "alice")
        assert [m.motif for m in profile.motifs] == ["hangs_material"]
        assert not profile.motifs[0].is_pattern
        assert profile.motifs[0].status == "once_only"
        assert "| once_only" in format_profile(profile)

    def test_repeated_motif_becomes_a_pattern_with_a_count(self, conn):
        for i in range(MIN_OCCURRENCES_FOR_PATTERN):
            ingest_game(conn, pgn(moves=f"1. e4 e5 2. Nf3 Nc6 {i} 1-0"), report(), "alice")
        profile = build_profile(conn, "alice")
        stat = profile.motifs[0]
        assert stat.is_pattern
        assert stat.status == "recurring"
        assert stat.occurrences == MIN_OCCURRENCES_FOR_PATTERN
        assert "| recurring" in format_profile(profile)

    def test_average_cost_is_reported_not_a_summed_percentage(self, conn):
        """Summed win-probability runs past 100% and reads as a bug; the average doesn't."""
        for i in range(4):
            ingest_game(conn, pgn(moves=f"1. e4 e5 {i} 1-0"), report(), "alice")
        stat = build_profile(conn, "alice").motifs[0]
        assert stat.win_prob_lost == pytest.approx(1.0)  # 4 x 0.25 — over 100%
        assert stat.avg_win_prob_lost == pytest.approx(0.25)
        assert "| 25% |" in format_profile(build_profile(conn, "alice"))

    def test_window_limits_to_recent_games(self, conn):
        for i in range(5):
            ingest_game(conn, pgn(moves=f"1. e4 e5 {i} 1-0", date=f"2026.01.0{i + 1}"),
                        report(), "alice")
        assert build_profile(conn, "alice").games == 5
        assert build_profile(conn, "alice", last_n=2).games == 2

    def test_phase_breakdown_is_present(self, conn):
        ingest_game(conn, pgn(), report(), "alice")
        profile = build_profile(conn, "alice")
        assert [p.phase for p in profile.phases] == ["opening"]
        assert profile.phases[0].mistakes == 1

    def test_trend_needs_enough_games(self, conn):
        for i in range(MIN_GAMES_FOR_TREND - 1):
            ingest_game(conn, pgn(moves=f"1. e4 e5 {i} 1-0", date=f"2026.01.0{i + 1}"),
                        report(), "alice")
        assert build_profile(conn, "alice").trend is None

        ingest_game(conn, pgn(moves="1. d4 d5 1-0", date="2026.01.09"), report(), "alice")
        trend = build_profile(conn, "alice").trend
        assert trend is not None
        assert trend.earlier_games + trend.later_games == MIN_GAMES_FOR_TREND

    def test_opening_needs_repeat_visits_to_be_reported(self, conn):
        ingest_game(conn, pgn(), report(), "alice")
        assert build_profile(conn, "alice").openings == []
        ingest_game(conn, pgn(moves="1. e4 e5 2. Bc4 1-0"), report(), "alice")
        openings = build_profile(conn, "alice").openings
        assert [o.eco for o in openings] == ["C50"]
        assert openings[0].games == 2

    def test_untagged_mistakes_produce_no_pattern_table_at_all(self, conn):
        """A positional error tags no motif, and the profile must not imply otherwise.

        Absence is the signal: no `pattern` header means nothing was tagged, and the
        system prompt tells the model how to read that."""
        quiet = report(moves=[move(quality="inaccuracy", cp_loss=40, fen_before=HANG_FEN)])
        ingest_game(conn, pgn(), quiet, "alice")
        text = format_profile(build_profile(conn, "alice"))
        assert "pattern | occurrences" not in text
        assert "total_mistakes | 1" in text


class TestProfileIsSafeInsideTheFactsBlock:
    """The profile gets rendered into the coach's facts block, and the grounding checker
    treats that block as the set of moves the coach may cite. Anything move-like that
    leaks in from *past* games licenses a citation in *this* one."""

    def test_a_rendered_profile_names_no_moves(self, conn):
        from eval.grounding import extract_moves

        for i in range(3):
            ingest_game(conn, pgn(moves=f"1. e4 e5 {i} 1-0"), report(), "alice")
        assert extract_moves(format_profile(build_profile(conn, "alice"))) == set()

    def test_an_opening_name_containing_notation_falls_back_to_its_eco(self, conn):
        from eval.grounding import extract_moves

        hostile = report()
        for i in range(2):
            game_pgn = pgn(moves=f"1. Nf3 d5 {i} 1-0").replace(
                '[Opening "Italian Game"]', '[Opening "King\'s Indian Attack, with e6"]'
            )
            ingest_game(conn, game_pgn, {**hostile, "opening": "King's Indian Attack, with e6"},
                        "alice")
        profile = build_profile(conn, "alice")
        assert profile.openings and profile.openings[0].name == "C50"
        assert extract_moves(format_profile(profile)) == set()
