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
