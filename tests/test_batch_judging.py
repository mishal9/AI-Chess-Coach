"""Batch judging (Message Batches API). The client is a fake; no API calls."""

from __future__ import annotations

import json
from types import SimpleNamespace as NS

from eval import backends
from tests.test_judge_rows import VERDICT, _rows
from training import judge_rows

MESSAGES = [{"role": "system", "content": "SYS"}, {"role": "user", "content": "facts %d"}]


def _messages(n):
    return [[MESSAGES[0], {"role": "user", "content": f"facts {i}"}] for i in range(n)]


class FakeBatches:
    """Ends on the second poll. ``outcomes`` maps a request index to a non-success type."""

    def __init__(self, outcomes=None):
        self.created, self.polls, self.outcomes = [], 0, outcomes or {}

    def create(self, requests):
        self.created.append(requests)
        return NS(id="msgbatch_1")

    def retrieve(self, batch_id):
        self.polls += 1
        counts = NS(processing=1, succeeded=0, errored=0)
        return NS(processing_status="ended" if self.polls >= 2 else "in_progress",
                  request_counts=counts)

    def results(self, batch_id):
        requests = self.created[-1] if self.created else self.saved
        for i, req in reversed(list(enumerate(requests))):  # results come in any order
            kind = self.outcomes.get(i, "succeeded")
            if kind == "succeeded":
                msg = NS(content=[NS(type="text", text=req["params"]["messages"][0]["content"])])
                yield NS(custom_id=req["custom_id"], result=NS(type="succeeded", message=msg))
            else:
                yield NS(custom_id=req["custom_id"], result=NS(type=kind, error="boom"))


def _client(batches):
    return NS(messages=NS(batches=batches))


def test_batched_requests_are_the_direct_requests_and_come_back_in_order():
    batches = FakeBatches()
    out = backends.anthropic_batch(_messages(3), client=_client(batches), poll_seconds=0)
    sent = [r["params"] for r in batches.created[0]]
    assert sent == [backends.anthropic_params(m) for m in _messages(3)]
    assert out == ["facts 0", "facts 1", "facts 2"]


def test_a_failed_request_comes_back_as_an_exception_in_its_place():
    batches = FakeBatches(outcomes={1: "errored", 2: "expired"})
    out = backends.anthropic_batch(_messages(3), client=_client(batches), poll_seconds=0)
    assert out[0] == "facts 0"
    assert all(isinstance(x, Exception) for x in out[1:])


def test_an_interrupted_run_polls_the_saved_batch_instead_of_paying_twice(tmp_path):
    state = tmp_path / "out.batch.json"
    first = FakeBatches()
    backends.anthropic_batch(_messages(2), client=_client(first), poll_seconds=0,
                             state_path=state)
    assert not state.exists()  # removed once the results are read

    # Simulate a kill after submission: the state file names a batch for these requests.
    params = [backends.anthropic_params(m) for m in _messages(2)]
    state.write_text(json.dumps({"batch_id": "msgbatch_1",
                                 "fingerprint": json.dumps(params, sort_keys=True)}))
    again = FakeBatches()
    again.saved = first.created[0]
    out = backends.anthropic_batch(_messages(2), client=_client(again), poll_seconds=0,
                                   state_path=state)
    assert again.created == []
    assert out == ["facts 0", "facts 1"]


def test_a_saved_batch_for_other_requests_is_not_reused(tmp_path):
    state = tmp_path / "out.batch.json"
    state.write_text(json.dumps({"batch_id": "old", "fingerprint": "something else"}))
    batches = FakeBatches()
    backends.anthropic_batch(_messages(2), client=_client(batches), poll_seconds=0,
                             state_path=state)
    assert len(batches.created) == 1


def test_judge_rows_batch_writes_verdicts_and_counts_failures(tmp_path):
    rows = _rows(tmp_path, n=4)
    out = tmp_path / "v.jsonl"

    def batch_fn(requests, model=None, state_path=None, progress=None):
        return [VERDICT % 4, RuntimeError("expired"), VERDICT % 5, VERDICT % 3]

    args = [str(rows), "--n", "4", "--out", str(out), "--batch"]
    assert judge_rows.main(args, batch_fn=batch_fn) == 2
    verdicts = [json.loads(l) for l in out.read_text().splitlines()]
    assert len(verdicts) == 3

    calls = []

    def retry(requests, model=None, state_path=None, progress=None):
        calls.append(len(requests))
        return [VERDICT % 5] * len(requests)

    assert judge_rows.main(args + ["--resume"], batch_fn=retry) == 0
    assert calls == [1]  # only the failed row is re-sent


def test_rejudge_batch_fills_every_rubric_and_keeps_the_rest_on_failure(tmp_path, monkeypatch):
    import pytest

    rejudge = pytest.importorskip("eval.rejudge")
    games = [{"pgn": f"g{i}.pgn", "game_index": 0, "coached_side": "white",
              "coaching": f"text {i}", "grounding": {"score": 1.0, "grounded": True},
              "identifies_worst_move": True} for i in range(3)]
    report = {"judge_model": None, "depth": 18, "games": games}
    monkeypatch.setattr(rejudge, "analyze_manifest", lambda path, depth: [
        {"pgn": g["pgn"], "report": {}} for g in games])
    monkeypatch.setattr(rejudge, "report_judge_messages",
                        lambda text, rep, side: [{"role": "user", "content": text}])
    out_path = tmp_path / "r.json"

    def flaky(requests, model=None, state_path=None, progress=None):
        return [VERDICT % 4, RuntimeError("expired"), VERDICT % 5]

    with pytest.raises(rejudge.BatchJudgingIncomplete):
        rejudge.rejudge(report, judge="anthropic", batch=True, batch_fn=flaky,
                        out_path=out_path)
    saved = json.loads(out_path.read_text())
    assert [("rubric" in g) for g in saved["games"]] == [True, False, True]

    sent = []

    def ok(requests, model=None, state_path=None, progress=None):
        sent.append([r[0]["content"] for r in requests])
        return [VERDICT % 3] * len(requests)

    out = rejudge.rejudge(report, judge="anthropic", batch=True, batch_fn=ok,
                          out_path=out_path)
    assert sent == [["text 1"]]  # only the missing game is re-sent
    assert all(g["judged_by"] == "claude-opus-4-8" for g in out["games"])
    assert out["aggregate"]["rubric_axis_means"]["factual_correctness"] == round(
        (4 + 3 + 5) / 3, 2)
