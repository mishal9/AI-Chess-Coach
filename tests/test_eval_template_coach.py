"""The template coach is the no-LLM control arm. It must say only what the facts say."""

from __future__ import annotations

import copy

from eval import claims, grounding, run, template_coach
from tests.test_coach import SAMPLE_REPORT


def _no_mistakes(acpl: float) -> dict:
    report = copy.deepcopy(SAMPLE_REPORT)
    report["moves"] = []
    report["summary"]["acpl_black"] = acpl
    return report


def test_names_the_worst_move_and_its_replacement():
    text = template_coach.template_coaching(SAMPLE_REPORT, "black")
    assert "17...Nxd4??" in text
    assert "Qe7" in text
    assert "62%" in text
    assert text.index("17...Nxd4") < text.index("12...h6")  # worst first


def test_omits_the_opponents_mistakes():
    assert "a3" not in template_coach.template_coaching(SAMPLE_REPORT, "black")


def test_is_deterministic():
    a = template_coach.template_coaching(SAMPLE_REPORT, "black")
    assert a == template_coach.template_coaching(copy.deepcopy(SAMPLE_REPORT), "black")


def test_fully_grounded_and_claim_clean():
    for report, side in [(SAMPLE_REPORT, "black"), (SAMPLE_REPORT, "white"),
                         (_no_mistakes(10.0), "black"), (_no_mistakes(90.0), "black")]:
        text = template_coach.template_coaching(report, side)
        g = grounding.grounding_from_report(text, report, side)
        assert g.grounded and not g.hallucinated, (side, text)
        assert claims.check_claims_from_report(text, report, side).ok, (side, text)


def test_no_flagged_moves_cites_no_moves():
    for acpl in (10.0, 90.0):
        text = template_coach.template_coaching(_no_mistakes(acpl), "black")
        assert not grounding.grounding_from_report(text, _no_mistakes(acpl), "black").cited


def test_clean_and_gradual_loss_are_told_apart():
    assert "clean game" in template_coach.template_coaching(_no_mistakes(10.0), "black")
    assert "gradually" in template_coach.template_coaching(_no_mistakes(90.0), "black")


def test_no_alternative_clause_when_the_engine_agreed():
    report = copy.deepcopy(SAMPLE_REPORT)
    report["moves"][0]["best_san"] = report["moves"][0]["san"]
    assert "engine preferred" not in template_coach.template_coaching(report, "black").split("\n\n")[1]


def test_run_selects_it_by_name_and_needs_no_ollama():
    coach_fn = run.make_coach_fn(template_coach.NAME, temperature=0.0)
    assert coach_fn(SAMPLE_REPORT, "black") == template_coach.template_coaching(
        SAMPLE_REPORT, "black")
