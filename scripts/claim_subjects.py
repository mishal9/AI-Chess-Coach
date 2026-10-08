"""Who is the subject of each attack or defence claim in a file of position rows?

Counts active "defends / protects / guards / supports / attacks" verbs with a piece or
square as object (not hypothetical, negated or passive) by what stands just before them: a piece named with its square ("your
queen on d5"), a piece without one ("your queen"), a pronoun ("it", "which", "that",
"this", "they") or a bare move ("Qd5"). The 8 Oct prompt rule asks for the first; this
measures how often the teacher complies. Pre-registered in
``docs/experiments/2026-10-08-explicit-defence-claims.md``.

Usage: python scripts/claim_subjects.py data/distill/raw_deepseek_pos_v4.jsonl
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

from eval import claims
from training.qc import load_records

# Only pairings: the verb's object is a piece or a square ("attacks the c3 pawn",
# "defends f2"), not "under attack" or "defending passively".
VERB = re.compile(rf"\b(?:defend|protect|guard|support|attack)(?:s|ed|ing)?\b(?!\s+by\b)"
                  rf"(?=\s+(?:[\w'-]+\s+){{0,2}}?(?:(?:{claims._PIECE_NAMES})s?\b|"
                  rf"[a-h][1-8]\b))", re.I)
PRONOUN = re.compile(r"\b(?:it|which|that|this|they)\s+(?:\w+\s+){0,2}\Z", re.I)
MOVE = re.compile(r"\b[KQRBN][a-h]?[1-8]?x?[a-h][1-8][+#]?\**\s+(?:\w+\s+){0,2}\Z")
SQUARED = re.compile(rf"\b(?:{claims._PIECE_NAMES})\s+(?:on|at)\s+[a-h][1-8]\s+"
                     rf"(?:\w+\s+){{0,2}}\Z|\b[a-h][1-8][- ](?:{claims._PIECE_NAMES})\s+"
                     rf"(?:\w+\s+){{0,2}}\Z", re.I)
PIECE = re.compile(rf"\b(?:{claims._PIECE_NAMES})\s+(?:\w+\s+){{0,2}}\Z", re.I)


def subjects(text: str) -> Counter:
    counts = Counter()
    starts = [0] + [m.end() for m in claims._SENTENCE_BREAK_RE.finditer(text)]
    for s, e in zip(starts, starts[1:] + [len(text)]):
        sentence = text[s:e]
        for verb in VERB.finditer(sentence):
            before = sentence[: verb.start()]
            if (claims._MODAL_RE.search(before) or claims._NEGATION_RE.search(before)
                    or claims._PASSIVE_RE.search(before)):
                continue
            counts["move" if MOVE.search(before) else "pronoun" if PRONOUN.search(before)
                   else "piece on square" if SQUARED.search(before)
                   else "piece" if PIECE.search(before) else "other"] += 1
    return counts


def main(path: str) -> None:
    total = Counter()
    for record in load_records(Path(path)):
        total += subjects(record.completion)
    n = sum(total.values())
    vague = total["pronoun"] + total["move"]
    print(f"{path}: {n} claims; pronoun or bare move {vague} ({vague / max(n, 1):.0%}); "
          f"{dict(total.most_common())}")


if __name__ == "__main__":
    main(sys.argv[1])
