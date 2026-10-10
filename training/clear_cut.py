"""Keep the position rows whose facts show a clear-cut tactic.

A property of the *position*, read from the row's facts block before its coaching is
looked at. A row is clear-cut if the facts show either:

- the opponent's best reply after the move captures at once (the first move of "Engine's
  best line after your move" is marked "takes your ..."), or
- the move played leaves one of the student's pieces attacked with no defender ("After
  your move, your pieces under attack: ... defenders 0").

These are the mistakes with a simple, concrete explanation in the facts, so there is less
for the teacher to invent. Clear-cut does not mean accurate: QC and a judged sample still
measure what is left. Pre-registered in
``docs/experiments/2026-10-08-clear-cut-position-rows.md``.

Game rows and position rows without these fact lines are never clear-cut.

Usage:
    python -m training.clear_cut data/distill/deepseek_pos_v3b_qc.jsonl \
        --out data/distill/deepseek_pos_v3b_clear.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from training.qc import load_records

_REPLY_CAPTURES = re.compile(r"^- Engine's best line after your move: \S+ \(takes your ",
                             re.MULTILINE)
_LEFT_UNDEFENDED = re.compile(r"^- After your move, your pieces under attack: .*\bdefenders 0\)",
                              re.MULTILINE)


def reply_captures(facts: str) -> bool:
    return bool(_REPLY_CAPTURES.search(facts))


def left_undefended(facts: str) -> bool:
    return bool(_LEFT_UNDEFENDED.search(facts))


def is_clear_cut(facts: str) -> bool:
    return reply_captures(facts) or left_undefended(facts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Keep position rows with a clear-cut tactic.")
    parser.add_argument("rows", type=Path, help="raw record JSONL (normally QC-filtered)")
    parser.add_argument("--out", type=Path, required=True, help="clear-cut rows JSONL")
    args = parser.parse_args(argv)

    records = load_records(args.rows)
    kept = [r for r in records if r.kind == "position" and is_clear_cut(r.facts)]
    positions = sum(r.kind == "position" for r in records)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for rec in kept:
            fh.write(json.dumps(rec.to_dict(), ensure_ascii=False) + "\n")
    print(f"{len(kept)} of {positions} position rows are clear-cut "
          f"({len(kept) / max(positions, 1):.0%}) -> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
