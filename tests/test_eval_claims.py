"""Tests for the deterministic claim checker.

No engine, no model, no network. The cases are drawn from real coaching text — both the
failures the checker must catch and the correct phrasings that earlier drafts wrongly
flagged (see docs/experiments/2026-08-11-grounding-metric-audit.md §3).
"""

from __future__ import annotations

import chess
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


# --- invented placement ---------------------------------------------------------
# The facts block carries no piece placement at all, so any "piece on square" claim is
# invention unless the game bears it out. This is what the bare-square parser used to
# catch by accident (audit §5); once #41 fixed that false positive, nothing watched it.

def _game_report(sans: list[str]) -> dict:
    """Build a report with real ``fen_before`` values by replaying ``sans``."""
    board = chess.Board()
    moves = []
    for san in sans:
        moves.append({
            "san": san,
            "side": "white" if board.turn == chess.WHITE else "black",
            "fen_before": board.fen(),
            "quality": "good",
            "best_san": san,
            "move_number": board.fullmove_number,
            "cp_loss": 0,
            "win_prob_loss": 0.0,
        })
        board.push_san(san)
    return {"moves": moves}


OPENING = _game_report(["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5"])


def test_occupancy_includes_the_position_after_the_final_move():
    # Bc5 is the last move and no fen_before shows it, so only the final-position push
    # can put a black bishop on c5.
    occupancy = claims.occupied_squares(OPENING)
    assert (chess.BLACK, "b", "c5") in occupancy
    assert (chess.WHITE, "n", "f3") in occupancy


def test_invented_placement_is_flagged():
    result = claims.check_board_state(
        "You moved your rook from b7 to b8, which achieved little.", OPENING, "black"
    )
    assert [v.kind for v in result.violations] == ["invented_placement"]
    assert "b7" in result.violations[0].claimed


def test_a_true_placement_claim_passes():
    result = claims.check_board_state(
        "Your knight on c6 was well placed.", OPENING, "black"
    )
    assert result.checked == 1
    assert result.ok


def test_placement_without_a_possessive_accepts_either_colour():
    # "the knight on f3" is White's; a claim that vague must not be called invented.
    assert claims.check_board_state("The knight on f3 was active.", OPENING, "black").ok


def test_advice_about_where_a_piece_belongs_is_not_a_claim():
    """The recommendation trap, in its board-state form.

    None of these asserts where a piece *was*, so none can be false about it.
    """
    for text in (
        "Knights belong on f5 in this structure.",
        "You should put your rook on d7 next time.",
        "It would be better to bring your queen to h4.",
    ):
        assert claims.check_board_state(text, OPENING, "white").ok


def test_no_moves_means_nothing_to_check():
    assert claims.check_board_state("Your rook on b7 was passive.", {"moves": []}, "white").ok


def test_full_check_merges_all_three_families():
    report = dict(
        OPENING,
        summary={"acpl_white": 20.0, "acpl_black": 30.0, "blunders": 0,
                 "mistakes": 0, "inaccuracies": 0, "worst_move": None},
        white="Alice", black="Bob", result="1-0", opening="Italian Game", eco="C50",
    )
    result = claims.check_claims_from_report(
        "You moved your rook from b7 to b8. You castled early.", report, "black"
    )
    kinds = {v.kind for v in result.violations}
    assert kinds == {"invented_placement", "invented_castling"}


# --- v2: false positives found by hand-auditing DeepSeek-V4 Pro coaching -----------

@pytest.mark.parametrize("text", [
    # hypothetical about the engine's alternative (inaccuracies #2)
    "Small differences matter — the queen on e2 would have been more harmonious.",
    # a target, not a placement (two_mistakes #10)
    "10.Ng5 looks active, pointing the knight at f7 and h7.",
    # an -ing advice verb (two_mistakes #13)
    "Completing your development (like getting the bishop to e7) matters more.",
    # conditional, general advice (multi_blunder #5)
    "When your opponent has a pawn on d5 or e5, always ask whether you can capture it.",
])
def test_hypotheticals_targets_and_general_advice_are_not_placement_claims(text):
    assert claims.check_board_state(text, OPENING, "white").ok


@pytest.mark.parametrize("text, square", [
    # the real errors from the same audit: stated as fact, so still flagged
    ("The engine preferred Bxc5, taking the rook on c5.", "c5"),        # slow_loss #16 shape
    ("You retreated instead of keeping calm; your bishop on h6 was lost.", "h6"),
    ("You moved your rook from b7 to b8, which achieved little.", "b7"),
    # "keeping" presupposes the piece was there (slow_loss #14 shape)
    ("The engine preferred keeping the queen on h6.", "h6"),
])
def test_placement_stated_as_fact_is_still_checked(text, square):
    result = claims.check_board_state(text, OPENING, "black")
    assert [v.kind for v in result.violations] == ["invented_placement"]
    assert square in result.violations[0].claimed


def test_a_move_attributed_to_the_opponent_is_not_checked_against_the_coached_side():
    # slow_loss #12: White really played 7.Ngxe4; Black's engine-preferred move was also
    # a knight capture on e4, so the SAN collides. The facts only assign Black's roles.
    facts = (
        "You are coaching the BLACK player (b); the opponent is a.\n"
        "- 7...Bg7?! (inaccuracy): the engine preferred Nxe4; cost about 8% win probability.\n"
    )
    assert claims.check_roles("After White played 7.Nxe4, you developed.", facts).ok
    # ...while the same move attributed to the coached player is still an inversion.
    flagged = claims.check_roles("You played Nxe4 here, which was a mistake.", facts)
    assert [v.kind for v in flagged.violations] == ["role_inversion"]


def test_metric_version_is_2():
    assert claims.METRIC_VERSION == 2


WORSE_FACTS = ("- Engine evaluation: with the preferred move, you are worse by about 3.1 pawns; "
               "after your move, you are worse by about 8.9 pawns.")
OLD_WORSE_FACTS = ("- Engine evaluation (in pawns; + favours you): with the preferred move "
                   "-1.2, after your move -3.9.")


@pytest.mark.parametrize("text", [
    # the 8 Oct spot-check's confirmed errors
    "You didn't need to force anything — you were already better, and g5 keeps it.",
    "The engine says that would have left you clearly better.",
    "You keep a solid, slightly better position where White has no easy targets.",
    "Your position remains clearly better because your pieces work together.",
    "The evaluation swings from a clearly winning position for you to a forced mate.",
])
def test_calling_a_worse_student_better_is_flagged(text):
    for facts in (WORSE_FACTS, OLD_WORSE_FACTS):
        result = claims.check_eval_sign(text, facts)
        assert [v.kind for v in result.violations] == ["eval_sign"], (text, facts)


@pytest.mark.parametrize("text", [
    "Ask whether the reply leaves you better or worse.",            # a question, not a claim
    "That capture looks natural: you're winning a central pawn.",   # material, not standing
    "When you're winning, prioritize king safety.",                 # advice
    "You were already worse, and this made it much harder.",        # true
    "You'd be better off keeping the rook.",                        # idiom
])
def test_other_uses_of_better_and_winning_pass(text):
    assert claims.check_eval_sign(text, WORSE_FACTS).ok


def test_better_is_fine_when_the_evaluation_agrees_and_worse_is_checked_too():
    better = ("- Engine evaluation: with the preferred move, you are better by about 2.5 "
              "pawns; after your move, you are better by about 1.2 pawns.")
    assert claims.check_eval_sign("You were clearly better here.", better).ok
    flagged = claims.check_eval_sign("After that move you were losing.", better)
    assert [v.kind for v in flagged.violations] == ["eval_sign"]
    # material, not standing (8 Oct v3 run, #1279: the check's one false flag)
    assert claims.check_eval_sign("Suddenly you're losing your rook in the corner.", better).ok
    level = ("- Engine evaluation: with the preferred move, the position is about level; "
             "after your move, you are worse by about 0.9 pawns.")
    assert claims.check_eval_sign("You were slightly better.", level).ok  # under a pawn


def test_facts_without_an_evaluation_check_nothing():
    result = claims.check_eval_sign("You were already better.", FACTS)
    assert result.ok and result.checked == 0
