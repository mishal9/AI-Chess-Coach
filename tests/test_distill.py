"""Tests for the distillation pipeline.

The teacher is injected as a fake, so record-building, the grounding self-check, the
leakage guard, and the spend guard run with no Stockfish, Claude, or API key.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from training import distill
from training.teacher import build_teacher_messages
from tests.test_coach import SAMPLE_REPORT


# --- teacher prompt ----------------------------------------------------------------

def test_teacher_sees_the_same_user_facts_as_the_student():
    from coach import prompts

    student = prompts.build_messages(SAMPLE_REPORT, "black")
    teacher = build_teacher_messages(SAMPLE_REPORT, "black")
    assert teacher[1] == student[1]           # identical facts/user turn
    assert teacher[0] != student[0]           # elevated teacher system prompt
    assert "GOLD-STANDARD TEACHER" in teacher[0]["content"]


# --- build_record ------------------------------------------------------------------

def _source() -> distill.SourceGame:
    return distill.SourceGame(pgn=Path("game.pgn"), game_index=0, coached_side="black")


def test_build_record_packages_grounded_pair():
    teacher_fn = lambda r, s: "Your 17...Nxd4 was the blunder; Qe7 held."
    rec = distill.build_record(_source(), SAMPLE_REPORT, teacher_fn,
                               {"backend": "anthropic", "model": "m"})
    assert rec.coached_side == "black"
    assert rec.completion.startswith("Your 17...Nxd4")
    assert rec.quality["grounded"] is True
    assert rec.quality["grounding"] == 1.0
    assert rec.prompt[-1]["role"] == "user"
    # difficulty signals come from the report
    assert rec.quality["num_mistakes"] == 2      # Nxd4 + h6 by black
    assert rec.quality["acpl"] == 88.0


def test_build_record_flags_teacher_hallucination():
    rec = distill.build_record(_source(), SAMPLE_REPORT,
                               lambda r, s: "You blundered with Nf7.",
                               {"backend": "anthropic", "model": "m"})
    assert rec.quality["grounded"] is False
    assert rec.quality["hallucinated"] == ["Nf7"]


def test_build_record_auto_picks_worse_side():
    src = distill.SourceGame(pgn=Path("g.pgn"), game_index=0, coached_side=None)
    rec = distill.build_record(src, SAMPLE_REPORT, lambda r, s: "ok",
                               {"backend": "x", "model": "y"})
    assert rec.coached_side == "black"           # higher ACPL


# --- source loading & guards -------------------------------------------------------

def test_load_sources_refuses_heldout_set():
    with pytest.raises(SystemExit, match="held-out"):
        distill.load_sources(Path("eval/heldout/manifest.json"))


def test_load_sources_reads_manifest(tmp_path):
    (tmp_path / "a.pgn").write_text("")
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps([{"pgn": "a.pgn", "coached_side": "white"}]))
    sources = distill.load_sources(manifest)
    assert len(sources) == 1
    assert sources[0].coached_side == "white"
    assert sources[0].pgn == tmp_path / "a.pgn"


def test_spend_guard_refuses_over_budget(tmp_path, capsys):
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps([{"pgn": "a.pgn"}, {"pgn": "b.pgn"}]))
    rc = distill.main(["--sources", str(manifest), "--max-teacher-calls", "1"])
    assert rc == 1
    assert "Refusing to start" in capsys.readouterr().err
