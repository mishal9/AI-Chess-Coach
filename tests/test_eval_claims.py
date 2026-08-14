"""Tests for the deterministic claim checker.

No engine, no model, no network. The cases are drawn from real coaching text — both the
failures the checker must catch and the correct phrasings that earlier drafts wrongly
flagged (see docs/experiments/2026-08-11-grounding-metric-audit.md §3).
"""

from __future__ import annotations

import pytest

from eval import claims

FACTS = (
    "Your most costly moves (worst first):\n"
    "- 12...Re8?! (inaccuracy): the engine preferred Nh5; cost about 10% win probability "
    "(cp loss 119).\n"
    "- 21...Nd2? (mistake): the engine preferred g3; cost about 13% win probability "
    "(cp loss 140).\n"
)


def _report(moves: list[tuple[str, str]]) -> dict:
    return {"moves": [{"side": side, "san": san} for side, san in moves]}


# --- parsing the roles out of the facts block -----------------------------------

def test_parse_roles_splits_played_from_preferred():
    played, preferred = claims.parse_roles(FACTS)
    assert played == {"Re8", "Nd2"}
    assert preferred == {"Nh5", "g3"}


def test_parse_roles_drops_a_move_that_holds_both_roles():
    # It cannot arbitrate an inversion, so it must not be used to claim one.
    facts = (
        "- 10.Nf3?! (inaccuracy): the engine preferred Bc4; cost 5%.\n"
        "- 14.Bc4? (mistake): the engine preferred Nf3; cost 20%.\n"
    )
    assert claims.parse_roles(facts) == (set(), set())


def test_parse_roles_ignores_a_facts_block_with_no_mistakes():
    assert claims.parse_roles("Across the whole game: 0 blunders, 0 mistakes.") == (
        set(),
        set(),
    )


# --- role inversion -------------------------------------------------------------

@pytest.mark.parametrize(
    "coaching, move",
    [
        ("When you played Nf3 or g3 instead, it slipped.", "g3"),   # via coordination
        ("You chose a passive rook move (Nh5) there.", "Nh5"),      # via appositive
        ("The engine preferred Re8, which keeps the tension.", "Re8"),
    ],
)
def test_role_inversion_is_flagged(coaching, move):
    result = claims.check_roles(coaching, FACTS)
    assert [v.move for v in result.violations] == [move]
    assert result.violations[0].kind == "role_inversion"
    assert not result.ok


def test_correct_attribution_is_clean():
    result = claims.check_roles("You played Re8, but the engine preferred Nh5.", FACTS)
    assert result.checked == 2
    assert result.ok
    assert result.score == 1.0


def test_a_later_move_does_not_steal_an_earlier_cue():
    """The trap a windowed search falls into.

    "preferred" governs Nh5; Re8 must be left ungoverned rather than read as
    engine-preferred, which would invert a perfectly correct sentence.
    """
    result = claims.check_roles("The engine preferred Nh5 instead of Re8.", FACTS)
    assert result.ok


def test_a_cue_does_not_reach_across_a_clause():
    # "Nh5" belongs to "was stronger", not to "chose".
    result = claims.check_roles(
        "You chose a capture when the quiet Nh5 was stronger.", FACTS
    )
    assert result.checked == 0
    assert result.ok


@pytest.mark.parametrize(
    "coaching",
    [
        "The engine wanted you to play Nh5.",          # recommendation, not a claim
        "You left value on the board by not playing Nh5.",  # negated
        "When you have the chance to play Nh5, take it.",   # hypothetical
        "In this structure you play Nh5 to gain space.",    # present tense: generic advice
    ],
)
def test_recommendations_and_negations_are_not_assertions(coaching):
    assert claims.check_roles(coaching, FACTS).ok


def test_moves_outside_the_facts_are_left_to_grounding():
    # Bg5 has no role in the facts, so this module must not double-count it.
    result = claims.check_roles("You played Bg5 early.", FACTS)
    assert result.checked == 0
    assert result.ok


# --- invented castling ----------------------------------------------------------

def test_castling_claimed_by_a_player_who_never_castled():
    report = _report([("white", "e4"), ("white", "Nf3"), ("black", "O-O")])
    result = claims.check_castling("You castled on the kingside early.", report, "white")
    assert [v.kind for v in result.violations] == ["invented_castling"]


def test_castling_claim_is_fine_when_the_player_did_castle():
    report = _report([("white", "e4"), ("white", "O-O")])
    assert claims.check_castling("You castled early.", report, "white").ok


def test_mentioning_castling_is_not_claiming_it():
    """The false positive that an earlier draft produced on a factual=5 game.

    Both of these are correct English about a player who never castled: the first says so
    explicitly, the second is advice.
    """
    report = _report([("white", "d4"), ("white", "Qe2")])
    for text in (
        "You played d4 instead of castling (O-O), which was the critical moment.",
        "Two things to work on: 1. Castling first when the position allows it.",
    ):
        assert claims.check_castling(text, report, "white").ok


def test_hypothetical_castling_is_not_a_claim():
    report = _report([("white", "d4")])
    result = claims.check_castling(
        "Before pushing pawns, ask whether you've castled and developed.", report, "white"
    )
    assert result.ok


# --- aggregation ----------------------------------------------------------------

def test_score_is_the_fraction_of_correct_assertions():
    # One right ("you played Re8"), one wrong ("you played g3").
    result = claims.check_roles("You played Re8. You played g3 as well.", FACTS)
    assert result.checked == 2
    assert len(result.violations) == 1
    assert result.score == 0.5


def test_no_testable_assertion_scores_clean():
    result = claims.check_roles("Focus on king safety and slow down.", FACTS)
    assert result.checked == 0
    assert result.score == 1.0
    assert result.ok


def test_to_dict_is_serialisable():
    result = claims.check_roles("When you played g3, it slipped.", FACTS)
    payload = result.to_dict()
    assert payload["score"] == 0.0
    assert payload["ok"] is False
    assert payload["violations"][0]["move"] == "g3"
    assert payload["violations"][0]["actual"] == "engine-preferred"
