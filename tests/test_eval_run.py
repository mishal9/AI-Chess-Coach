"""Tests for the baseline eval runner.

The coach and judge are injected as fakes, so the case-evaluation, aggregation, report,
and spend-guard logic run with no Stockfish, Ollama, or API key. A fixture-integrity test
confirms every held-out PGN actually parses (python-chess only).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from eval import run
from eval.rubric import RubricScore
from tests.test_coach import SAMPLE_REPORT

_SCORES = {
    "factual_correctness": 4, "clarity": 5, "actionability": 3, "identifies_key_mistake": 4,
}


def _fake_judge(coaching, report, coached_side):
    return RubricScore.from_judge_json(_SCORES)


# --- held-out set integrity --------------------------------------------------------

def test_manifest_loads_and_pgns_parse():
    from engine.pgn import load_game

    cases = run.load_cases()
    assert len(cases) >= 5  # a real, varied held-out set
    names = {c.pgn.name for c in cases}
    assert {"clean_draw.pgn", "slow_loss.pgn", "multi_blunder.pgn"} <= names
    for case in cases:
        assert case.coached_side in ("white", "black")
        assert case.pgn.exists()
        assert load_game(case.pgn, case.game_index) is not None  # parses cleanly


# --- evaluate_case -----------------------------------------------------------------

def test_evaluate_case_scores_grounding_and_rubric():
    case = run.EvalCase(pgn=Path("x.pgn"), game_index=0, coached_side="black")
    coaching = "The blunder was 17...Nxd4; the engine preferred Qe7."
    record = run.evaluate_case(case, SAMPLE_REPORT, lambda r, s: coaching, _fake_judge)

    assert record["coaching"] == coaching
    assert record["grounding"]["grounded"] is True
    assert record["identifies_worst_move"] is True  # cites the worst move (Nxd4)
    assert record["rubric"]["overall"] == 4.0


def test_evaluate_case_flags_hallucination():
    case = run.EvalCase(pgn=Path("x.pgn"), game_index=0, coached_side="black")
    record = run.evaluate_case(
        case, SAMPLE_REPORT, lambda r, s: "You blundered with Nf7.", _fake_judge
    )
    assert record["grounding"]["grounded"] is False
    assert record["grounding"]["hallucinated"] == ["Nf7"]


def test_evaluate_case_without_judge_omits_rubric():
    case = run.EvalCase(pgn=Path("x.pgn"), game_index=0, coached_side="black")
    record = run.evaluate_case(case, SAMPLE_REPORT, lambda r, s: "Nxd4 was bad.", None)
    assert "rubric" not in record


# --- aggregate ---------------------------------------------------------------------

def _record(gscore, grounded, worst, overall, scores):
    return {
        "grounding": {"score": gscore, "grounded": grounded, "hallucinated": []},
        "identifies_worst_move": worst,
        "rubric": {"scores": scores, "overall": overall, "rationale": ""},
    }


def test_aggregate_computes_means():
    records = [
        _record(1.0, True, True, 4.0,
                {"factual_correctness": 4, "clarity": 5, "actionability": 3, "identifies_key_mistake": 4}),
        _record(0.0, False, False, 2.0,
                {"factual_correctness": 2, "clarity": 3, "actionability": 1, "identifies_key_mistake": 2}),
    ]
    agg = run.aggregate(records)
    assert agg["games"] == 2
    assert agg["grounding_mean"] == 0.5
    assert agg["grounded_rate"] == 0.5
    assert agg["worst_move_identified_rate"] == 0.5
    assert agg["rubric_axis_means"]["clarity"] == 4.0
    assert agg["rubric_overall_mean"] == 3.0


def test_aggregate_without_rubric_skips_rubric_keys():
    records = [
        {"grounding": {"score": 1.0, "grounded": True, "hallucinated": []},
         "identifies_worst_move": True},
    ]
    agg = run.aggregate(records)
    assert agg["grounding_mean"] == 1.0
    assert "rubric_overall_mean" not in agg


# --- spend guard -------------------------------------------------------------------

def test_spend_guard_refuses_before_spending(capsys):
    # More cases than the cap -> exit 1 before any analysis or judge call.
    rc = run.main(["--max-judge-calls", "0"])
    assert rc == 1
    assert "Refusing to start" in capsys.readouterr().err


# --- --resume / incremental partial writes ------------------------------------------

def _rec(pgn="a.pgn", side="white", score=1.0, game_index=0):
    return {"pgn": pgn, "game_index": game_index, "coached_side": side, "note": "",
            "coaching": "text",
            "grounding": {"score": score, "grounded": True, "hallucinated": []},
            "identifies_worst_move": True}


def test_partial_roundtrips_and_strips_provenance(tmp_path):
    out = tmp_path / "r.json"
    run.append_partial(out, _rec(), "coach-a", "judge-a")
    done = run.load_partial(out, "coach-a", "judge-a")
    assert list(done) == [("a.pgn", 0, "white")]
    assert "_coach" not in done[("a.pgn", 0, "white")]  # provenance never reaches the report


def test_partial_distinguishes_games_within_one_pgn(tmp_path):
    """Bucket files hold several games; keyed on the name alone, finishing one would mark
    its file-mates done and resume would silently skip them."""
    out = tmp_path / "r.json"
    run.append_partial(out, _rec(game_index=0), "coach-a", "judge-a")
    run.append_partial(out, _rec(game_index=3), "coach-a", "judge-a")
    done = run.load_partial(out, "coach-a", "judge-a")
    assert set(done) == {("a.pgn", 0, "white"), ("a.pgn", 3, "white")}


def test_resume_refuses_a_partial_from_another_model(tmp_path):
    out = tmp_path / "r.json"
    run.append_partial(out, _rec(), "coach-a", "judge-a")
    with pytest.raises(SystemExit, match="Refusing to resume"):
        run.load_partial(out, "coach-b", "judge-a")


def test_load_partial_absent_is_empty(tmp_path):
    assert run.load_partial(tmp_path / "nope.json", "c", "j") == {}
