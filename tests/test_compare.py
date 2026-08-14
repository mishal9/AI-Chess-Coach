"""Tests for eval.compare — the baseline-vs-fine-tune report diff."""

from __future__ import annotations

from eval import compare


def _game(pgn, side, gscore, grounded, worst, factual, overall=None):
    return {
        "pgn": pgn, "coached_side": side, "note": "",
        "grounding": {"score": gscore, "grounded": grounded},
        "identifies_worst_move": worst,
        "rubric": {"scores": {
            "factual_correctness": factual, "clarity": 4,
            "actionability": 3, "identifies_key_mistake": 4,
        }, "overall": overall if overall is not None else factual},
    }


def test_aggregate_means():
    games = [
        _game("clean_draw.pgn", "white", 0.0, False, False, 2),
        _game("one_blunder.pgn", "white", 1.0, True, True, 4),
    ]
    m = compare.aggregate(games)
    assert m["grounding"] == 0.5
    assert m["grounded_pct"] == 50.0
    assert m["worst_pct"] == 50.0
    assert m["factual_correctness"] == 3.0


def test_by_bucket_groups_by_pgn_stem():
    games = [_game("clean_draw.pgn", "white", 0.4, False, False, 2),
             _game("clean_draw.pgn", "black", 0.4, True, False, 3),
             _game("one_blunder.pgn", "white", 1.0, True, True, 4)]
    b = compare.by_bucket(games)
    assert set(b) == {"clean_draw", "one_blunder"}
    assert len(b["clean_draw"]) == 2


def test_paired_factual_counts():
    base = [_game("a.pgn", "white", 0.5, True, True, 2),
            _game("b.pgn", "black", 0.5, True, True, 3)]
    cand = [_game("a.pgn", "white", 0.9, True, True, 4),   # +2 better
            _game("b.pgn", "black", 0.5, True, True, 3)]   # same
    p = compare.paired_factual(base, cand)
    assert p == {"better": 1, "same": 1, "worse": 0}


def test_render_verdict_beats():
    base = [_game("clean_draw.pgn", "white", 0.4, False, False, 2, overall=2.5)]
    cand = [_game("clean_draw.pgn", "white", 0.9, True, True, 4, overall=3.8)]
    txt = compare.render(base, cand, "baseline", "v1")
    assert "BEATS baseline" in txt
    assert "clean_draw" in txt
    assert "factual" in txt


def test_render_verdict_regression():
    base = [_game("one_blunder.pgn", "white", 0.9, True, True, 4, overall=3.8)]
    cand = [_game("one_blunder.pgn", "white", 0.5, True, True, 2, overall=2.5)]
    txt = compare.render(base, cand)
    assert "does NOT beat baseline" in txt


# --- judge-free (--no-judge) reports -------------------------------------------------

def _g(pgn="clean_draw.pgn", side="white", score=0.9, worst=True, rubric=None):
    g = {"pgn": pgn, "coached_side": side,
         "grounding": {"score": score, "grounded": score >= 1.0},
         "identifies_worst_move": worst}
    if rubric is not None:
        g["rubric"] = rubric
    return g


def test_aggregate_omits_rubric_metrics_when_absent():
    m = compare.aggregate([_g(), _g(score=0.8)])
    assert "grounding" in m and "overall" not in m
    assert not compare.has_rubric(m)


def test_render_grounding_only_reports_does_not_crash():
    base = [_g(score=0.79)]
    cand = [_g(score=0.91)]
    out = compare.render(base, cand, "arm_a", "arm_b")
    assert "grounding" in out
    assert "verdict:" not in out         # the verdict LINE is skipped (message may name it)
    assert "grounding-only" in out


def test_render_still_full_when_both_judged():
    r = {"overall": 4.0, "scores": {a: 4 for a in compare.AXES}}
    out = compare.render([_g(rubric=r)], [_g(rubric=r)], "a", "b")
    assert "verdict" in out and "paired factual" in out


# --- comparability: refusing to difference incompatible reports ------------------
# This tool once reported a fine-tune 0.02 BEHIND on grounding when it was 0.042 ahead,
# because the candidate carried post-#41 scores and the baseline's stored mean pre-#41
# ones. Nothing recorded which semantics produced either number.

import json  # noqa: E402

from eval import claims, grounding  # noqa: E402


def _report(metric_versions=None, judge_model="claude-opus-4-8", with_claims=False):
    game = _game("one_blunder.pgn", "white", 1.0, True, True, 4)
    if with_claims:
        game = dict(game, claims={"score": 1.0, "ok": True, "violations": []})
    report = {"judge_model": judge_model, "aggregate": {}, "games": [game]}
    if metric_versions is not None:
        report["metric_versions"] = metric_versions
    return report


def test_missing_versions_are_read_as_the_pre_41_semantics():
    # Every report predating versioning was produced by the old parser — known, not unknown.
    assert compare.metric_versions(_report()) == {"grounding": 1}


def test_stamped_versions_are_used_as_given():
    assert compare.metric_versions(_report({"grounding": 2, "claims": 1})) == {
        "grounding": 2, "claims": 1
    }


def test_grounding_version_mismatch_is_refused():
    problems = compare.comparability_problems(
        _report({"grounding": 2}), _report()          # v2 vs legacy v1
    )
    assert len(problems) == 1
    assert "grounding" in problems[0]
    assert "eval.rescore" in problems[0]               # says how to repair it


def test_matching_versions_compare_cleanly():
    assert compare.comparability_problems(
        _report({"grounding": 2}), _report({"grounding": 2})
    ) == []


def test_claims_version_is_only_checked_when_both_reports_have_claims():
    # A judged report and a claims-bearing one still compare fine on grounding.
    base = _report({"grounding": 2}, with_claims=False)
    cand = _report({"grounding": 2, "claims": 1}, with_claims=True)
    assert compare.comparability_problems(base, cand) == []

    both_old = _report({"grounding": 2, "claims": 1}, with_claims=True)
    both_new = _report({"grounding": 2, "claims": 2}, with_claims=True)
    problems = compare.comparability_problems(both_old, both_new)
    assert len(problems) == 1 and "claims" in problems[0]


def test_different_judges_are_refused():
    problems = compare.comparability_problems(
        _report({"grounding": 2}, judge_model="claude-opus-4-8"),
        _report({"grounding": 2}, judge_model="gemini-2.5-pro"),
    )
    assert len(problems) == 1 and "ruler" in problems[0]


def test_cli_refuses_a_cross_version_comparison(tmp_path, capsys):
    base, cand = tmp_path / "b.json", tmp_path / "c.json"
    base.write_text(json.dumps(_report({"grounding": 2})), encoding="utf-8")
    cand.write_text(json.dumps(_report()), encoding="utf-8")
    assert compare.main([str(base), str(cand)]) == 1
    err = capsys.readouterr().err
    assert "Refusing to compare" in err and "eval.rescore" in err


def test_cli_override_proceeds_but_shouts(tmp_path, capsys):
    base, cand = tmp_path / "b.json", tmp_path / "c.json"
    base.write_text(json.dumps(_report({"grounding": 2})), encoding="utf-8")
    cand.write_text(json.dumps(_report()), encoding="utf-8")
    assert compare.main([str(base), str(cand), "--allow-version-mismatch"]) == 0
    captured = capsys.readouterr()
    assert "NOT valid" in captured.err
    assert "eval.compare" in captured.out          # the table still renders


def test_current_versions_are_stamped_by_the_metrics_themselves():
    # The constants live next to the code defining the semantics, so a change to one is
    # a visible change to the other.
    assert grounding.METRIC_VERSION >= 2          # post-#41 bare-square handling
    assert claims.METRIC_VERSION >= 1
