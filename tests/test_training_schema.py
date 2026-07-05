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
