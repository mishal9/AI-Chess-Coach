"""Build a blinded rating sheet so people can score the same coaching the judges did.

Every rubric number in this project comes from an LLM. Whether those judges agree with
a human has never been measured, and it is the difference between "our automatic metric
correlates with human judgement" and an assertion. This produces the instrument: a
stratified sample of coaching texts with model identity removed and order randomised,
plus a CSV for scores to come back in.

Three design choices, each load-bearing:

* **Stratified by mistake bucket**, so raters see the full range (a clean draw and a
  multi-blunder game demand different coaching) rather than whatever the shuffle gave.
* **Blinded and shuffled** — the item id encodes nothing. A rater who can tell which
  system wrote a text is not rating the text.
* **The rubric wording is imported, not restated.** If humans and judges are scored
  against different definitions, the agreement number is meaningless. Importing
  :data:`eval.rubric.RUBRIC_AXES` makes drift impossible rather than unlikely.

The rater sees the coaching and the *engine facts it was given*, because the factual axis
cannot be judged without them — the same information the LLM judge gets.

Usage:
    python -m eval.human_rating --out eval/human/round1 \\
        --report eval/reports/prompted_8b_2026-08-14.json \\
        --report eval/reports/8b_v2_2026-08-10.json
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from dataclasses import dataclass, field
from pathlib import Path

from eval.rubric import RUBRIC_AXES, SCALE_MAX, SCALE_MIN

# Enough for a stable agreement estimate without asking a volunteer for an evening. Two
# raters x 20 items is the size the sprint plan budgets for.
DEFAULT_SAMPLE = 20

# Fixed so the same sample can be rebuilt, and so a second rater gets identical items.
DEFAULT_SEED = 20260902


@dataclass(frozen=True)
class RatingItem:
    """One blinded coaching text for a human to score."""

    item_id: str
    coaching: str
    facts: str
    # Kept out of the rater's view, written only to the answer key.
    source_report: str
    pgn: str
    game_index: int
    bucket: str

    def as_key_row(self) -> dict:
        return {
            "item_id": self.item_id,
            "source_report": self.source_report,
            "pgn": self.pgn,
            "game_index": self.game_index,
            "bucket": self.bucket,
        }


@dataclass
class Sample:
    items: list[RatingItem] = field(default_factory=list)

    @property
    def buckets(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self.items:
            counts[item.bucket] = counts.get(item.bucket, 0) + 1
        return counts


def bucket_of(game: dict) -> str:
    """The mistake-profile bucket, from the held-out file the game came from."""
    return Path(game.get("pgn", "unknown")).stem


def collect(reports: list[Path], facts_by_game: dict[tuple[str, int], str]) -> list[RatingItem]:
    """Every scoreable coaching text across the given reports."""
    items: list[RatingItem] = []
    for path in reports:
        report = json.loads(path.read_text(encoding="utf-8"))
        for game in report.get("games", []):
            text = (game.get("coaching") or "").strip()
            if not text:
                continue
            key = (game.get("pgn", ""), game.get("game_index", 0))
            items.append(
                RatingItem(
                    item_id="",  # assigned after shuffling, so it encodes no provenance
                    coaching=text,
                    facts=facts_by_game.get(key, ""),
                    source_report=path.stem,
                    pgn=game.get("pgn", ""),
                    game_index=game.get("game_index", 0),
                    bucket=bucket_of(game),
                )
            )
    return items


def stratified_sample(
    items: list[RatingItem], size: int = DEFAULT_SAMPLE, seed: int = DEFAULT_SEED
) -> Sample:
    """Take ``size`` items spread as evenly as possible across buckets.

    Round-robins across buckets rather than sampling uniformly, so a bucket with few
    games still appears. Whichever system produced a text is irrelevant to selection —
    both arms are pooled, which is what keeps the sample blind by construction.
    """
    rng = random.Random(seed)
    by_bucket: dict[str, list[RatingItem]] = {}
    for item in items:
        by_bucket.setdefault(item.bucket, []).append(item)
    for pool in by_bucket.values():
        rng.shuffle(pool)

    picked: list[RatingItem] = []
    buckets = sorted(by_bucket)
    while len(picked) < size and any(by_bucket[b] for b in buckets):
        for bucket in buckets:
            if len(picked) >= size:
                break
            if by_bucket[bucket]:
                picked.append(by_bucket[bucket].pop())

    rng.shuffle(picked)  # order must not carry information either
    return Sample(
        items=[
            RatingItem(**{**vars(item), "item_id": f"item-{i + 1:02d}"})
            for i, item in enumerate(picked)
        ]
    )


def render_sheet(sample: Sample) -> str:
    """The rater-facing document. Markdown so it reads anywhere, prints, and diffs."""
    lines = [
        "# Chess coaching — rating sheet",
        "",
        f"You are scoring **{len(sample.items)} pieces of coaching**, each written about "
        "one chess game that a chess engine has already analysed.",
        "",
        "You do **not** need to be a strong chess player. Each item gives you the engine's "
        "own findings — treat those as ground truth — and your job is to judge the "
        "coaching written from them.",
        "",
        "## How to score",
        "",
        f"Give each item four scores from **{SCALE_MIN} to {SCALE_MAX}**:",
        "",
    ]
    for axis, description in RUBRIC_AXES.items():
        lines.append(f"- **{axis.replace('_', ' ')}** — {description}")
    lines += [
        "",
        "Put your scores in `ratings.csv` next to this file. One row per item; the "
        "item ids are already filled in.",
        "",
        "Notes:",
        "",
        "- The items are in random order and several different systems wrote them. "
        "Don't try to work out which — just score what's in front of you.",
        "- If you're torn between two scores, take the lower one.",
        "- Score each item on its own. Don't revise earlier ones to be consistent.",
        "",
        "---",
        "",
    ]
    for item in sample.items:
        lines += [
            f"## {item.item_id}",
            "",
            "**What the engine found:**",
            "",
            "```",
            item.facts.strip() or "(not recorded)",
            "```",
            "",
            "**The coaching:**",
            "",
            item.coaching.strip(),
            "",
            "---",
            "",
        ]
    return "\n".join(lines)


def write_round(sample: Sample, out_dir: Path) -> dict[str, Path]:
    """Write the sheet, the blank score CSV, and the answer key.

    The key lives beside the sheet but is what makes the blinding auditable afterwards:
    it is the only file mapping an item id back to which system wrote it.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "sheet": out_dir / "rating_sheet.md",
        "ratings": out_dir / "ratings.csv",
        "key": out_dir / "answer_key.csv",
    }

    paths["sheet"].write_text(render_sheet(sample), encoding="utf-8")

    with paths["ratings"].open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["item_id", *RUBRIC_AXES, "comment"])
        for item in sample.items:
            writer.writerow([item.item_id, *[""] * len(RUBRIC_AXES), ""])

    with paths["key"].open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["item_id", "source_report", "pgn", "game_index", "bucket"]
        )
        writer.writeheader()
        for item in sample.items:
            writer.writerow(item.as_key_row())

    return paths


def load_ratings(path: Path) -> dict[str, dict[str, int]]:
    """Read a returned ratings CSV as ``{item_id: {axis: score}}``, skipping blanks."""
    out: dict[str, dict[str, int]] = {}
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            scores = {}
            for axis in RUBRIC_AXES:
                value = (row.get(axis) or "").strip()
                if value:
                    scores[axis] = max(SCALE_MIN, min(SCALE_MAX, int(float(value))))
            if scores:
                out[row["item_id"]] = scores
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a blinded human rating sheet from committed eval reports."
    )
    parser.add_argument("--report", type=Path, action="append", required=True,
                        help="an eval report JSON (repeatable; both arms get pooled)")
    parser.add_argument("--out", type=Path, required=True, help="directory to write into")
    parser.add_argument("--size", type=int, default=DEFAULT_SAMPLE)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--manifest", type=Path, default=None,
                        help="held-out manifest, for rebuilding the facts blocks")
    parser.add_argument("--depth", type=int, default=15)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    # Facts are what make the factual axis answerable, and they are not stored in the
    # reports — rebuild them from the manifest exactly as the judge pipeline does.
    from eval.recheck import DEFAULT_MANIFEST, analyze_manifest

    analyzed = analyze_manifest(args.manifest or DEFAULT_MANIFEST, depth=args.depth)
    facts_by_game = {(e["pgn"], e["game_index"]): e["facts"] for e in analyzed}

    items = collect(args.report, facts_by_game)
    if not items:
        print("No coaching texts found in those reports.")
        return 1

    sample = stratified_sample(items, args.size, args.seed)
    paths = write_round(sample, args.out)

    print(f"{len(sample.items)} items from {len(items)} candidates")
    print(f"buckets: {sample.buckets}")
    for name, path in paths.items():
        print(f"  {name:8s} {path}")
    print("\nGive raters the sheet and a copy of ratings.csv. Keep answer_key.csv back.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# --- comparing humans to the judges -----------------------------------------------------

def judge_scores_for(
    key_path: Path, reports: dict[str, Path], axes: tuple[str, ...] | None = None
) -> dict[str, dict[str, int]]:
    """The LLM judge's scores for the rated items, via the answer key.

    Returns ``{item_id: {axis: score}}`` so it lines up with :func:`load_ratings`.
    """
    axes = axes or tuple(RUBRIC_AXES)
    loaded = {name: json.loads(p.read_text(encoding="utf-8")) for name, p in reports.items()}
    out: dict[str, dict[str, int]] = {}
    with Path(key_path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            report = loaded.get(row["source_report"])
            if report is None:
                continue
            for game in report.get("games", []):
                if (game.get("pgn") == row["pgn"]
                        and game.get("game_index", 0) == int(row["game_index"])
                        and game.get("rubric")):
                    out[row["item_id"]] = {
                        a: game["rubric"]["scores"][a]
                        for a in axes if a in game["rubric"]["scores"]
                    }
                    break
    return out


def agreement(
    human: dict[str, dict[str, int]], judge: dict[str, dict[str, int]]
) -> dict[str, dict]:
    """Per-axis human-vs-judge agreement over the items both scored.

    Reports the same shape as :func:`eval.equivalence.judge_agreement` — correlation plus
    a bias term — because the question is the same one: do they rank alike, and do they
    sit on the same scale? Kim et al. (NAACL 2025) report human agreement for chess
    commentary at Pearson 0.40-0.56, which is the band to read these against.
    """
    from scipy import stats

    shared = sorted(set(human) & set(judge))
    out: dict[str, dict] = {}
    for axis in RUBRIC_AXES:
        pairs = [
            (human[i][axis], judge[i][axis])
            for i in shared
            if axis in human[i] and axis in judge[i]
        ]
        if len(pairs) < 3:
            continue
        h = [p[0] for p in pairs]
        j = [p[1] for p in pairs]
        varies = len(set(h)) > 1 and len(set(j)) > 1
        out[axis] = {
            "n": len(pairs),
            "pearson": round(float(stats.pearsonr(h, j).statistic), 3) if varies else None,
            "kendall": round(float(stats.kendalltau(h, j).statistic), 3) if varies else None,
            "human_mean": round(sum(h) / len(h), 3),
            "judge_mean": round(sum(j) / len(j), 3),
            "bias": round((sum(j) - sum(h)) / len(h), 3),
            "exact": round(sum(a == b for a, b in pairs) / len(pairs), 3),
            "within_one": round(sum(abs(a - b) <= 1 for a, b in pairs) / len(pairs), 3),
        }
    return out
