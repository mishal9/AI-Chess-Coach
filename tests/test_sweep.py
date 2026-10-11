"""Tests for the nested sweep training sets (training.sweep)."""

from __future__ import annotations

import json

import pytest

from training import sweep
from training.dataset import write_jsonl
from training.schema import DistillRecord


def _rec(index: int, kind: str = "game", move: int = 0, grounding: float = 1.0) -> DistillRecord:
    source = {"pgn": "corpus.pgn", "game_index": index, "coached_side": "white"}
    if kind == "position":
        source["move_number"] = move
    return DistillRecord(
        source=source, coached_side="white", facts="f",
        prompt=[{"role": "system", "content": "s"}, {"role": "user", "content": "u"}],
        completion=f"{kind} {index} {move}", teacher={"backend": "deepseek", "model": "m"},
        quality={"grounding": grounding}, kind=kind,
    )


GAMES = [_rec(i) for i in range(60)]
POSITIONS = [_rec(i, "position", m) for i in range(60) for m in (30, 10, 20)]


def test_sizes_are_nested_prefixes():
    games, positions = sweep.ordered(GAMES, 0), sweep.ordered(POSITIONS, 0)
    for arm in ("G", "M"):
        small = sweep.arm_rows(arm, 30, games, positions)
        large = sweep.arm_rows(arm, 45, games, positions)
        assert set(map(id, small)) <= set(map(id, large))


def test_mixed_arm_is_one_game_to_two_position():
    games, positions = sweep.ordered(GAMES, 0), sweep.ordered(POSITIONS, 0)
    rows = sweep.arm_rows("M", 30, games, positions)
    assert [r.kind for r in rows].count("game") == 10
    assert [r.kind for r in rows].count("position") == 20
    top = sweep.arm_rows("M", "all", games, positions)
    assert [r.kind for r in top].count("position") == 2 * [r.kind for r in top].count("game")


def test_a_games_positions_stay_together_in_move_order():
    positions = sweep.ordered(POSITIONS, 0)
    first = positions[0].source_key()
    assert [r.source["move_number"] for r in positions[:3]] == [10, 20, 30]
    assert {r.source_key() for r in positions[:3]} == {first}


def test_a_size_the_pool_cannot_fill_is_refused():
    with pytest.raises(ValueError):
        sweep.arm_rows("G", 61, GAMES, POSITIONS)
    with pytest.raises(ValueError):
        sweep.arm_rows("M", 300, GAMES, POSITIONS)


def test_cli_writes_chat_sets_with_no_game_in_both_splits(tmp_path):
    mixed = GAMES + [_rec(99, "position", 5)]          # a position row in the game file
    write_jsonl(tmp_path / "g.jsonl", (r.to_dict() for r in mixed))
    write_jsonl(tmp_path / "p.jsonl", (r.to_dict() for r in POSITIONS + [_rec(1, grounding=0.5)]))
    sweep.main(["--game", str(tmp_path / "g.jsonl"), "--position", str(tmp_path / "p.jsonl"),
                "--arm", "G:20", "--arm", "M:30,all",
                "--out-root", str(tmp_path / "ds"), "--prefix", "t"])
    manifest = json.loads((tmp_path / "ds" / "t-M-30" / "manifest.json").read_text())
    assert manifest["train_kinds"] == {"game": 10, "position": 20}
    train = [json.loads(l) for l in open(tmp_path / "ds" / "t-M-30" / "train.jsonl")]
    val = [json.loads(l) for l in open(tmp_path / "ds" / "t-M-30" / "val.jsonl")]
    assert set(train[0]) == {"messages"}
    index = lambda row: int(row["messages"][-1]["content"].split()[1])
    assert not {index(r) for r in train} & {index(r) for r in val}
    # the game file's stray position row (game 99) is not used as a position row
    assert all(index(r) != 99 for r in train + val)
    g_val = [json.loads(l) for l in open(tmp_path / "ds" / "t-G-20" / "val.jsonl")]
    assert all(r["messages"][-1]["content"].startswith("game") for r in g_val)
