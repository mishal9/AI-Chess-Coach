"""Do a file's defence claims stay within what each row's facts state?

For every resolvable "X defends Y" claim (``eval.claims.iter_defence_claims``): ``stated``
if the row's facts name X as Y's defender, ``unstated`` if it is true on the board but no
facts line says so, ``false`` if the board refutes it. A teacher with board tools must not
raise the unstated share: the student sees only the facts and has no tools to check with.

Usage: python scripts/claim_support.py data/distill/raw_deepseek_pos_v5.jsonl [...]
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from eval import claims
from training.qc import load_records


def main(paths: list[str]) -> None:
    for path in paths:
        total = Counter()
        rows = load_records(Path(path))
        for record in rows:
            total.update(claims.defence_claim_support(record.completion, record.facts))
        n = sum(total.values())
        share = ", ".join(f"{k} {total[k]} ({total[k] / max(n, 1):.0%})"
                          for k in ("stated", "unstated", "false"))
        print(f"{path}: {len(rows)} rows, {n} defence claims: {share}")


if __name__ == "__main__":
    main(sys.argv[1:])
