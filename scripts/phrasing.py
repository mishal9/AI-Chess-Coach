"""Phrasing variety of training rows: recurring openings, stock phrases and distinct n-grams.

A teacher that writes every row from the same template teaches the student the template.
Reported per chat-format train file (the assistant turn of each row).

Usage:
    python scripts/phrasing.py training/datasets/sweep-v5-G-1700/train.jsonl \\
        training/datasets/sweep-v5-M-1700/train.jsonl
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter

STOCK = ("the lesson here", "two things to work on", "a good habit", "work on this",
         "the key idea", "the reusable", "the engine's line shows", "to work on:",
         "before you move", "ask yourself")


def texts(path: str) -> list[str]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line)["messages"][-1]["content"] for line in fh if line.strip()]


def distinct(rows: list[str], n: int) -> float:
    grams = Counter()
    for t in rows:
        words = re.findall(r"[a-z']+", t.lower())
        grams.update(zip(*(words[i:] for i in range(n))))
    return len(grams) / max(sum(grams.values()), 1)


def report(path: str) -> None:
    rows = texts(path)
    n = len(rows)
    openers = Counter(" ".join(re.findall(r"[A-Za-z']+", t)[:3]).lower() for t in rows)
    print(f"{path}: {n} rows, median {sorted(len(t.split()) for t in rows)[n // 2]} words")
    print(f"  distinct 3-grams {distinct(rows, 3):.3f}, 4-grams {distinct(rows, 4):.3f}")
    top = ", ".join(f"'{o}' {c / n:.0%}" for o, c in openers.most_common(5))
    print(f"  most common first three words: {top}")
    stock = ", ".join(f"'{s}' {sum(s in t.lower() for t in rows) / n:.0%}" for s in STOCK)
    print(f"  rows containing: {stock}")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        report(p)
