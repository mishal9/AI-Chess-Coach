"""Tests for backfilling claim checks onto committed reports.

The join is the risky part — reports written before #43 carry no ``game_index`` — so most
of these test that an unsafe join is refused rather than guessed at.
"""

from __future__ import annotations

import json

import chess

from eval import recheck

FACTS = (
    "Your most costly moves (worst first):\n"
    "- 12...Re8?! (inaccuracy): the engine preferred Nh5; cost about 10% win probability "
    "(cp loss 119).\n"
)


def _analyzed(pgn="one_blunder.pgn", game_index=0, side="black", sans=("e4", "e5")):
    board = chess.Board()
    moves = []
    for san in sans:
        moves.append({"san": san,
                      "side": "white" if board.turn == chess.WHITE else "black",
                      "fen_before": board.fen()})
        board.push_san(san)
    return {"pgn": pgn, "game_index": game_index, "coached_side": side,
            "report": {"moves": moves}, "facts": FACTS}


def _game(coaching, pgn="one_blunder.pgn", side="black", score=1.0, hallucinated=()):
    return {"pgn": pgn, "coached_side": side, "coaching": coaching,
            "grounding": {"score": score, "grounded": not hallucinated,
                          "hallucinated": list(hallucinated)}}


def test_alignment_holds_for_a_matching_report():
    games = [_game("You played Re8, and the engine preferred Nh5.")]
    assert recheck.verify_alignment(games, [_analyzed()]) == []


def test_alignment_rejects_a_length_mismatch():
    problems = recheck.verify_alignment([_game("text")], [_analyzed(), _analyzed()])
    assert problems and "manifest has 2" in problems[0]


def test_alignment_rejects_a_pgn_or_side_mismatch():
    games = [_game("You played Re8.", pgn="clean_draw.pgn")]
    problems = recheck.verify_alignment(games, [_analyzed()])
    assert problems and "does not match manifest" in problems[0]


def test_alignment_rejects_when_grounding_does_not_reproduce():
    """The check that makes a positional join trustworthy rather than assumed.

    The coaching cites Bg5, which the facts do not contain, so the stored "clean" score
    cannot have come from this game.
    """
    games = [_game("You played Bg5.", score=1.0, hallucinated=())]
    problems = recheck.verify_alignment(games, [_analyzed()])
    assert problems and "does not reproduce" in problems[0]


def test_alignment_rejects_a_disagreeing_game_index():
    games = [dict(_game("You played Re8."), game_index=4)]
    problems = recheck.verify_alignment(games, [_analyzed(game_index=0)])
    assert problems and "game_index disagrees" in problems[0]


def test_recheck_attaches_claims_and_aggregates():
    report = {"games": [_game("You played Re8, and the engine preferred Nh5."),
                        _game("When you played Nh5, it slipped.")],
              "aggregate": {"grounding_mean": 1.0}}
    out = recheck.recheck_report(report, [_analyzed(), _analyzed(game_index=1)])
    assert out["games"][0]["claims"]["ok"]
    assert not out["games"][1]["claims"]["ok"]          # Nh5 is the engine's move
    assert out["aggregate"]["claims_ok_rate"] == 0.5
    assert out["aggregate"]["grounding_mean"] == 1.0    # untouched
    assert out["games"][1]["game_index"] == 1           # backfilled from the manifest
    assert "claims" not in report["games"][0]           # input not mutated


def test_violation_counts_groups_by_kind():
    report = {"games": [
        {"claims": {"violations": [{"kind": "role_inversion"}]}},
        {"claims": {"violations": [{"kind": "role_inversion"},
                                   {"kind": "invented_placement"}]}},
    ]}
    assert recheck.violation_counts(report) == {
        "role_inversion": 2, "invented_placement": 1
    }


def test_cli_refuses_an_unaligned_report(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(recheck, "analyze_manifest", lambda *a, **k: [_analyzed()])
    path = tmp_path / "r.json"
    path.write_text(json.dumps({"depth": 15, "games": [_game("You played Bg5.")]}),
                    encoding="utf-8")
    assert recheck.main([str(path)]) == 1
    assert "refusing to backfill" in capsys.readouterr().err


def test_recheck_stamps_the_current_claims_version():
    """Same contract as eval.rescore: a backfilled report advertises its semantics."""
    from eval import claims

    report = {"games": [_game("You played Re8, and the engine preferred Nh5.")]}
    out = recheck.recheck_report(report, [_analyzed()])
    assert out["metric_versions"]["claims"] == claims.METRIC_VERSION


def test_recheck_refreshes_the_label_stable_subset():
    game = dict(_game("You played Bg5."), label_stable=True, identifies_worst_move=True)
    report = {"games": [game], "aggregate": {"label_stable_subset": {"claims_ok_rate": 0.0}}}
    out = recheck.recheck_report(report, [_analyzed()])
    assert out["aggregate"]["label_stable_subset"]["games"] == 1
    assert out["aggregate"]["label_stable_subset"]["claims_ok_rate"] == out["aggregate"]["claims_ok_rate"]
