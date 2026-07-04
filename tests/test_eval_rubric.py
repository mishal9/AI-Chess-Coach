"""Tests for the rubric data model and the LLM-as-judge parsing/orchestration.

Pure-logic and mocked-transport tests run everywhere; one live smoke test calls the
local judge model and auto-skips when it isn't available.
"""

from __future__ import annotations

import pytest

from eval import judge, rubric
from tests.test_coach import SAMPLE_REPORT, requires_model

VALID_VERDICT = (
    '{"factual_correctness": 4, "clarity": 5, "actionability": 3, '
    '"identifies_key_mistake": 4, "rationale": "solid, grounded advice"}'
)


# --- rubric ------------------------------------------------------------------------

def test_rubric_from_judge_json_valid():
    score = rubric.RubricScore.from_judge_json(
        {"factual_correctness": 4, "clarity": 5, "actionability": 3,
         "identifies_key_mistake": 4, "rationale": "ok"}
    )
    assert score.scores["clarity"] == 5
    assert score.overall == 4.0
    assert score.rationale == "ok"


def test_rubric_clamps_out_of_range():
    score = rubric.RubricScore.from_judge_json(
        {"factual_correctness": 0, "clarity": 9, "actionability": 3,
         "identifies_key_mistake": 3}
    )
    assert score.scores["factual_correctness"] == rubric.SCALE_MIN  # 0 -> 1
    assert score.scores["clarity"] == rubric.SCALE_MAX              # 9 -> 5


def test_rubric_missing_axis_raises():
    with pytest.raises(rubric.RubricError, match="clarity"):
        rubric.RubricScore.from_judge_json(
            {"factual_correctness": 4, "actionability": 3, "identifies_key_mistake": 4}
        )


def test_rubric_non_integer_axis_raises():
    with pytest.raises(rubric.RubricError):
        rubric.RubricScore.from_judge_json(
            {"factual_correctness": "great", "clarity": 5, "actionability": 3,
             "identifies_key_mistake": 4}
        )


def test_rubric_to_dict_shape():
    score = rubric.RubricScore.from_judge_json(
        {"factual_correctness": 3, "clarity": 3, "actionability": 3,
         "identifies_key_mistake": 3}
    )
    d = score.to_dict()
    assert d["overall"] == 3.0
    assert set(d["scores"]) == set(rubric.RUBRIC_AXES)


# --- judge parsing -----------------------------------------------------------------

def test_parse_verdict_plain_json():
    score = judge.parse_verdict(VALID_VERDICT)
    assert score.overall == 4.0


def test_parse_verdict_tolerates_fences_and_prose():
    raw = "Here is my verdict:\n```json\n" + VALID_VERDICT + "\n```\nHope that helps!"
    score = judge.parse_verdict(raw)
    assert score.scores["actionability"] == 3


def test_parse_verdict_no_json_raises():
    with pytest.raises(judge.JudgeError, match="no JSON"):
        judge.parse_verdict("I think it was pretty good, 4 out of 5.")


def test_parse_verdict_malformed_json_raises():
    with pytest.raises(judge.JudgeError):
        judge.parse_verdict('{"factual_correctness": 4, "clarity": }')


def test_parse_verdict_missing_axis_raises():
    with pytest.raises(judge.JudgeError, match="identifies_key_mistake"):
        judge.parse_verdict(
            '{"factual_correctness": 4, "clarity": 5, "actionability": 3}'
        )


# --- judge orchestration -----------------------------------------------------------

def test_build_judge_messages_includes_facts_and_coaching():
    messages = judge.build_judge_messages("Coaching text here.", "FACTS: 17...Nxd4")
    system, user = messages[0]["content"], messages[1]["content"]
    assert "factual_correctness" in system and "JSON" in system
    assert "17...Nxd4" in user and "Coaching text here." in user


def test_judge_coaching_uses_client(monkeypatch):
    captured = {}

    def fake_chat(messages, model, temperature):
        captured["temperature"] = temperature
        return VALID_VERDICT

    monkeypatch.setattr(judge.client, "chat", fake_chat)
    score = judge.judge_coaching("great coaching", SAMPLE_REPORT, coached_side="black")
    assert score.overall == 4.0
    assert captured["temperature"] == judge.DEFAULT_JUDGE_TEMPERATURE  # 0.0


# --- live smoke test ---------------------------------------------------------------

@requires_model
def test_live_judge_returns_valid_scores():
    coaching = "Your worst move was 17...Nxd4; Qe7 was safer. Also 12...h6 — prefer Be7."
    score = judge.judge_coaching(coaching, SAMPLE_REPORT, coached_side="black")
    assert set(score.scores) == set(rubric.RUBRIC_AXES)
    assert all(rubric.SCALE_MIN <= v <= rubric.SCALE_MAX for v in score.scores.values())
