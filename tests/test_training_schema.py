"""Tests for the distillation record shape and its projections."""

from __future__ import annotations

from training.schema import SCHEMA_VERSION, DistillRecord


def _record(**over) -> DistillRecord:
    base = dict(
        source={"pgn": "g.pgn", "game_index": 2, "coached_side": "black"},
        coached_side="black",
        facts="You are coaching BLACK...",
        prompt=[
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "facts"},
        ],
        completion="Your 17...Nxd4 dropped a piece.",
        teacher={"backend": "anthropic", "model": "claude-opus-4-8"},
        quality={"grounding": 1.0, "grounded": True},
    )
    base.update(over)
    return DistillRecord(**base)


def test_roundtrips_through_dict():
    rec = _record()
    assert DistillRecord.from_dict(rec.to_dict()).to_dict() == rec.to_dict()


def test_to_dict_stamps_schema_version():
    assert _record().to_dict()["schema_version"] == SCHEMA_VERSION


def test_chat_example_appends_completion_as_assistant():
    ex = _record().to_chat_example()["messages"]
    assert [m["role"] for m in ex] == ["system", "user", "assistant"]
    assert ex[-1]["content"] == "Your 17...Nxd4 dropped a piece."


def test_chat_example_drops_teacher_and_quality():
    # The trainer must never see the teacher's identity or our internal metadata.
    ex = _record().to_chat_example()
    assert set(ex) == {"messages"}


def test_source_key_is_pgn_and_index():
    assert _record().source_key() == "g.pgn#2"


def test_kind_defaults_to_game_and_roundtrips():
    assert _record().kind == "game"
    pos = _record(kind="position",
                  source={"pgn": "g.pgn", "game_index": 2, "coached_side": "black",
                          "move_number": 17, "move_san": "Nxd4"})
    back = DistillRecord.from_dict(pos.to_dict())
    assert back.kind == "position"
    assert back.source["move_san"] == "Nxd4"


def test_v1_rows_without_kind_load_as_game_rows():
    d = _record().to_dict()
    del d["kind"]
    d["schema_version"] = 1
    back = DistillRecord.from_dict(d)
    assert back.kind == "game"
    assert back.schema_version == 1


def test_position_rows_share_the_game_split_key():
    game = _record()
    pos = _record(kind="position",
                  source={"pgn": "g.pgn", "game_index": 2, "coached_side": "black",
                          "move_number": 17, "move_san": "Nxd4"})
    assert pos.source_key() == game.source_key()  # same game -> same split, no leakage
