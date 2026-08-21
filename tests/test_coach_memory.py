"""Feeding a player's history into the coaching prompt.

The load-bearing test here is the *negative* one: with no profile, the facts block must be
byte-identical to the pre-memory version. Every committed eval report was produced against
that exact text, and a stray blank line would silently make them incomparable.
"""

from __future__ import annotations

import argparse

import pytest

from coach import coach, prompts
from memory.store import connect, ingest_game
from tests.test_memory_store import pgn
from tests.test_memory_store import report as _store_report


def report(**overrides) -> dict:
    """A report dict complete enough for the *coaching* path.

    The store fixture only needs per-side ACPL; the facts block also reads the whole-game
    quality counts, so they are filled in here rather than widened over there.
    """
    base = _store_report(**overrides)
    base["summary"] = {
        **base["summary"],
        "blunders": 1,
        "mistakes": 0,
        "inaccuracies": 0,
        "worst_move": None,
    }
    return base

PROFILE = (
    "games_analyzed | 9\n"
    "total_mistakes | 20\n"
    "average_centipawn_loss | 50.0\n\n"
    "pattern | occurrences | games | avg_cost | status\n"
    "leaving material hanging | 4 | 3 | 20% | recurring"
)


def args(**overrides) -> argparse.Namespace:
    base = {
        "user": None, "db": None, "last": None, "pgn": None, "from_json": None,
        "game_index": 0, "depth": 12, "side": None, "remember": False,
    }
    return argparse.Namespace(**{**base, **overrides})


class TestFactsBlockCompatibility:
    def test_no_profile_is_identical_to_omitting_the_argument(self):
        without = prompts.format_report_facts(report(), "white")
        explicit_none = prompts.format_report_facts(report(), "white", 6, None)
        assert without == explicit_none

    def test_no_profile_adds_no_history_section(self):
        assert "PLAYER HISTORY" not in prompts.format_report_facts(report(), "white")

    def test_empty_profile_string_is_treated_as_no_history(self):
        """An empty section would invite the model to fill the silence."""
        assert "PLAYER HISTORY" not in prompts.format_report_facts(report(), "white", 6, "")

    def test_profile_is_appended_inside_the_facts_block(self):
        facts = prompts.format_report_facts(report(), "white", 6, PROFILE)
        assert "PLAYER HISTORY" in facts
        assert "leaving material hanging | 4 | 3 | 20% | recurring" in facts
        # Still one block — eval.grounding rebuilds this whole string.
        assert facts.startswith("Game: White")


class TestBuildMessages:
    def test_profile_reaches_the_user_turn(self):
        messages = prompts.build_messages(report(), "white", 6, PROFILE)
        assert "PLAYER HISTORY" in messages[-1]["content"]

    def test_system_prompt_carries_the_interpretation_rules(self):
        """The renderer emits statuses; the prompt is where they get meaning."""
        system = prompts.SYSTEM_PROMPT
        assert "PLAYER HISTORY" in system
        assert "never inflate" in system.lower()
        # Every status the renderer can emit must be explained here.
        for status in ("recurring", "once_only", "improving", "declining", "unclear"):
            assert status in system, f"system prompt never explains {status!r}"

    def test_history_section_is_marked_as_holding_no_moves(self):
        facts = prompts.format_report_facts(report(), "white", 6, PROFILE)
        assert "no moves" in facts
        assert "It contains NO moves" in prompts.SYSTEM_PROMPT


class TestLoadProfile:
    def test_no_user_means_no_history(self):
        assert coach.load_profile(args()) is None

    def test_unknown_player_gets_no_history_rather_than_an_empty_one(self, tmp_path):
        db = tmp_path / "m.db"
        connect(db).close()
        assert coach.load_profile(args(user="nobody", db=str(db))) is None

    def test_known_player_gets_their_profile(self, tmp_path):
        db = tmp_path / "m.db"
        conn = connect(db)
        ingest_game(conn, pgn(), report(), "alice")
        conn.close()
        profile = coach.load_profile(args(user="alice", db=str(db)))
        assert profile is not None
        assert "games_analyzed | 1" in profile


class TestRemember:
    def test_stores_the_game_once(self, tmp_path, capsys):
        db = tmp_path / "m.db"
        connect(db).close()
        pgn_path = tmp_path / "g.pgn"
        pgn_path.write_text(pgn(), encoding="utf-8")

        options = args(user="alice", db=str(db), pgn=str(pgn_path))
        coach.remember(options, report(), "white")
        assert "Remembered" in capsys.readouterr().err

        coach.remember(options, report(), "white")
        assert "not counted twice" in capsys.readouterr().err

    def test_needs_a_user(self, tmp_path, capsys):
        coach.remember(args(pgn="x.pgn"), report(), "white")
        assert "needs --user" in capsys.readouterr().err

    def test_a_saved_json_report_cannot_be_remembered(self, capsys):
        """Movetext is the dedup key, and a JSON report has none."""
        coach.remember(args(user="alice", from_json="r.json"), report(), "white")
        assert "needs the PGN" in capsys.readouterr().err


class TestGroundingLicenceIsUnchanged:
    def test_adding_history_does_not_widen_the_set_of_citable_moves(self):
        from eval.grounding import extract_moves

        plain = extract_moves(prompts.format_report_facts(report(), "white"))
        with_history = extract_moves(
            prompts.format_report_facts(report(), "white", 6, PROFILE)
        )
        assert plain == with_history
