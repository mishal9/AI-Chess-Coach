"""Tests for offline re-scoring of committed eval reports.

No engine, no model, no network — re-scoring reads only what the report already stores.
"""

from __future__ import annotations

import json

from eval import grounding, rescore


def _game(coaching: str, score: float, hallucinated: list[str], **grounding) -> dict:
    return {
        "pgn": "one_blunder.pgn",
        "coaching": coaching,
        "grounding": {
            "score": score,
            "grounded": not hallucinated,
            "hallucinated": hallucinated,
            **grounding,
        },
    }


def test_legacy_extractor_reproduces_the_old_bare_square_behaviour():
    # Keeping the old parser is what makes the historical `cited` set recoverable.
    text = "Your rook on b7 is passive."
    assert "b7" in rescore.legacy_extract_moves(text)
    assert "b7" not in grounding.extract_moves(text)


def test_rescore_drops_bare_square_false_positives():
    # Old: cited {Rb8, Bc6, b7, b8}, 2 flagged -> 0.5. New: b7/b8 aren't citations.
    game = _game(
        "On **12...Rb8** you moved your rook from b7 to b8; the engine preferred Bc6.",
        score=0.5,
        hallucinated=["b7", "b8"],
    )
    result = rescore.rescore_game(game)
    assert result["cited"] == ["Bc6", "Rb8"]
    assert result["hallucinated"] == []
    assert result["grounded"]
    assert result["score"] == 1.0


def test_rescore_keeps_a_genuine_hallucination():
    game = _game(
        "The blunder was 21.Nd2; you should have played Bg5 to hold it.",
        score=0.5,
        hallucinated=["Bg5"],
    )
    result = rescore.rescore_game(game)
    assert result["hallucinated"] == ["Bg5"]
    assert not result["grounded"]
    assert result["score"] == 0.5


def test_rescore_prefers_a_stored_allowed_set():
    # With `allowed` persisted there is no reconstruction: the diff is taken directly,
    # so a move absent from `hallucinated` can still be flagged.
    game = _game(
        "You played Nd2 but Bg5 was better.",
        score=1.0,
        hallucinated=[],
        cited=["Bg5", "Nd2"],
        allowed=["Nd2"],
    )
    result = rescore.rescore_game(game)
    assert result["hallucinated"] == ["Bg5"]


def test_verify_accepts_a_self_consistent_report():
    game = _game(
        "On **12...Rb8** you moved your rook from b7 to b8; the engine preferred Bc6.",
        score=0.5,
        hallucinated=["b7", "b8"],
    )
    assert rescore.verify_reconstruction(game)


def test_verify_rejects_a_report_whose_score_does_not_follow():
    # Stored score is impossible for the stored coaching + flags -> refuse to guess.
    game = _game("You played Nd2.", score=0.25, hallucinated=["Bg5"])
    assert not rescore.verify_reconstruction(game)


def test_verify_passes_through_when_allowed_is_stored():
    game = _game("Anything.", score=0.0, hallucinated=[], allowed=["Nd2"])
    assert rescore.verify_reconstruction(game)


def test_rescore_report_recomputes_aggregates():
    report = {
        "coach_model": "qwen-coach-8b-v2",
        "aggregate": {"grounding_mean": 0.5, "grounded_rate": 0.0, "factual": 3.7},
        "games": [
            _game("Your rook on b7 is passive.", score=0.0, hallucinated=["b7"]),
            _game("You played Nd2 but Bg5 was better.", score=0.5, hallucinated=["Bg5"]),
        ],
    }
    out = rescore.rescore_report(report)
    assert out["aggregate"]["grounding_mean"] == 0.75  # (1.0 + 0.5) / 2
    assert out["aggregate"]["grounded_rate"] == 0.5
    assert out["aggregate"]["factual"] == 3.7          # untouched
    assert out["coach_model"] == "qwen-coach-8b-v2"
    assert report["games"][0]["grounding"]["score"] == 0.0  # input not mutated


def test_cli_refuses_an_unreconstructable_report(tmp_path, capsys):
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps({"games": [_game("You played Nd2.", 0.25, ["Bg5"])]}), encoding="utf-8"
    )
    assert rescore.main([str(path)]) == 1
    assert "cannot reconstruct" in capsys.readouterr().err


def test_cli_writes_the_rescored_report(tmp_path):
    src, out = tmp_path / "r.json", tmp_path / "out.json"
    src.write_text(
        json.dumps(
            {"games": [_game("Your rook on b7 is passive.", 0.0, ["b7"])]}
        ),
        encoding="utf-8",
    )
    assert rescore.main([str(src), "--out", str(out)]) == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["rescored_from"] == "r.json"
    assert written["aggregate"]["grounding_mean"] == 1.0


def test_rescore_stamps_the_current_grounding_version():
    """So eval.compare recognises a repaired report as repaired, rather than refusing it."""
    from eval import grounding

    report = {"games": [_game("Your rook on b7 is passive.", 0.0, ["b7"])]}
    out = rescore.rescore_report(report)
    assert out["metric_versions"]["grounding"] == grounding.METRIC_VERSION
