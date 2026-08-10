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
