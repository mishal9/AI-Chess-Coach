"""Compare two ``eval.run`` reports — a baseline vs a fine-tuned coach — on the same held-out set.

Prints three views:
  1. **Overall** — every metric, baseline → candidate, with the delta.
  2. **Per bucket** — the six mistake profiles, so you see *where* the fine-tune helped
     (the whole point is clean_draw's grounding climbing off the baseline's 0.38).
  3. **Paired per-game** — both reports score the *same* games, so we can count how many
     games got a better / equal / worse factual score. A paired read is far more trustworthy
     on a small set than comparing two independent means.

Usage:
    python -m eval.compare eval/reports/baseline_29g_2026-07-10.json eval/reports/v1_finetuned.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

AXES = ["factual_correctness", "clarity", "actionability", "identifies_key_mistake"]
BUCKETS = ["clean_draw", "slow_loss", "inaccuracies", "two_mistakes", "one_blunder", "multi_blunder"]

# metric key -> (label, is_percentage)
_METRICS = [
    ("grounding", "grounding", False),
    ("grounded_pct", "grounded %", True),
    ("worst_pct", "worst-move %", True),
    ("factual_correctness", "factual", False),
    ("clarity", "clarity", False),
    ("actionability", "actionability", False),
    ("identifies_key_mistake", "key-mistake", False),
    ("overall", "overall", False),
]


def load_games(path: str | Path) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))["games"]


def aggregate(games: list[dict]) -> dict:
    """Mean of every metric over ``games``."""
    n = len(games)
    if n == 0:
        return {}
    m = {
        "grounding": sum(g["grounding"]["score"] for g in games) / n,
        "grounded_pct": sum(1 for g in games if g["grounding"]["grounded"]) / n * 100,
        "worst_pct": sum(1 for g in games if g["identifies_worst_move"]) / n * 100,
    }
    # --no-judge reports carry no rubric; grounding-only comparisons are still valid.
    if all("rubric" in g for g in games):
        m["overall"] = sum(g["rubric"]["overall"] for g in games) / n
        for a in AXES:
            m[a] = sum(g["rubric"]["scores"][a] for g in games) / n
    return m


def has_rubric(*aggs: dict) -> bool:
    """True only when every aggregate carries judged metrics."""
    return all("overall" in a for a in aggs)


def by_bucket(games: list[dict]) -> dict[str, list[dict]]:
    d: dict[str, list[dict]] = {}
    for g in games:
        d.setdefault(Path(g["pgn"]).stem, []).append(g)
    return d


def paired_factual(base: list[dict], cand: list[dict]) -> dict:
    """Count games whose factual score went up / stayed / went down, game-for-game.

    Both reports come from the same manifest in the same order, so games are paired by
    position. Pairs whose ``pgn`` doesn't line up are skipped as a safety check.
    """
    up = same = down = 0
    for b, c in zip(base, cand):
        if "rubric" not in b or "rubric" not in c:
            continue
        if b["pgn"] != c["pgn"] or b.get("coached_side") != c.get("coached_side"):
            continue
        d = c["rubric"]["scores"]["factual_correctness"] - b["rubric"]["scores"]["factual_correctness"]
        up += d > 0
        down += d < 0
        same += d == 0
    return {"better": up, "same": same, "worse": down}


def _fmt(v: float, pct: bool) -> str:
    return f"{v:5.1f}%" if pct else f"{v:5.2f}"


def _delta(b: float, c: float, pct: bool) -> str:
    d = c - b
    unit = "pp" if pct else ""
    sign = "+" if d >= 0 else ""
    return f"{sign}{d:.1f}{unit}" if pct else f"{sign}{d:.2f}"


def render(base: list[dict], cand: list[dict], base_name="baseline", cand_name="candidate") -> str:
    ab, ac = aggregate(base), aggregate(cand)
    out: list[str] = []
    out.append(f"eval.compare  ·  {base_name}  →  {cand_name}   ({len(base)} vs {len(cand)} games)")
    out.append("")

    # 1) overall
    out.append(f"{'metric':<14}{base_name[:9]:>10}{cand_name[:9]:>10}{'Δ':>9}")
    out.append("─" * 43)
    for key, label, pct in _METRICS:
        if key not in ab or key not in ac:
            continue
        out.append(f"{label:<14}{_fmt(ab[key],pct):>10}{_fmt(ac[key],pct):>10}{_delta(ab[key],ac[key],pct):>9}")

    # 2) per bucket (grounding / factual / overall)
    bb, bc = by_bucket(base), by_bucket(cand)
    out.append("")
    judged = has_rubric(ab, ac)
    header = f"{'bucket':<14}{'n':>3}{'ground Δ':>11}"
    if judged:
        header += f"{'factual Δ':>11}{'overall Δ':>11}"
    out.append(header)
    out.append("─" * (50 if judged else 28))
    for b in BUCKETS:
        if b not in bb:
            continue
        mb, mc = aggregate(bb[b]), aggregate(bc.get(b, []))
        if not mc:
            continue
        star = "  ←" if b == "clean_draw" else ""
        row = f"{b:<14}{len(bb[b]):>3}{_delta(mb['grounding'],mc['grounding'],False):>11}"
        if has_rubric(mb, mc):
            row += (f"{_delta(mb['factual_correctness'],mc['factual_correctness'],False):>11}"
                    f"{_delta(mb['overall'],mc['overall'],False):>11}")
        out.append(row + star)

    # 3) paired + verdict — judged metrics only
    if not has_rubric(ab, ac):
        out.append("")
        out.append("(grounding-only reports — rubric, paired factual, and verdict skipped)")
        return "\n".join(out)

    p = paired_factual(base, cand)
    out.append("")
    out.append(f"paired factual (same games): {p['better']} better · {p['same']} same · {p['worse']} worse")

    beat_f = ac["factual_correctness"] > ab["factual_correctness"]
    beat_o = ac["overall"] > ab["overall"]
    verdict = "BEATS baseline" if (beat_f and beat_o) else \
              "mixed" if (beat_f or beat_o) else "does NOT beat baseline"
    out.append("")
    out.append(f"verdict: {cand_name} {verdict}  "
               f"(factual {_delta(ab['factual_correctness'],ac['factual_correctness'],False)}, "
               f"overall {_delta(ab['overall'],ac['overall'],False)})")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Diff two eval.run reports on the same held-out set.")
    ap.add_argument("baseline", help="baseline report JSON")
    ap.add_argument("candidate", help="fine-tuned coach report JSON")
    args = ap.parse_args(argv)
    base, cand = load_games(args.baseline), load_games(args.candidate)
    print(render(base, cand, Path(args.baseline).stem, Path(args.candidate).stem))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
