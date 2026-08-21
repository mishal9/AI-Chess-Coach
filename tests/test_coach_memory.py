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
    "Across 9 analyzed game(s), alice made 20 flagged mistakes "
    "(average centipawn loss 50.0).\n\n"
    "Recurring patterns (most costly first):\n"
    "- leaving material hanging: 4 times across 3 game(s), costing about 20% "
    "win probability each time."
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
        assert "YOUR HISTORY" not in prompts.format_report_facts(report(), "white")

    def test_empty_profile_string_is_treated_as_no_history(self):
        """An empty section would invite the model to fill the silence."""
        assert "YOUR HISTORY" not in prompts.format_report_facts(report(), "white", 6, "")

    def test_profile_is_appended_inside_the_facts_block(self):
        facts = prompts.format_report_facts(report(), "white", 6, PROFILE)
        assert "YOUR HISTORY" in facts
        assert "leaving material hanging: 4 times" in facts
        # Still one block — eval.grounding rebuilds this whole string.
        assert facts.startswith("Game: White")


class TestBuildMessages:
    def test_profile_reaches_the_user_turn(self):
        messages = prompts.build_messages(report(), "white", 6, PROFILE)
        assert "YOUR HISTORY" in messages[-1]["content"]

    def test_system_prompt_constrains_history_use(self):
        system = prompts.SYSTEM_PROMPT
        assert "YOUR HISTORY" in system
        assert "never turn" in system.lower() or "never inflate" in system.lower()

    def test_history_section_is_told_it_holds_no_citable_moves(self):
        facts = prompts.format_report_facts(report(), "white", 6, PROFILE)
        assert "do not cite moves from here" in facts


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
        assert "alice" in profile


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
