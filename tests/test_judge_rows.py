"""Tests for the judge spot-check of distilled rows. The judge is a fake; no API calls."""

from __future__ import annotations

import json

from tests.test_qc import GOOD, _record
from training import judge_rows

VERDICT = ('{"factual_correctness": %d, "clarity": 5, "actionability": 4, '
           '"identifies_key_mistake": 5, "rationale": "r"}')


def _rows(tmp_path, n=10):
    path = tmp_path / "rows.jsonl"
    path.write_text("".join(json.dumps(_record(GOOD, move_number=i).to_dict()) + "\n"
                            for i in range(n)), encoding="utf-8")
    return path


def test_sample_is_seeded_and_in_file_order(tmp_path):
    records = judge_rows.load_records(_rows(tmp_path))
    a = judge_rows.sample_rows(records, 4, seed=1)
    assert a == judge_rows.sample_rows(records, 4, seed=1)
    nums = [r.source["move_number"] for r in a]
    assert nums == sorted(nums) and len(nums) == 4


def test_judge_sees_the_rows_own_facts(tmp_path):
    seen = []

    def backend(messages, model=None):
        seen.append(messages[-1]["content"])
        return VERDICT % 5

    rec = judge_rows.load_records(_rows(tmp_path, 1))[0]
    out = judge_rows.judge_row(rec, backend, None)
    assert rec.facts in seen[0] and rec.completion in seen[0]
    assert out["scores"]["factual_correctness"] == 5 and out["kind"] == "position"


def test_resume_judges_only_the_rest(tmp_path, capsys):
    rows, out = _rows(tmp_path), tmp_path / "v.jsonl"
    calls = []

    def backend(messages, model=None):
        calls.append(1)
        return VERDICT % (3 if len(calls) == 1 else 5)

    args = [str(rows), "--n", "6", "--seed", "2", "--out", str(out), "--workers", "1"]
    assert judge_rows.main(args, backend=backend) == 0
    assert len(calls) == 6
    assert judge_rows.main(args + ["--resume"], backend=backend) == 0
    assert len(calls) == 6                      # nothing left to judge
    assert "<4: 1" in capsys.readouterr().out


def test_spend_guard(tmp_path):
    args = [str(_rows(tmp_path)), "--n", "6", "--out", str(tmp_path / "v.jsonl"),
            "--max-judge-calls", "5"]
    assert judge_rows.main(args, backend=lambda m, model=None: VERDICT % 5) == 1
