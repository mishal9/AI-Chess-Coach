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


# --- v2: position rows, retries, mixed emission -------------------------------------

def test_position_teacher_sees_the_same_user_facts_as_the_student():
    from coach import prompts
    from training.teacher import build_teacher_position_messages

    move = prompts.coachable_mistakes(SAMPLE_REPORT, "black")[0]
    student = prompts.build_position_messages(SAMPLE_REPORT, "black", move)
    teacher = build_teacher_position_messages(SAMPLE_REPORT, "black", move)
    assert teacher[1] == student[1]
    assert "GOLD-STANDARD TEACHER" in teacher[0]["content"]
    assert "ONE key moment" in teacher[0]["content"]


def test_build_position_record_packages_the_moment():
    from coach import prompts

    move = prompts.coachable_mistakes(SAMPLE_REPORT, "black")[0]     # 17...Nxd4
    fn = lambda r, s, m: "17...Nxd4 lost the knight for nothing; Qe7 kept it defended."
    rec = distill.build_position_record(_source(), SAMPLE_REPORT, move, fn,
                                        {"backend": "anthropic", "model": "m"})
    assert rec.kind == "position"
    assert rec.source["move_san"] == "Nxd4" and rec.source["move_number"] == 17
    assert rec.quality["grounded"] is True
    assert rec.quality["move_quality"] == "blunder"
    assert "h6" not in rec.facts                 # the other game mistake stays out


def test_position_grounding_is_stricter_than_game_grounding():
    # h6 is a real move of the game — but NOT part of this position's facts, so a
    # position row citing it counts as hallucinated. That strictness is the point.
    from coach import prompts

    move = prompts.coachable_mistakes(SAMPLE_REPORT, "black")[0]
    fn = lambda r, s, m: "After 17...Nxd4 (and earlier 12...h6) you were lost."
    rec = distill.build_position_record(_source(), SAMPLE_REPORT, move, fn,
                                        {"backend": "x", "model": "y"})
    assert rec.quality["grounded"] is False
    assert "h6" in rec.quality["hallucinated"]


def test_retry_rerolls_until_grounded_and_keeps_best():
    attempts = iter(["You blundered with Nf7.",                       # hallucinated
                     "Your 17...Nxd4 was the blunder; Qe7 held."])    # clean
    rec = distill.build_record(_source(), SAMPLE_REPORT,
                               lambda r, s: next(attempts),
                               {"backend": "x", "model": "y"}, retries=1)
    assert rec.quality["grounded"] is True
    assert rec.completion.startswith("Your 17...Nxd4")


def test_no_retry_keeps_the_single_attempt():
    rec = distill.build_record(_source(), SAMPLE_REPORT,
                               lambda r, s: "You blundered with Nf7.",
                               {"backend": "x", "model": "y"}, retries=0)
    assert rec.quality["grounded"] is False


def test_spend_guard_counts_positions_and_retries(tmp_path, capsys):
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps([{"pgn": "a.pgn"}, {"pgn": "b.pgn"}]))
    # 2 games x (1 + 4 positions) x (1 + 1 retry) = worst case 20 > 19
    rc = distill.main(["--sources", str(manifest), "--max-teacher-calls", "19"])
    assert rc == 1
    assert "worst case 20" in capsys.readouterr().err


def test_main_emits_game_plus_position_rows(tmp_path, monkeypatch):
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps([{"pgn": "a.pgn", "coached_side": "black"}]))
    out = tmp_path / "raw.jsonl"

    monkeypatch.setattr(distill, "analyze_source", lambda src, depth: SAMPLE_REPORT)
    monkeypatch.setattr(distill.teacher_mod, "make_teacher_fn",
                        lambda *a, **k: lambda r, s: "Your 17...Nxd4 was the blunder.")
    monkeypatch.setattr(distill.teacher_mod, "make_position_teacher_fn",
                        lambda *a, **k: lambda r, s, m: f"{m['san']} was costly.")

    rc = distill.main(["--sources", str(manifest), "--out", str(out),
                       "--max-teacher-calls", "100"])
    assert rc == 0
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    kinds = [r["kind"] for r in rows]
    assert kinds == ["game", "position", "position"]   # black has 2 coachable mistakes
    assert rows[1]["source"]["move_san"] == "Nxd4"     # worst first
    assert rows[2]["source"]["move_san"] == "h6"


def test_no_game_rows_emits_positions_only(tmp_path, monkeypatch):
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps([{"pgn": "a.pgn", "coached_side": "black"}]))
    out = tmp_path / "raw.jsonl"

    monkeypatch.setattr(distill, "analyze_source", lambda src, depth: SAMPLE_REPORT)
    monkeypatch.setattr(distill.teacher_mod, "make_teacher_fn",
                        lambda *a, **k: lambda r, s: "game row (should not be emitted)")
    monkeypatch.setattr(distill.teacher_mod, "make_position_teacher_fn",
                        lambda *a, **k: lambda r, s, m: f"{m['san']} was costly.")

    rc = distill.main(["--sources", str(manifest), "--out", str(out),
                       "--no-game-rows", "--max-teacher-calls", "100"])
    assert rc == 0
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert [r["kind"] for r in rows] == ["position", "position"]


# --- per-attempt temperature ---------------------------------------------------------

def test_first_attempt_and_retries_use_their_own_temperatures():
    seen = []

    def teacher(r, s, temperature=None):
        seen.append(temperature)
        return ("You blundered with Nf7." if len(seen) == 1
                else "Your 17...Nxd4 was the blunder; Qe7 held.")

    rec = distill.build_record(_source(), SAMPLE_REPORT, teacher,
                               {"backend": "deepseek", "model": "m"}, retries=2,
                               temperatures=(0.0, 0.7))
    assert seen == [0.0, 0.7]                    # stops at the first grounded re-roll
    assert rec.teacher["temperature"] == 0.7     # the kept attempt's temperature
    assert rec.quality["attempt"] == 1


def test_a_clean_first_attempt_is_recorded_at_the_gate_temperature():
    rec = distill.build_position_record(
        _source(), SAMPLE_REPORT,
        next(m for m in SAMPLE_REPORT["moves"] if m["san"] == "Nxd4"),
        lambda r, s, m, temperature=None: f"{m['san']} was costly.",
        {"backend": "deepseek", "model": "m"}, retries=1, temperatures=(0.0, 0.7),
    )
    assert rec.teacher["temperature"] == 0.0
    assert rec.quality["attempt"] == 0


def test_temperature_is_refused_for_backends_without_one():
    from training import teacher

    with pytest.raises(ValueError):
        teacher._temperature_kw("anthropic", 0.0)
    assert teacher._temperature_kw("anthropic", None) == {}


# --- resume ----------------------------------------------------------------------------

def _two_game_manifest(tmp_path: Path) -> Path:
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps([
        {"pgn": "a.pgn", "game_index": 0, "coached_side": "black"},
        {"pgn": "a.pgn", "game_index": 1, "coached_side": "black"},
    ]))
    return manifest


def _fake_teachers(monkeypatch, calls: list):
    monkeypatch.setattr(distill, "analyze_source", lambda src, depth: SAMPLE_REPORT)

    def game_teacher(r, s):
        calls.append("game")
        return "Your 17...Nxd4 was the blunder."

    monkeypatch.setattr(distill.teacher_mod, "make_teacher_fn", lambda *a, **k: game_teacher)
    monkeypatch.setattr(distill.teacher_mod, "make_position_teacher_fn",
                        lambda *a, **k: lambda r, s, m: f"{m['san']} was costly.")


def test_resume_skips_finished_games_and_redoes_a_torn_one(tmp_path, monkeypatch):
    manifest = _two_game_manifest(tmp_path)
    out = tmp_path / "raw.jsonl"
    calls: list = []
    _fake_teachers(monkeypatch, calls)
    assert distill.main(["--sources", str(manifest), "--out", str(out),
                         "--positions-per-game", "0"]) == 0
    assert len(calls) == 2

    # Simulate a kill after game #1's row was written but before its ledger line.
    ledger = distill.ledger_path(out)
    ledger.write_text(ledger.read_text().splitlines()[0] + "\n")
    first_key = json.loads(ledger.read_text())["key"]

    calls.clear()
    assert distill.main(["--sources", str(manifest), "--out", str(out),
                         "--positions-per-game", "0", "--resume"]) == 0
    assert len(calls) == 1                        # only the unfinished game is redone
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    keys = sorted(f"{r['source']['pgn']}#{r['source']['game_index']}" for r in rows)
    assert keys == ["a.pgn#0", "a.pgn#1"]        # no duplicate of the torn game
    assert first_key in keys
    assert len(ledger.read_text().splitlines()) == 2


def test_without_resume_the_run_starts_fresh(tmp_path, monkeypatch):
    manifest = _two_game_manifest(tmp_path)
    out = tmp_path / "raw.jsonl"
    calls: list = []
    _fake_teachers(monkeypatch, calls)
    for _ in range(2):
        assert distill.main(["--sources", str(manifest), "--out", str(out),
                             "--positions-per-game", "0"]) == 0
    assert len(out.read_text().splitlines()) == 2
    assert len(calls) == 4


def test_a_failed_game_is_left_out_of_the_ledger(tmp_path, monkeypatch, capsys):
    manifest = _two_game_manifest(tmp_path)
    out = tmp_path / "raw.jsonl"
    calls: list = []
    _fake_teachers(monkeypatch, calls)

    def analyze(src, depth):
        if src.game_index == 1:
            raise RuntimeError("engine died")
        return SAMPLE_REPORT

    monkeypatch.setattr(distill, "analyze_source", analyze)
    rc = distill.main(["--sources", str(manifest), "--out", str(out),
                       "--positions-per-game", "0", "--workers", "2"])
    assert rc == 2
    assert "a.pgn#1 FAILED" in capsys.readouterr().err
    assert [json.loads(l)["key"] for l in distill.ledger_path(out).read_text().splitlines()] \
        == ["a.pgn#0"]
