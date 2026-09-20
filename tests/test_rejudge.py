"""Re-judging stored coaching with a second judge.

No API calls: the judge is injected. What matters here is that the run survives a
free-tier daily quota landing mid-way, because that is exactly what happened the first
time it was run for real.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("scipy", reason="needs the `eval` extra")

from eval.backends import GeminiDailyQuotaExhausted, _retry_delay  # noqa: E402
from eval.equivalence import judge_agreement  # noqa: E402
from eval.rejudge import _reaggregate, judged_count  # noqa: E402


def game(pgn="a.pgn", index=0, side="white", coaching="You played Nxe5.", **scores):
    base = {"factual_correctness": 3, "clarity": 3,
            "actionability": 3, "identifies_key_mistake": 3}
    return {
        "pgn": pgn, "game_index": index, "coached_side": side, "coaching": coaching,
        "rubric": {"scores": {**base, **scores}, "overall": 3.0, "rationale": "r"},
    }


def report(games, judge="claude-opus-4-8"):
    return {"judge_model": judge, "metric_versions": {"grounding": 2, "claims": 1},
            "games": games}


class TestQuotaHandling:
    def test_a_per_minute_limit_is_a_wait_not_a_failure(self):
        """The server tells us how long; honour it rather than guessing."""
        assert _retry_delay("'retryDelay': '20.8s'") == pytest.approx(21.8)
        assert _retry_delay("no delay here") == 20.0

    def test_a_daily_cap_raises_its_own_error(self):
        """Retrying a daily cap burns attempts and hides the reason for hours."""
        assert issubclass(GeminiDailyQuotaExhausted, RuntimeError)


class TestResume:
    def test_counts_only_games_judged_by_the_named_model(self):
        games = [game(), game(pgn="b.pgn"), game(pgn="c.pgn")]
        games[0]["judged_by"] = "gemini-2.5-flash"
        games[1]["judged_by"] = "claude-opus-4-8"
        assert judged_count(report(games), "gemini-2.5-flash") == 1

    def test_an_empty_report_counts_zero(self):
        assert judged_count({}, "gemini-2.5-flash") == 0


class TestReaggregate:
    def test_the_summary_readers_use_follows_the_new_judge(self):
        """A stale nested summary once kept the first judge's means beside the second's games."""
        games = [
            {**game(clarity=5), "grounding": {"score": 1.0, "grounded": True},
             "claims": {"score": 1.0, "ok": True}, "identifies_worst_move": True},
        ]
        rep = report(games)
        rep["aggregate"] = {"rubric_axis_means": {"clarity": 1.0}, "rubric_overall_mean": 1.0}
        _reaggregate(rep)
        assert rep["aggregate"]["rubric_axis_means"]["clarity"] == 5.0
        assert rep["aggregate"]["rubric_overall_mean"] == 3.0


class TestAgreement:
    def test_identical_judges_agree_perfectly(self):
        games = [game(pgn=f"{i}.pgn", factual_correctness=s)
                 for i, s in enumerate([1, 3, 5, 2, 4])]
        a = report(games)
        b = json.loads(json.dumps(a))
        results = {r.axis: r for r in judge_agreement(a, b)}
        assert results["factual_correctness"].pearson == pytest.approx(1.0)
        assert results["factual_correctness"].exact_match == 1.0
        assert results["factual_correctness"].bias == 0.0

    def test_a_uniformly_generous_judge_shows_up_as_bias_not_disagreement(self):
        """The finding a single-judge setup cannot see: perfect ranking, shifted scale."""
        strict = [game(pgn=f"{i}.pgn", factual_correctness=s)
                  for i, s in enumerate([1, 2, 3, 4])]
        kind = [game(pgn=f"{i}.pgn", factual_correctness=s + 1)
                for i, s in enumerate([1, 2, 3, 4])]
        r = {x.axis: x for x in judge_agreement(report(strict), report(kind))}[
            "factual_correctness"
        ]
        assert r.pearson == pytest.approx(1.0)
        assert r.bias == pytest.approx(1.0)
        assert r.exact_match == 0.0
        assert r.within_one == 1.0

    def test_a_flat_judge_has_no_correlation_to_report(self):
        varied = [game(pgn=f"{i}.pgn", factual_correctness=s)
                  for i, s in enumerate([1, 3, 5])]
        flat = [game(pgn=f"{i}.pgn", factual_correctness=4) for i in range(3)]
        r = {x.axis: x for x in judge_agreement(report(varied), report(flat))}[
            "factual_correctness"
        ]
        import math
        assert math.isnan(r.pearson), "no variance means no correlation to report"
        assert r.bias == pytest.approx(1.0)
