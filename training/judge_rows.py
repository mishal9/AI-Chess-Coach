"""Spot-check distilled rows with the LLM judge: a seeded random sample, scored on the rubric.

QC (``training.qc``) checks what a program can: cited moves, piece placements, castling,
roles. It cannot tell whether a sentence's chess reasoning is right. This scores a random
sample of rows with the same judge and rubric the held-out evaluation uses
(``eval.judge``), each row against the exact facts block it was written from, so the share
of rows with an error QC cannot see can be estimated before fine-tuning on them.

Rows are drawn with a fixed seed from the file given (normally the QC-filtered rows), so a
rerun judges the same rows. ``--same-as`` instead judges the rows whose keys an earlier
verdict file holds (optionally one ``--kind``), so regenerated rows can be scored on
exactly the positions an earlier spot-check scored, and ``--exclude`` leaves an earlier
verdict file's rows out of the random sample, so a fresh sample shares none of them. Verdicts are appended one per line as they arrive; ``--resume``
skips rows already judged.

Usage:
    python -m training.judge_rows data/distill/deepseek_qc.jsonl --n 200 --seed 20261007 \
        --out data/distill/deepseek_qc_judged.jsonl --max-judge-calls 200
    python -m training.judge_rows data/distill/deepseek_pos_v2_qc.jsonl \
        --same-as data/distill/deepseek_qc_judged.jsonl --kind position \
        --out data/distill/deepseek_pos_v2_judged.jsonl --max-judge-calls 150
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from eval import backends, judge
from training.qc import load_records, row_key
from training.schema import DistillRecord


def sample_rows(records: list[DistillRecord], n: int, seed: int) -> list[DistillRecord]:
    """``n`` rows drawn without replacement by ``seed``, in file order."""
    if n >= len(records):
        return list(records)
    picked = set(random.Random(seed).sample(range(len(records)), n))
    return [r for i, r in enumerate(records) if i in picked]


def same_rows(records: list[DistillRecord], verdicts: Path,
              kind: str | None = None) -> list[DistillRecord]:
    """The rows whose keys ``verdicts`` holds (of ``kind``, if given), in file order."""
    keys = {k for k, v in load_done(verdicts).items() if kind is None or v["kind"] == kind}
    return [r for r in records if row_key(r) in keys]


def judge_row(record: DistillRecord, backend, model: str | None) -> dict:
    """One verdict for one row, scored against the row's own facts block."""
    messages = judge.build_judge_messages(record.completion, record.facts)
    verdict = judge.parse_verdict(backend(messages, model=model))
    return {"key": row_key(record), "kind": record.kind, **verdict.to_dict()}


def load_done(out: Path) -> dict[str, dict]:
    done = {}
    if out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue  # a torn last line from a kill
            done[row["key"]] = row
    return done


def summarize(verdicts: list[dict]) -> str:
    lines = []
    for scope in ("all", "game", "position"):
        rows = [v for v in verdicts if scope == "all" or v["kind"] == scope]
        if not rows:
            continue
        n = len(rows)
        factual = Counter(v["scores"]["factual_correctness"] for v in rows)
        mean = sum(v["scores"]["factual_correctness"] for v in rows) / n
        below5 = sum(c for s, c in factual.items() if s < 5)
        below4 = sum(c for s, c in factual.items() if s < 4)
        overall = sum(v["overall"] for v in rows) / n
        lines.append(
            f"{scope:<9}n={n:<4} factual mean {mean:.2f}  <5: {below5} ({below5 / n:.0%})  "
            f"<4: {below4} ({below4 / n:.0%})  overall {overall:.2f}  "
            f"factual counts {dict(sorted(factual.items()))}"
        )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Judge a random sample of distilled rows.")
    parser.add_argument("rows", type=Path, help="raw record JSONL (normally QC-filtered)")
    parser.add_argument("--n", type=int, default=200, help="rows to sample")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--same-as", type=Path, default=None,
                        help="judge the rows keyed in this earlier verdict JSONL instead of "
                             "a random sample (--n and --seed are ignored)")
    parser.add_argument("--kind", choices=["game", "position"], default=None,
                        help="with --same-as: only that verdict file's rows of this kind")
    parser.add_argument("--exclude", type=Path, action="append", default=[],
                        help="leave the rows keyed in this verdict JSONL out of the random "
                             "sample, so it draws fresh rows (repeatable)")
    parser.add_argument("--out", type=Path, required=True, help="verdict JSONL")
    parser.add_argument("--judge-model", default=None,
                        help=f"default: {backends.DEFAULT_ANTHROPIC_MODEL}")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--resume", action="store_true",
                        help="keep verdicts already in --out and judge only the rest")
    parser.add_argument("--max-judge-calls", type=int, default=50,
                        help="refuse to start if more rows than this need judging")
    return parser


def main(argv: list[str] | None = None, backend=None) -> int:
    args = build_parser().parse_args(argv)
    backend = backend or backends.anthropic_backend
    records = load_records(args.rows)
    excluded = {k for path in args.exclude for k in load_done(path)}
    records = [r for r in records if row_key(r) not in excluded]
    if args.same_as:
        sample = same_rows(records, args.same_as, args.kind)
    else:
        sample = sample_rows(records, args.n, args.seed)

    if not args.resume:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text("", encoding="utf-8")
    done = load_done(args.out)
    todo = [r for r in sample if row_key(r) not in done]
    if len(todo) > args.max_judge_calls:
        print(f"Refusing to start: {len(todo)} rows to judge exceeds --max-judge-calls "
              f"{args.max_judge_calls}.", file=sys.stderr)
        return 1

    model = args.judge_model or backends.DEFAULT_ANTHROPIC_MODEL
    print(f"Judging {len(todo)} rows ({len(done)} already judged) with {model}.",
          file=sys.stderr)
    failed = 0
    with args.out.open("a", encoding="utf-8") as fh, \
            ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(judge_row, r, backend, args.judge_model): r for r in todo}
        for i, future in enumerate(as_completed(futures), 1):
            try:
                verdict = future.result()
            except Exception as exc:  # one bad verdict must not lose the rest
                failed += 1
                print(f"[{i}/{len(todo)}] {row_key(futures[future])} FAILED: {exc!r}",
                      file=sys.stderr)
                continue
            fh.write(json.dumps(verdict, ensure_ascii=False) + "\n")
            fh.flush()
            done[verdict["key"]] = verdict
            print(f"[{i}/{len(todo)}] {verdict['key']}: factual "
                  f"{verdict['scores']['factual_correctness']}", file=sys.stderr)

    keys = {row_key(r) for r in sample}
    print(summarize([v for k, v in done.items() if k in keys]))
    if failed:
        print(f"{failed} row(s) failed; rerun with --resume.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
