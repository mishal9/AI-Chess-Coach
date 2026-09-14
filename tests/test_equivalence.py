"""Paired equivalence testing.

The first test is a regression lock on the numbers the paper reports. The project's own
convention is "no number in prose without its JSON"; this extends it to "no number in
prose without a test", because a headline statistic that silently drifts is worse than one
that was never computed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("scipy", reason="needs the `eval` extra")

from eval.compare import load_report  # noqa: E402
from eval.equivalence import (  # noqa: E402
    agreement_problems,
    compare_reports,
    assess_axis,
    judge_agreement,
    main,
    paired_scores,
    rubric_comparability_problems,
)

REPORTS = Path("eval/reports")
CONTROL = REPORTS / "prompted_8b_2026-08-14.json"
FINE_TUNED = REPORTS / "8b_v2_2026-08-10.json"


def game(pgn="a.pgn", index=0, side="white", **scores):
    base = {
        "factual_correctness": 3,
        "clarity": 3,
        "actionability": 3,
        "identifies_key_mistake": 3,
    }
    return {
        "pgn": pgn,
        "game_index": index,
        "coached_side": side,
        "rubric": {"scores": {**base, **scores}, "overall": 3.0, "rationale": ""},
    }


def report(games, judge="claude-opus-4-8", grounding_version=2):
    return {
        "judge_model": judge,
        "metric_versions": {"grounding": grounding_version, "claims": 1},
        "games": games,
    }


@pytest.mark.skipif(not CONTROL.exists(), reason="committed reports not present")
class TestThePaperNumbers:
    """Locks §6.3 of the paper outline to the committed reports."""

    def results(self):
        return {
            r.axis: r
            for r in compare_reports(load_report(CONTROL), load_report(FINE_TUNED))
        }

    def test_the_factual_null_is_underpowered_not_a_tie(self):
        """The headline. Δ is exactly zero, and that is NOT the same as equivalence."""
        r = self.results()["factual_correctness"]
        assert r.n == 29
        assert r.mean_difference == pytest.approx(0.0, abs=1e-9)
        assert (r.ci_low, r.ci_high) == pytest.approx((-0.368, 0.368), abs=5e-4)
        assert r.tost_p == pytest.approx(0.088, abs=5e-4)
        assert not r.equivalent, "must not be reported as equivalence — it is a bound"

    def test_overall_quality_is_a_genuine_equivalence(self):
        r = self.results()["rubric_overall"]
        assert r.tost_p == pytest.approx(0.016, abs=5e-4)
        assert r.equivalent

    def test_the_axes_split_the_way_the_paper_says(self):
        results = self.results()
        equivalent = {a for a, r in results.items() if r.equivalent}
        assert equivalent == {"clarity", "identifies_key_mistake", "rubric_overall"}

    def test_the_factual_axis_would_need_roughly_120_games(self):
        r = self.results()["factual_correctness"]
        assert r.mde == pytest.approx(0.63, abs=0.01)
        assert 110 <= r.n_needed <= 130


class TestTostBehaviour:
    def test_identical_scores_are_equivalent(self):
        scores = [3.0] * 10
        result = assess_axis(scores, list(scores), "factual_correctness")
        assert result.mean_difference == 0.0
        assert result.equivalent

    def test_a_large_consistent_difference_is_not_equivalence(self):
        base = [2.0] * 20
        cand = [4.0] * 20
        result = assess_axis(base, cand, "factual_correctness")
        assert result.mean_difference == 2.0
        assert not result.equivalent

    def test_noisy_data_around_zero_is_inconclusive_not_equivalent(self):
        """The distinction the whole module exists for."""
        base = [1.0, 5.0] * 6
        cand = [5.0, 1.0] * 6
        result = assess_axis(base, cand, "factual_correctness")
        assert result.mean_difference == pytest.approx(0.0)
        assert not result.equivalent, "wide spread cannot support an equivalence claim"
        assert result.n_needed > len(base)

    def test_two_games_is_the_minimum(self):
        with pytest.raises(ValueError, match="at least 2"):
            assess_axis([3.0], [4.0], "factual_correctness")


class TestPairing:
    def test_misaligned_games_are_refused(self):
        base = report([game(pgn="one.pgn")])
        cand = report([game(pgn="two.pgn")])
        with pytest.raises(ValueError, match="not paired"):
            paired_scores(base, cand, "factual_correctness")

    def test_a_different_coached_side_is_refused(self):
        base = report([game(side="white")])
        cand = report([game(side="black")])
        with pytest.raises(ValueError, match="not paired"):
            paired_scores(base, cand, "factual_correctness")

    def test_different_lengths_are_refused(self):
        with pytest.raises(ValueError, match="different numbers"):
            paired_scores(report([game()]), report([game(), game()]), "clarity")


class TestComparability:
    def test_a_different_judge_blocks_the_comparison(self):
        problems = rubric_comparability_problems(
            report([game()], judge="claude-opus-4-8"),
            report([game()], judge="gemini-2.5-pro"),
        )
        assert problems and "same ruler" in problems[0]

    def test_a_grounding_version_difference_does_not(self):
        """The rubric comes from a judge that never touches the citation parser.

        eval.compare rightly refuses this pairing for grounding; applying that rule here
        would block a valid rubric comparison, which is its own kind of wrong answer.
        """
        problems = rubric_comparability_problems(
            report([game()], grounding_version=1),
            report([game()], grounding_version=2),
        )
        assert problems == []


def judged(text, factual):
    g = game(factual_correctness=factual, clarity=factual)
    g["coaching"] = text
    return g


class TestJudgeAgreement:
    def texts(self):
        return [f"coaching {i}" for i in range(5)]

    def test_identical_scores_agree_perfectly(self):
        a = report([judged(t, s) for t, s in zip(self.texts(), [1, 2, 3, 4, 5])])
        b = report([judged(t, s) for t, s in zip(self.texts(), [1, 2, 3, 4, 5])],
                   judge="gemini-3.1-pro-preview")
        factual = {r.axis: r for r in judge_agreement(a, b)}["factual_correctness"]
        assert factual.pearson == 1.0 and factual.exact_match == 1.0 and factual.bias == 0

    def test_a_uniformly_harsher_judge_shows_as_bias_not_disagreement(self):
        a = report([judged(t, s) for t, s in zip(self.texts(), [2, 3, 4, 5, 5])])
        b = report([judged(t, s) for t, s in zip(self.texts(), [1, 2, 3, 4, 4])],
                   judge="gemini-3.1-pro-preview")
        factual = {r.axis: r for r in judge_agreement(a, b)}["factual_correctness"]
        assert factual.pearson == 1.0
        assert factual.bias == -1.0
        assert factual.exact_match == 0.0 and factual.within_one == 1.0

    def test_different_coaching_text_is_refused(self):
        a = report([judged("one", 3), judged("two", 3)])
        b = report([judged("one", 3), judged("CHANGED", 3)],
                   judge="gemini-3.1-pro-preview")
        problems = agreement_problems(a, b)
        assert problems and "not the same texts" in problems[0]

    def test_the_same_judge_twice_is_refused(self):
        a = report([judged("one", 3)])
        assert "no second judge" in agreement_problems(a, a)[0]

    def test_cli_prints_agreement(self, tmp_path, capsys):
        import json

        a = report([judged(t, s) for t, s in zip(self.texts(), [1, 2, 3, 4, 5])])
        b = report([judged(t, s) for t, s in zip(self.texts(), [1, 3, 3, 4, 5])],
                   judge="gemini-3.1-pro-preview")
        pa, pb = tmp_path / "a.json", tmp_path / "b.json"
        pa.write_text(json.dumps(a))
        pb.write_text(json.dumps(b))
        assert main(["--agreement", str(pa), str(pb)]) == 0
        out = capsys.readouterr().out
        assert "Cross-judge agreement" in out and "gemini-3.1-pro-preview" in out
