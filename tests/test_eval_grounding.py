"""Tests for the deterministic grounding metric.

No engine and no model required — these run anywhere, including CI.
"""

from __future__ import annotations

from coach import prompts
from eval import grounding
from tests.test_coach import SAMPLE_REPORT


def test_extract_moves_covers_san_shapes():
    text = "You played 17...Nxd4?? instead of Qe7. Later Be7, then O-O, e4, exd5 and Qxf7#."
    moves = grounding.extract_moves(text)
    assert {"Nxd4", "Qe7", "Be7", "O-O", "e4", "exd5", "Qxf7"} <= moves


def test_extract_moves_ignores_non_moves():
    # Prose, ECO codes, capitalized words and bare numbers must not read as moves.
    text = "In the C41 Philidor Defense, Black lost 88% with a Bishop. Great effort!"
    assert grounding.extract_moves(text) == set()


def test_extract_moves_normalizes_castling_and_marks():
    assert grounding.extract_moves("0-0-0 and Qh7+!") == {"O-O-O", "Qh7"}


def test_facts_allowed_set_is_exactly_the_shown_moves():
    facts = prompts.format_report_facts(SAMPLE_REPORT, "black")
    assert grounding.extract_moves(facts) == {"Nxd4", "Qe7", "h6", "Be7"}


def test_grounded_coaching_scores_clean():
    facts = prompts.format_report_facts(SAMPLE_REPORT, "black")
    coaching = "Your worst move was 17...Nxd4; Qe7 was safer. Also 12...h6 — prefer Be7."
    result = grounding.score_grounding(coaching, facts)
    assert result.grounded
    assert result.hallucinated == set()
    assert result.score == 1.0


def test_hallucinated_move_is_flagged():
    facts = prompts.format_report_facts(SAMPLE_REPORT, "black")
    # Nf7 and Bg5 never appeared in the facts -> fabricated.
    coaching = "You should have avoided Nf7 and played Bg5 to hold the center."
    result = grounding.score_grounding(coaching, facts)
    assert not result.grounded
    assert result.hallucinated == {"Nf7", "Bg5"}
    assert result.score == 0.0


def test_grounding_from_report_partial_score():
    # One real move (Nxd4) + one invented (Nf7) -> half the citations are grounded.
    coaching = "The key error was 17...Nxd4; also Nf7 was loose."
    result = grounding.grounding_from_report(coaching, SAMPLE_REPORT, "black")
    assert result.hallucinated == {"Nf7"}
    assert result.score == 0.5


def test_sparse_facts_flags_all_invention():
    # The Opera-Game situation: coached side has no flagged move, so the facts carry no
    # moves at all. Any move the coach cites is therefore a hallucination.
    report = {
        **SAMPLE_REPORT,
        "moves": [],
        "summary": {
            **SAMPLE_REPORT["summary"],
            "acpl_white": 22.9,
            "acpl_black": 79.8,
        },
    }
    coaching = "On move 16 you blundered with Nf7 and missed the tactic Qe2."
    result = grounding.grounding_from_report(coaching, report)  # auto-picks Black
    assert result.allowed == set()
    assert result.hallucinated == {"Nf7", "Qe2"}
    assert not result.grounded
    assert result.score == 0.0


def test_no_moves_cited_is_vacuously_grounded():
    facts = prompts.format_report_facts(SAMPLE_REPORT, "black")
    result = grounding.score_grounding("Focus on king safety and slow down.", facts)
    assert result.grounded
    assert result.score == 1.0


def test_identifies_worst_move():
    assert grounding.identifies_worst_move("The blunder was 17...Nxd4.", SAMPLE_REPORT)
    assert not grounding.identifies_worst_move("You played well overall.", SAMPLE_REPORT)


def test_identifies_worst_move_false_when_none():
    report = {"summary": {"worst_move": None}}
    assert not grounding.identifies_worst_move("Nxd4 was bad.", report)


# --- bare-square disambiguation -------------------------------------------------
# Pawn moves and square references share a shape ("e4"), and reading every square
# reference as a claimed pawn move was the metric's dominant error: 84-94% of every
# hallucination it flagged, and 64 of the 64 rows its gate dropped from the v2
# distillation set. See docs/experiments/2026-08-11-grounding-metric-audit.md.


def test_square_after_location_preposition_is_not_a_move():
    assert grounding.extract_moves("Your rook on b7 is doing nothing.") == set()
    assert grounding.extract_moves("You moved your rook from b7 to b8.") == set()


def test_square_qualifying_a_noun_is_not_a_move():
    assert grounding.extract_moves("Fight for control of the e5 square.") == set()
    assert grounding.extract_moves("The b7 rook was passive.") == set()


def test_coordinated_square_inherits_the_preposition():
    # "f6" is governed by the same "on" as "f3" — both are places, not moves.
    assert grounding.extract_moves("Knights belong on f3 and f6, usually.") == set()


def test_notation_beats_locational_phrasing():
    # A move number or annotation is decisive even after a locational preposition.
    assert grounding.extract_moves("The costly moment came on 12...e5?!") == {"e5"}
    assert grounding.extract_moves("Then e4?? threw the game away.") == {"e4"}
    assert grounding.extract_moves("He met it with d5+.") == {"d5"}


def test_bare_square_used_as_a_move_is_still_counted():
    # Coaching cites moves in many shapes; none of these is a location.
    assert grounding.extract_moves("g4 preserved the initiative.") == {"g4"}
    assert grounding.extract_moves("d3 is passive; c3 keeps your pieces working.") == {
        "d3",
        "c3",
    }
    assert grounding.extract_moves("The engine preferred **c5**, a better try.") == {"c5"}


def test_invented_pawn_move_is_still_flagged():
    facts = prompts.format_report_facts(SAMPLE_REPORT, "black")
    result = grounding.score_grounding("You should have played d5 instead.", facts)
    assert result.hallucinated == {"d5"}
    assert not result.grounded


def test_prose_restatement_of_a_cited_move_scores_clean():
    """The regression this fix exists for.

    The coach names the move correctly ("12...Rb8") and then restates it in English.
    The old parser read "b7" and "b8" as two phantom pawn moves and scored 0.71.
    """
    facts = (
        "- 12...Rb8?! (inaccuracy): the engine preferred Bc6; "
        "cost about 10% win probability (cp loss 119)."
    )
    coaching = (
        "The most costly moment came on **12...Rb8**. You moved your rook from b7 "
        "to b8, but the engine preferred **Bc6**, a quiet developing move."
    )
    result = grounding.score_grounding(coaching, facts)
    assert result.cited == {"Rb8", "Bc6"}
    assert result.grounded
    assert result.score == 1.0
