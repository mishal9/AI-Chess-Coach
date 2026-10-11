"""Build the nested training sets of the pre-registered size sweep.

Pre-registered in ``docs/experiments/2026-10-10-game-only-vs-mixed-student.md``. Two arms:

- ``G``: whole-game rows only;
- ``M``: whole-game and position rows at 1 game : 2 position.

Each arm is built at several train sizes. Within an arm the sizes are **nested**: every set
is a prefix of the next, so only size varies. Games are put in a seeded order derived from
their identity alone (``training.dataset.bucket_value``), and a game's position rows stay
together in move order. ``M`` takes its first ``n // 3`` game rows and its first
``n - n // 3`` position rows from the two ordered streams. ``all`` is the largest ``M`` set
at exactly 1:2.

The train/validation split is decided per game by ``training.dataset.assign_split``, as in
``training.dataset``, so no game straddles the two. Every size of an arm shares one
validation set: the arm's rows from the validation games.

Usage:
    python -m training.sweep --game data/distill/deepseek_qc.jsonl \\
        --position data/distill/deepseek_pos_v5_clear.jsonl \\
        --position data/distill/deepseek_pos_paired_plain_clear.jsonl \\
        --arm G:400,1000,1700 --arm M:400,1000,1700,2500,all \\
        --out-root training/datasets --prefix sweep-v5
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from training.dataset import assign_split, bucket_value, filter_records, write_jsonl
from training.qc import load_records, row_key
from training.schema import SCHEMA_VERSION, DistillRecord

RATIOS = (0.9, 0.1, 0.0)


def ordered(records: list[DistillRecord], seed: int) -> list[DistillRecord]:
    """Rows in the seeded game order, a game's positions together and in move order."""
    return sorted(records, key=lambda r: (bucket_value(r.source_key(), seed),
                                          r.source_key(), r.source.get("move_number", 0)))


def arm_rows(arm: str, size: int | str, games: list[DistillRecord],
             positions: list[DistillRecord]) -> list[DistillRecord]:
    """The train rows of one arm at one size, taken from already-ordered streams."""
    if arm == "G":
        if size == "all":
            return list(games)
        if size > len(games):
            raise ValueError(f"G:{size} needs {size} game rows; only {len(games)}")
        return games[:size]
    if arm != "M":
        raise ValueError(f"unknown arm {arm!r}")
    if size == "all":
        n_game = min(len(games), len(positions) // 2)
        return games[:n_game] + positions[: 2 * n_game]
    n_game = size // 3
    n_pos = size - n_game
    if n_game > len(games) or n_pos > len(positions):
        raise ValueError(f"M:{size} needs {n_game} game and {n_pos} position rows; "
                         f"only {len(games)} and {len(positions)}")
    return games[:n_game] + positions[:n_pos]


def load_kind(paths: list[Path], kind: str, min_grounding: float) -> list[DistillRecord]:
    """Rows of one kind from several files, grounding-gated, without duplicate rows."""
    seen, out = set(), []
    for path in paths:
        for rec in filter_records(load_records(path), min_grounding):
            if rec.kind == kind and row_key(rec) not in seen:
                seen.add(row_key(rec))
                out.append(rec)
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the nested sweep training sets.")
    parser.add_argument("--game", type=Path, action="append", required=True,
                        help="JSONL holding the game rows (other kinds in it are ignored)")
    parser.add_argument("--position", type=Path, action="append", default=[],
                        help="JSONL holding position rows (other kinds ignored; repeatable)")
    parser.add_argument("--arm", action="append", required=True,
                        help="ARM:SIZE,SIZE,... with ARM G or M and SIZE a row count or 'all'")
    parser.add_argument("--out-root", type=Path, required=True)
    parser.add_argument("--prefix", required=True,
                        help="each set goes to OUT_ROOT/PREFIX-ARM-SIZE/")
    parser.add_argument("--split-seed", type=int, default=0)
    parser.add_argument("--order-seed", type=int, default=0)
    parser.add_argument("--min-grounding", type=float, default=1.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    pools = {"game": load_kind(args.game, "game", args.min_grounding),
             "position": load_kind(args.position, "position", args.min_grounding)}
    split = {k: {"train": [], "val": []} for k in pools}
    for kind, recs in pools.items():
        for rec in recs:
            s = assign_split(rec.source_key(), RATIOS, args.split_seed)
            split[kind]["val" if s == "val" else "train"].append(rec)
    games = ordered(split["game"]["train"], args.order_seed)
    positions = ordered(split["position"]["train"], args.order_seed)

    for spec in args.arm:
        arm, _, sizes = spec.partition(":")
        val = split["game"]["val"] + (split["position"]["val"] if arm == "M" else [])
        for size in sizes.split(","):
            size = size if size == "all" else int(size)
            train = arm_rows(arm, size, games, positions)
            out = args.out_root / f"{args.prefix}-{arm}-{size}"
            counts = {"train": write_jsonl(out / "train.jsonl",
                                           (r.to_chat_example() for r in train)),
                      "val": write_jsonl(out / "val.jsonl",
                                         (r.to_chat_example() for r in val))}
            kinds = {k: sum(r.kind == k for r in train) for k in ("game", "position")}
            manifest = {
                "schema_version": SCHEMA_VERSION,
                "registration": "docs/experiments/2026-10-10-game-only-vs-mixed-student.md",
                "arm": arm, "size": size, "format": "chat",
                "game_sources": [str(p) for p in args.game],
                "position_sources": [str(p) for p in args.position],
                "ratios": dict(zip(("train", "val", "test"), RATIOS)),
                "split_seed": args.split_seed, "order_seed": args.order_seed,
                "min_grounding": args.min_grounding,
                "counts": counts, "train_kinds": kinds,
                "train_games": len({r.source_key() for r in train}),
            }
            (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                               encoding="utf-8")
            print(f"{arm}-{size}: train {counts['train']} ({kinds['game']} game, "
                  f"{kinds['position']} position)  val {counts['val']} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
