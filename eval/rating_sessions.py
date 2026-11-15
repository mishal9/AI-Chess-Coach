"""Turn saved rating sessions into the per-rater CSVs that ``eval.human_rating`` reads.

Both stores keep one JSON state per rater: ``{tag, level, started, updated, scores}`` with
``scores = {item_id: {axis: 1-5, comment}}``. Export them as a JSON list, one object per
rater, each either that state or a row holding it under ``state`` (Supabase) or ``data``
(the claude.ai artifact database). For Supabase:

    select json_agg(json_build_object('label', r.label, 'state', s.state))
    from rating.sessions s join rating.raters r using (token) where s.round = 'round2';

Then:

    python -m eval.rating_sessions sessions.json --out eval/human/round2/returned

writes ``ratings_<tag>.csv`` per rater (the same format as the page's Download button) and
prints the ``--rater`` arguments for the analysis.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
from pathlib import Path

from eval.rubric import RUBRIC_AXES


def state_of(row: dict) -> dict:
    return row.get("state") or row.get("data") or row


def to_csv(state: dict, round_name: str) -> str:
    buf = io.StringIO()
    buf.write(f"# rater={state.get('tag', '')} level={state.get('level', '')} round={round_name}\n")
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["item_id", *RUBRIC_AXES, "comment"])
    for item_id in sorted(state.get("scores", {})):
        s = state["scores"][item_id]
        writer.writerow([item_id, *(s.get(a, "") for a in RUBRIC_AXES), s.get("comment", "")])
    return buf.getvalue()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("sessions", type=Path, help="JSON list of saved sessions")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--round", default="round2")
    args = parser.parse_args(argv)

    rows = json.loads(args.sessions.read_text(encoding="utf-8")) or []
    args.out.mkdir(parents=True, exist_ok=True)
    specs, seen = [], set()
    for row in rows:
        state = state_of(row)
        base = re.sub(r"[^A-Za-z0-9_-]", "", state.get("tag") or row.get("label") or "rater") or "rater"
        name, n = base, 2
        while name in seen:
            name, n = f"{base}{n}", n + 1
        seen.add(name)
        path = args.out / f"ratings_{name}.csv"
        path.write_text(to_csv(state, args.round), encoding="utf-8")
        done = sum(1 for s in state.get("scores", {}).values() if all(s.get(a) for a in RUBRIC_AXES))
        print(f"{path}: {done} items fully scored")
        specs.append(f"--rater {name}={path}")
    print(" ".join(specs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
