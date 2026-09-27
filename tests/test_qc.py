"""Tests for the distillation quality-control script and the DeepSeek teacher backend.

Everything runs offline: the PGN is replayed with python-chess, and the DeepSeek HTTP call
is replaced with a fake, so no engine, key or network is needed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from training import qc, teacher
from training.schema import DistillRecord

PGN = """[Event "t"]
[White "a"]
[Black "b"]
[Result "*"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Bxc6 dxc6 *
"""

FACTS = (
    "You are coaching the BLACK player.\n\nThe moment:\n"
    "- 3...a6?! (inaccuracy): the engine preferred Nf6; cost about 5% win probability."
)
GOOD = (
    "On 3...a6 you played a natural-looking move, but the engine preferred Nf6. "
    "Developing a piece keeps your options open and prepares to castle, which is the "
    "reusable idea here. Something to work on: finish development before spending "
    "tempi on pawn moves, and ask what each move does for your pieces. " * 2
)


@pytest.fixture
def corpus_dir(tmp_path: Path) -> Path:
    (tmp_path / "corpus.pgn").write_text(PGN, encoding="utf-8")
    return tmp_path


def _record(completion: str, kind: str = "position", **source) -> DistillRecord:
    from coach import prompts

    system = prompts.POSITION_SYSTEM_PROMPT if kind == "position" else prompts.SYSTEM_PROMPT
    return DistillRecord(
        source={"pgn": "corpus.pgn", "game_index": 0, "coached_side": "black",
                "move_number": 3, **source},
        coached_side="black",
        facts=FACTS,
        prompt=[{"role": "system", "content": system},
                {"role": "user", "content": f"Coach this.\n\n{FACTS}"}],
        completion=completion,
        teacher={"backend": "deepseek", "model": "m"},
        kind=kind,
    )


def test_replay_report_has_sides_san_and_fen(corpus_dir):
    report = qc.replay_report(corpus_dir / "corpus.pgn", 0)
    moves = report["moves"]
    assert [m["side"] for m in moves[:3]] == ["white", "black", "white"]
    assert moves[2]["san"] == "Nf3"
    assert moves[0]["fen_before"].startswith("rnbqkbnr/pppppppp")


@pytest.mark.parametrize("text,expected", [
    ("", ["empty"]),
    ("Too short.", ["too_short"]),
    ("<think>hmm</think>" + "x" * 500, ["reasoning_trace"]),
    ("Sure, here is your coaching. " + "x" * 500, ["chat_preamble"]),
    ("x" * 5000, ["too_long"]),
    ("A steady, ordinary coaching paragraph. " * 20, []),
])
def test_structure_problems(text, expected):
    assert qc.structure_problems(text) == expected


def test_clean_row_passes(corpus_dir):
    [result] = qc.run_qc([_record(GOOD)], corpus_dir)
    assert result["passed"] is True
    assert result["violations"] == [] and result["structure"] == []


def test_hallucinated_move_fails_grounding(corpus_dir):
    [result] = qc.run_qc([_record(GOOD + " You should have played Qh5 there.")], corpus_dir)
    assert result["grounded"] is False and result["hallucinated"] == ["Qh5"]
    assert result["passed"] is False


def test_invented_piece_placement_fails_claims(corpus_dir):
    text = GOOD + " Notice your rook on h5 was doing nothing."
    [result] = qc.run_qc([_record(text)], corpus_dir)
    assert "invented_placement" in result["violations"]
    assert result["passed"] is False


def test_duplicate_completions_are_flagged(corpus_dir):
    a, b = _record(GOOD, move_number=3), _record(GOOD, move_number=4)
    results = qc.run_qc([a, b], corpus_dir)
    assert all("duplicate_completion" in r["integrity"] for r in results)
    assert not any(r["passed"] for r in results)


def test_summarize_counts_per_kind(corpus_dir):
    rows = [_record(GOOD, "position"), _record("", "game", move_number=1)]
    summary = qc.summarize(qc.run_qc(rows, corpus_dir))
    assert summary["all"]["n"] == 2 and summary["all"]["passed"] == 1
    assert summary["position"]["passed"] == 1 and summary["game"]["passed"] == 0
    assert summary["game"]["structure_problems"] == {"empty": 1}


def test_passed_out_keeps_only_passing_rows(corpus_dir, tmp_path):
    rows = tmp_path / "rows.jsonl"
    good = _record(GOOD)
    bad = _record(GOOD + " Notice your rook on h5 was doing nothing.", move_number=4)
    rows.write_text("".join(json.dumps(r.to_dict()) + "\n" for r in (good, bad)),
                    encoding="utf-8")
    kept = tmp_path / "kept.jsonl"
    qc.main([str(rows), "--corpus-dir", str(corpus_dir), "--passed-out", str(kept)])
    [line] = kept.read_text(encoding="utf-8").splitlines()
    assert json.loads(line) == good.to_dict()


def test_paired_baseline_compares_shared_rows_only(corpus_dir, tmp_path, capsys):
    mine, base = tmp_path / "mine.jsonl", tmp_path / "base.jsonl"
    mine.write_text(json.dumps(_record(GOOD).to_dict()) + "\n", encoding="utf-8")
    base.write_text(
        json.dumps(_record(GOOD + " Different words.").to_dict()) + "\n"
        + json.dumps(_record(GOOD + " Other.", move_number=9).to_dict()) + "\n",
        encoding="utf-8",
    )
    qc.main([str(mine), "--baseline", str(base), "--corpus-dir", str(corpus_dir)])
    assert "Paired on 1 shared source rows" in capsys.readouterr().out


# --- DeepSeek backend --------------------------------------------------------------

class _Resp:
    def __init__(self, status: int, payload: dict | None = None):
        self.status_code, self._payload, self.text = status, payload or {}, "err"

    def json(self):
        return self._payload

    def raise_for_status(self):
        raise RuntimeError(f"HTTP {self.status_code}")


def _ok(content: str) -> _Resp:
    return _Resp(200, {
        "model": "deepseek-v4-pro-0813",
        "choices": [{"message": {"content": content, "reasoning_content": "secret trace"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20,
                  "completion_tokens_details": {"reasoning_tokens": 5}},
    })


@pytest.fixture
def deepseek_env(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "k")
    monkeypatch.setattr(teacher.time, "sleep", lambda s: None)
    monkeypatch.setattr(teacher, "DEEPSEEK_THINKING", None)
    teacher.DEEPSEEK_USAGE.update(calls=0, prompt_tokens=0, completion_tokens=0,
                                  reasoning_tokens=0, models=set())


def test_deepseek_returns_content_only_and_tallies_usage(deepseek_env, monkeypatch):
    seen = {}

    def post(url, headers, json, timeout):
        seen.update(url=url, auth=headers["Authorization"], body=json)
        return _ok("  the coaching  ")

    monkeypatch.setattr(teacher.requests, "post", post)
    out = teacher.deepseek_backend([{"role": "user", "content": "hi"}])
    assert out == "the coaching"                       # reasoning_content never returned
    assert seen["url"].endswith("/chat/completions") and seen["auth"] == "Bearer k"
    assert seen["body"]["model"] == "deepseek-v4-pro" and "thinking" not in seen["body"]
    u = teacher.DEEPSEEK_USAGE
    assert (u["calls"], u["prompt_tokens"], u["reasoning_tokens"]) == (1, 10, 5)
    assert u["models"] == {"deepseek-v4-pro-0813"}


def test_deepseek_sends_thinking_only_when_set(deepseek_env, monkeypatch):
    bodies = []
    monkeypatch.setattr(teacher.requests, "post",
                        lambda url, headers, json, timeout: bodies.append(json) or _ok("x"))
    monkeypatch.setattr(teacher, "DEEPSEEK_THINKING", "disabled")
    teacher.deepseek_backend([{"role": "user", "content": "hi"}])
    assert bodies[0]["thinking"] == {"type": "disabled"}


def test_deepseek_retries_429_then_succeeds(deepseek_env, monkeypatch):
    replies = iter([_Resp(429), _Resp(503), _ok("finally")])
    monkeypatch.setattr(teacher.requests, "post", lambda *a, **k: next(replies))
    assert teacher.deepseek_backend([{"role": "user", "content": "hi"}]) == "finally"


def test_deepseek_client_error_raises_immediately(deepseek_env, monkeypatch):
    monkeypatch.setattr(teacher.requests, "post", lambda *a, **k: _Resp(400))
    with pytest.raises(RuntimeError, match="400"):
        teacher.deepseek_backend([{"role": "user", "content": "hi"}])


def test_deepseek_without_key_exits(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(teacher.backends, "_load_dotenv", lambda *a, **k: None)
    with pytest.raises(SystemExit, match="DEEPSEEK_API_KEY"):
        teacher.deepseek_backend([{"role": "user", "content": "hi"}])


# --- the frozen v2-era prompt ------------------------------------------------------

def test_v2_era_prompt_matches_the_committed_v2_training_rows():
    from training.prompts_v2 import V2_ERA_SYSTEM_PROMPT

    rows = [json.loads(l) for l in
            (Path(__file__).parent.parent / "training/datasets/v2/train.jsonl")
            .read_text(encoding="utf-8").splitlines() if l.strip()]
    game_systems = {r["messages"][0]["content"] for r in rows
                    if "Objective engine summary" in r["messages"][1]["content"]}
    assert game_systems == {V2_ERA_SYSTEM_PROMPT}


def test_n2_coach_swaps_in_the_v2_era_prompt(monkeypatch):
    from tests.test_coach import SAMPLE_REPORT
    from training import n2_eval
    from training.prompts_v2 import V2_ERA_SYSTEM_PROMPT

    seen = {}
    monkeypatch.setattr(n2_eval.teacher, "deepseek_backend",
                        lambda messages, model=None: seen.update(m=messages, model=model) or "ok")
    n2_eval.make_deepseek_coach("deepseek-v4-pro", "v2-era")(SAMPLE_REPORT, "black")
    assert seen["m"][0]["content"] == V2_ERA_SYSTEM_PROMPT and seen["model"] == "deepseek-v4-pro"
    n2_eval.make_deepseek_coach("deepseek-v4-pro", "current")(SAMPLE_REPORT, "black")
    assert seen["m"][0]["content"] != V2_ERA_SYSTEM_PROMPT
