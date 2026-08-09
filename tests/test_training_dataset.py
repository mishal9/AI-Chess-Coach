"""Tests for JSONL I/O, the grounding filter, and the deterministic leakage-safe split."""

from __future__ import annotations

from training import dataset
from training.schema import DistillRecord


def _rec(pgn: str, index: int, grounding: float = 1.0) -> DistillRecord:
    return DistillRecord(
        source={"pgn": pgn, "game_index": index, "coached_side": "white"},
        coached_side="white",
        facts="f",
        prompt=[{"role": "system", "content": "s"}, {"role": "user", "content": "u"}],
        completion="c",
        teacher={"backend": "anthropic", "model": "m"},
        quality={"grounding": grounding, "grounded": grounding >= 1.0},
    )


# --- JSONL I/O ---------------------------------------------------------------------

def test_write_then_read_roundtrips(tmp_path):
    rows = [{"a": 1}, {"b": "two"}]
    path = tmp_path / "x.jsonl"
    assert dataset.write_jsonl(path, rows) == 2
    assert dataset.read_jsonl(path) == rows


# --- grounding filter --------------------------------------------------------------

def test_filter_drops_below_threshold():
    recs = [_rec("a.pgn", 0, 1.0), _rec("b.pgn", 0, 0.5), _rec("c.pgn", 0, 0.83)]
    kept = dataset.filter_records(recs, min_grounding=1.0)
    assert [r.source["pgn"] for r in kept] == ["a.pgn"]


# --- split determinism & leakage-safety --------------------------------------------

def test_assign_split_is_deterministic():
    assert dataset.assign_split("g.pgn#0") == dataset.assign_split("g.pgn#0")


def test_all_positions_of_a_game_share_a_split():
    # Same game (same key), many positions -> never straddles splits.
    recs = [_rec("same.pgn", 0) for _ in range(20)]
    splits = dataset.split_records(recs)
    nonempty = [s for s, r in splits.items() if r]
    assert len(nonempty) == 1


def test_split_covers_all_records_without_duplication():
    recs = [_rec(f"g{i}.pgn", 0) for i in range(50)]
    splits = dataset.split_records(recs)
    total = sum(len(r) for r in splits.values())
    assert total == 50


def test_ratios_roughly_honoured_over_many_games():
    recs = [_rec(f"g{i}.pgn", 0) for i in range(1000)]
    splits = dataset.split_records(recs, ratios=(0.8, 0.1, 0.1), seed=0)
    assert 0.7 < len(splits["train"]) / 1000 < 0.9  # ~80%, hash-uniform


# --- CLI end to end ----------------------------------------------------------------

def test_main_writes_splits_and_manifest(tmp_path):
    raw = tmp_path / "raw.jsonl"
    dataset.write_jsonl(
        raw,
        [_rec(f"g{i}.pgn", 0, grounding=1.0).to_dict() for i in range(10)]
        + [_rec("bad.pgn", 0, grounding=0.0).to_dict()],  # dropped by the gate
    )
    out = tmp_path / "v1"
    rc = dataset.main(["--in", str(raw), "--out-dir", str(out), "--as-chat"])
    assert rc == 0

    manifest = dataset.read_jsonl  # sanity: module loaded
    import json

    m = json.loads((out / "manifest.json").read_text())
    assert m["total"] == 10
    assert m["dropped_below_grounding"] == 1
    assert m["format"] == "chat"
    # chat rows carry the appended assistant turn
    for split in dataset.SPLITS:
        for row in dataset.read_jsonl(out / f"{split}.jsonl"):
            assert row["messages"][-1]["role"] == "assistant"


def test_manifest_counts_row_kinds(tmp_path):
    import dataclasses
    import json
    recs = [
        _rec("a.pgn", 0),
        dataclasses.replace(_rec("a.pgn", 0), kind="position"),
        dataclasses.replace(_rec("b.pgn", 0), kind="position"),
    ]
    raw = tmp_path / "raw.jsonl"
    dataset.write_jsonl(raw, [r.to_dict() for r in recs])
    out = tmp_path / "ds"
    assert dataset.main(["--in", str(raw), "--out-dir", str(out)]) == 0
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["kinds"] == {"game": 1, "position": 2}
