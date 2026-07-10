"""Grow the held-out eval set by auto-curating CC0 games into mistake-profile buckets.

The scoreboard started at 6 games — one per mistake profile — which is too small for a
trustworthy metric (a single game swings the proportion metrics by ~17 points). This tool
widens it: it fetches a pool of public CC0 games, runs Stockfish to read each game's
**mistake profile** for the worse-playing side, sorts games into the same six buckets, and
tops each bucket up to a target count. Every candidate is kept **disjoint from the existing
held-out set** (via ``training.corpus`` fingerprints); the *corpus* is kept disjoint from the
new held-out games by re-running ``training.corpus`` afterwards (it reads ``eval/heldout/``).

The buckets mirror the original hand-curated six:

    clean_draw     no coachable error (<=1 inaccuracy), low ACPL, not lost — coach must not invent mistakes
    slow_loss      no discrete error but high ACPL and lost — the confabulation trap
    inaccuracies   only inaccuracies (>=2), no mistake/blunder
    two_mistakes   >=1 mistake, no blunder
    one_blunder    exactly one blunder
    multi_blunder  two or more blunders

Classification is a pure function of the analyzed report, and fetch/analysis are injectable,
so bucketing, selection, and manifest-writing are all unit-tested with no engine or network.

Usage:
    python -m eval.expand_heldout --per-bucket 5           # fetch, analyze, top up, write
    python -m eval.expand_heldout --per-bucket 5 --dry-run # show the bucket table, write nothing
    # then re-assemble the corpus so it stays disjoint:
    python -m training.corpus
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Callable

from coach.prompts import choose_coached_side
from training import corpus

HELDOUT_DIR = Path(__file__).resolve().parent / "heldout"

# Bucket order = increasing severity. Names match the original curated files.
BUCKETS = [
    "clean_draw",
    "slow_loss",
    "inaccuracies",
    "two_mistakes",
    "one_blunder",
    "multi_blunder",
]

# ACPL thresholds that separate the two "no discrete error" buckets (centipawns).
CLEAN_ACPL = 25.0       # below this, with nothing flagged and not lost -> clean_draw
SLOW_LOSS_ACPL = 35.0   # above this, nothing flagged but lost -> slow_loss

AnalyzeFn = Callable[[str], dict]   # pgn text -> analyzed report dict
FetchFn = Callable[[str, int], str]  # (user, max) -> multi-game PGN text

_TAG_RE = {
    tag: re.compile(rf'^\[{tag}\s+"([^"]*)"\]', re.MULTILINE)
    for tag in ("White", "Black", "Result")
}


def _tag(pgn: str, name: str) -> str:
    m = _TAG_RE[name].search(pgn)
    return m.group(1) if m else ""


def mistake_profile(report: dict, side: str) -> dict:
    """Count the coached side's blunders/mistakes/inaccuracies + its ACPL and whether it lost."""
    moves = report.get("moves", [])
    counts = {q: 0 for q in ("blunder", "mistake", "inaccuracy")}
    for m in moves:
        if m["side"] == side and m["quality"] in counts:
            counts[m["quality"]] += 1
    result = report.get("result", "*")
    lost = (result == "1-0" and side == "black") or (result == "0-1" and side == "white")
    return {
        "blunders": counts["blunder"],
        "mistakes": counts["mistake"],
        "inaccuracies": counts["inaccuracy"],
        "acpl": report["summary"].get(f"acpl_{side}"),
        "lost": lost,
    }


def classify(report: dict) -> tuple[str, str] | None:
    """Sort a game into a bucket for its worse-playing side, or ``None`` if it fits none.

    Returns ``(bucket, coached_side)``. Buckets are checked most-severe first, so e.g. a game
    with a blunder *and* inaccuracies lands in a blunder bucket, not ``inaccuracies``.
    """
    side = choose_coached_side(report)
    p = mistake_profile(report, side)
    acpl = p["acpl"] or 0.0

    if p["blunders"] >= 2:
        return "multi_blunder", side
    if p["blunders"] == 1:
        return "one_blunder", side
    if p["mistakes"] >= 1:
        return "two_mistakes", side
    if p["inaccuracies"] >= 2:
        return "inaccuracies", side
    # No coachable error (no blunder/mistake, <=1 inaccuracy).
    if p["lost"] and acpl >= SLOW_LOSS_ACPL:
        return "slow_loss", side
    if not p["lost"] and p["inaccuracies"] <= 1 and acpl < CLEAN_ACPL:
        return "clean_draw", side
    return None


def existing_counts(manifest: list[dict]) -> dict[str, int]:
    """How many games each bucket already has. Original entries infer bucket from filename."""
    counts = {b: 0 for b in BUCKETS}
    for e in manifest:
        bucket = e.get("bucket") or Path(e["pgn"]).stem
        if bucket in counts:
            counts[bucket] += 1
    return counts


def select(
    candidates: list[tuple[str, dict]],
    counts: dict[str, int],
    per_bucket: int,
) -> dict[str, list[tuple[str, str]]]:
    """Pick games to top each bucket up to ``per_bucket``, skipping duplicates.

    ``candidates`` is ``[(pgn_text, report), ...]``. Returns ``{bucket: [(pgn, side), ...]}``.
    Games already in the held-out set (by fingerprint) are dropped, as are dups within the pool.
    """
    have = dict(counts)
    picked: dict[str, list[tuple[str, str]]] = {b: [] for b in BUCKETS}
    seen: set[str] = set(corpus.heldout_fingerprints())
    for pgn, report in candidates:
        result = classify(report)
        if result is None:
            continue
        bucket, side = result
        if have[bucket] >= per_bucket:
            continue
        key = corpus.game_key(pgn)
        digest = hashlib.sha256(
            corpus._normalized_movetext(pgn).encode("utf-8")
        ).hexdigest()[:16]
        if key in seen or f"moves:{digest}" in seen:
            continue
        seen.add(key)
        seen.add(f"moves:{digest}")
        picked[bucket].append((pgn, side))
        have[bucket] += 1
    return picked


def append_to_bucket_file(heldout_dir: Path, bucket: str, games: list[str]) -> int:
    """Append ``games`` to ``heldout_dir/<bucket>.pgn`` (preserving originals). Returns the
    game_index the first appended game got."""
    path = heldout_dir / f"{bucket}.pgn"
    existing = corpus.split_pgn(path.read_text(encoding="utf-8")) if path.exists() else []
    start = len(existing)
    path.write_text("\n\n".join(existing + games) + "\n", encoding="utf-8")
    return start


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Widen the held-out eval set by bucket.")
    parser.add_argument("--per-bucket", type=int, default=5,
                        help="target total games per bucket (default: 5)")
    parser.add_argument("--user", action="append", default=[],
                        help="Lichess user to draw candidates from (default: corpus roster)")
    parser.add_argument("--max", type=int, default=60,
                        help="candidate games to fetch per user (default: 60)")
    parser.add_argument("--depth", type=int, default=16,
                        help="Stockfish depth for bucketing (default: 16)")
    parser.add_argument("--dry-run", action="store_true",
                        help="analyze and show the bucket table, but write nothing")
    return parser


def _default_analyze(depth: int) -> AnalyzeFn:
    def analyze(pgn: str) -> dict:
        import io

        import chess.pgn

        from engine.analyzer import analyze_game

        game = chess.pgn.read_game(io.StringIO(pgn))
        if game is None:
            raise ValueError("unparseable PGN")
        return analyze_game(game, depth=depth).to_dict()

    return analyze


def main(
    argv: list[str] | None = None,
    fetch_fn: FetchFn = corpus._lichess_fetch,
    analyze_fn: AnalyzeFn | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    analyze_fn = analyze_fn or _default_analyze(args.depth)
    users = list(args.user) or list(corpus.DEFAULT_USERS)

    raw: list[str] = []
    for user in users:
        print(f"Fetching up to {args.max} candidates for '{user}'...", file=sys.stderr)
        raw.extend(corpus.split_pgn(fetch_fn(user, args.max)))
    print(f"Analyzing {len(raw)} candidate games (depth {args.depth})...", file=sys.stderr)

    candidates: list[tuple[str, dict]] = []
    for i, pgn in enumerate(raw, 1):
        try:
            candidates.append((pgn, analyze_fn(pgn)))
        except Exception as exc:  # noqa: BLE001 - skip anything the engine can't handle
            print(f"  [{i}/{len(raw)}] skipped ({exc})", file=sys.stderr)

    manifest_path = HELDOUT_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    counts = existing_counts(manifest)
    picked = select(candidates, counts, args.per_bucket)

    print("\nBucket            have  +new  ->  total", file=sys.stderr)
    for b in BUCKETS:
        print(f"  {b:15} {counts[b]:3}  {len(picked[b]):+4}  ->  "
              f"{counts[b] + len(picked[b]):3}", file=sys.stderr)
    total_new = sum(len(v) for v in picked.values())

    if args.dry_run:
        print(f"\n[dry-run] {total_new} games would be added; nothing written.", file=sys.stderr)
        return 0
    if total_new == 0:
        print("\nNothing to add — every bucket is already full.", file=sys.stderr)
        return 0

    new_entries: list[dict] = []
    for bucket in BUCKETS:
        games = [pgn for pgn, _ in picked[bucket]]
        if not games:
            continue
        start = append_to_bucket_file(HELDOUT_DIR, bucket, games)
        for offset, (pgn, side) in enumerate(picked[bucket]):
            new_entries.append({
                "pgn": f"{bucket}.pgn",
                "game_index": start + offset,
                "coached_side": "white" if side == "white" else "black",
                "white": _tag(pgn, "White"),
                "black": _tag(pgn, "Black"),
                "bucket": bucket,
                "note": f"auto-curated into '{bucket}' (coached side: {side})",
            })
    manifest_path.write_text(
        json.dumps(manifest + new_entries, indent=2) + "\n", encoding="utf-8"
    )

    print(f"\nAdded {total_new} games -> {len(manifest) + total_new} held-out total.\n"
          f"IMPORTANT: re-run `python -m training.corpus` so the corpus drops any game now "
          f"in the held-out set.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
