"""JSONL I/O and the train/val/test split — turn raw distillation into a versioned dataset.

The split is **deterministic and leakage-safe**: a record's split is decided by hashing its
per-game key (``pgn#index``), so (a) re-running produces the identical split with no stored
shuffle, and (b) every position from one game lands in the same split — a game can never
straddle train and test. A quality gate drops teacher outputs that failed their own grounding
self-check before they can teach the student to hallucinate.

Usage:
    python -m training.dataset --in data/distill/raw.jsonl --out-dir training/datasets/v1
    python -m training.dataset --in raw.jsonl --out-dir ds/v1 --min-grounding 1.0 --as-chat
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable

from training.schema import SCHEMA_VERSION, DistillRecord

DEFAULT_RATIOS = (0.8, 0.1, 0.1)  # train, val, test
SPLITS = ("train", "val", "test")


def write_jsonl(path: Path, rows: Iterable[dict]) -> int:
    """Write ``rows`` as one JSON object per line; returns the count written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    return n


def read_jsonl(path: Path) -> list[dict]:
    """Read a JSONL file into a list of dicts, skipping blank lines."""
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _bucket(key: str, seed: int) -> float:
    """Map a key to a stable, uniform value in ``[0, 1)`` via SHA-256 (no per-run state)."""
    h = hashlib.sha256(f"{seed}:{key}".encode()).hexdigest()
    return int(h[:16], 16) / 16**16


def assign_split(key: str, ratios=DEFAULT_RATIOS, seed: int = 0) -> str:
    """Which split a game key belongs to. Same key + seed -> always the same split."""
    r_train, r_val, _ = ratios
    x = _bucket(key, seed)
    if x < r_train:
        return "train"
    if x < r_train + r_val:
        return "val"
    return "test"


def split_records(
    records: list[DistillRecord], ratios=DEFAULT_RATIOS, seed: int = 0
) -> dict[str, list[DistillRecord]]:
    """Partition records into train/val/test by hashed per-game key (no game straddles splits)."""
    out: dict[str, list[DistillRecord]] = {s: [] for s in SPLITS}
    for rec in records:
        out[assign_split(rec.source_key(), ratios, seed)].append(rec)
    return out


def filter_records(
    records: Iterable[DistillRecord], min_grounding: float = 1.0
) -> list[DistillRecord]:
    """Keep only records whose teacher output met the grounding bar (default: perfectly clean).

    The whole point of the dataset is faithful coaching; a teacher example that itself
    invented a move is training poison and is dropped here, loudly counted by the CLI.
    """
    return [r for r in records if r.quality.get("grounding", 0.0) >= min_grounding]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Filter + split raw distillation into a dataset.")
    parser.add_argument("--in", dest="in_path", type=Path, required=True,
                        help="raw record JSONL from training.distill")
    parser.add_argument("--out-dir", type=Path, required=True,
                        help="write {train,val,test}.jsonl + manifest.json here")
    parser.add_argument("--min-grounding", type=float, default=1.0,
                        help="drop teacher outputs below this grounding score (default 1.0)")
    parser.add_argument("--ratios", type=float, nargs=3, default=list(DEFAULT_RATIOS),
                        metavar=("TRAIN", "VAL", "TEST"))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--as-chat", action="store_true",
                        help="emit minimal {messages:[...]} training rows instead of full records")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    raw = [DistillRecord.from_dict(d) for d in read_jsonl(args.in_path)]
    kept = filter_records(raw, args.min_grounding)
    dropped = len(raw) - len(kept)
    splits = split_records(kept, tuple(args.ratios), args.seed)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    for name, recs in splits.items():
        rows = [r.to_chat_example() if args.as_chat else r.to_dict() for r in recs]
        counts[name] = write_jsonl(args.out_dir / f"{name}.jsonl", rows)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "source": str(args.in_path),
        "format": "chat" if args.as_chat else "record",
        "min_grounding": args.min_grounding,
        "ratios": {s: r for s, r in zip(SPLITS, args.ratios)},
        "seed": args.seed,
        "counts": counts,
        "total": sum(counts.values()),
        "dropped_below_grounding": dropped,
    }
    (args.out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    print(
        f"train {counts['train']}  val {counts['val']}  test {counts['test']}  "
        f"(dropped {dropped} below grounding {args.min_grounding}) -> {args.out_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
