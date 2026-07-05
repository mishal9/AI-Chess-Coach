"""Distillation pipeline: analyzed games → grounding-checked coaching pairs (raw JSONL).

For each source game: run Stockfish, build the deterministic facts, have the teacher write
coaching for those facts, then **self-check the teacher's grounding** against the same facts
before keeping the pair. The output is a raw JSONL of :class:`~training.schema.DistillRecord`
that ``training.dataset`` later filters and splits into train/val/test.

Usage:
    python -m training.distill --sources data/games/manifest.json --out data/distill/raw.jsonl
    python -m training.distill --sources data/games/ --teacher anthropic --max-teacher-calls 200

LEAKAGE WARNING: never point ``--sources`` at ``eval/heldout/`` — those games are the
scoreboard. Distilling on them would make the Phase-4 win meaningless. The pipeline refuses
a sources path under ``eval/heldout`` as a guardrail.

The teacher and analysis are injectable (``teacher_fn`` / ``analyze_fn``) so aggregation,
the grounding gate, and the spend guard are unit-tested with no engine, model, or API key.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from coach import prompts
from eval import grounding
from training import teacher as teacher_mod
from training.schema import DistillRecord

# quality strings that count as a coachable mistake (mirrors coach.prompts).
_MISTAKE_QUALITIES = ("blunder", "mistake", "inaccuracy")

AnalyzeFn = Callable[["SourceGame", int], dict]


@dataclass
class SourceGame:
    """One game to distill coaching from."""

    pgn: Path
    game_index: int = 0
    coached_side: str | None = None  # None -> auto-pick the worse-playing side


def load_sources(path: Path) -> list[SourceGame]:
    """Load games from a manifest JSON (list of ``{pgn, game_index, coached_side}``) or a
    directory of ``.pgn`` files (every game in every file).

    ``pgn`` paths in a manifest resolve relative to the manifest. Refuses the held-out set.
    """
    resolved = path.resolve()
    if "heldout" in resolved.parts and "eval" in resolved.parts:
        raise SystemExit(
            f"Refusing to distill on the held-out eval set ({path}) — that would leak the "
            "scoreboard into training. Point --sources at a separate training corpus."
        )

    if resolved.is_dir():
        from engine.report import load_game

        sources: list[SourceGame] = []
        for pgn in sorted(resolved.glob("*.pgn")):
            i = 0
            while load_game(pgn, i) is not None:
                sources.append(SourceGame(pgn=pgn, game_index=i))
                i += 1
        return sources

    data = json.loads(resolved.read_text(encoding="utf-8"))
    base = resolved.parent
    return [
        SourceGame(
            pgn=base / e["pgn"],
            game_index=e.get("game_index", 0),
            coached_side=e.get("coached_side"),
        )
        for e in data
    ]


def analyze_source(source: SourceGame, depth: int) -> dict:
    """Run Stockfish over a source game and return the report dict (engine imported lazily
    so the rest of the module needs no engine)."""
    from engine.analyzer import analyze_game
    from engine.report import load_game

    game = load_game(source.pgn, source.game_index)
    if game is None:
        raise SystemExit(f"No game at index {source.game_index} in {source.pgn}")
    return analyze_game(game, depth=depth).to_dict()


def _difficulty(report: dict, coached_side: str) -> dict:
    """Signals for later dataset balancing/filtering: how hard/rich this example is."""
    n_mistakes = sum(
        1
        for m in report.get("moves", [])
        if m["side"] == coached_side and m["quality"] in _MISTAKE_QUALITIES
    )
    return {
        "num_mistakes": n_mistakes,
        "acpl": report["summary"].get(f"acpl_{coached_side}"),
    }


def build_record(
    source: SourceGame,
    report: dict,
    teacher_fn: teacher_mod.TeacherFn,
    teacher_desc: dict,
) -> DistillRecord:
    """Coach one game with the teacher and package the grounding-checked training pair."""
    coached_side = source.coached_side or prompts.choose_coached_side(report)
    messages = prompts.build_messages(report, coached_side)
    facts = prompts.format_report_facts(report, coached_side)
    completion = teacher_fn(report, coached_side)

    g = grounding.grounding_from_report(completion, report, coached_side)
    quality = {
        "grounding": round(g.score, 3),
        "grounded": g.grounded,
        "hallucinated": sorted(g.hallucinated),
        **_difficulty(report, coached_side),
    }
    return DistillRecord(
        source={
            "pgn": source.pgn.name,
            "game_index": source.game_index,
            "coached_side": coached_side,
        },
        coached_side=coached_side,
        facts=facts,
        prompt=messages,
        completion=completion,
        teacher=teacher_desc,
        quality=quality,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Distill coaching pairs from analyzed games.")
    parser.add_argument(
        "--sources", type=Path, required=True,
        help="manifest JSON or a directory of .pgn files (NOT the held-out set)",
    )
    parser.add_argument(
        "--out", type=Path, default=Path("data/distill/raw.jsonl"),
        help="write the raw record JSONL here (default: data/distill/raw.jsonl)",
    )
    parser.add_argument("--teacher", default="anthropic",
                        choices=["ollama", "anthropic", "gemini"])
    parser.add_argument("--teacher-model", default=None, help="override the teacher's model")
    parser.add_argument("--depth", type=int, default=18, help="Stockfish search depth")
    parser.add_argument(
        "--max-teacher-calls", type=int, default=100,
        help="refuse to start if the run would exceed this many teacher calls (spend guard)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    sources = load_sources(args.sources)
    if not sources:
        print(f"No source games found at {args.sources}", file=sys.stderr)
        return 1
    if len(sources) > args.max_teacher_calls:
        print(
            f"Refusing to start: {len(sources)} teacher calls exceeds "
            f"--max-teacher-calls {args.max_teacher_calls}.",
            file=sys.stderr,
        )
        return 1

    teacher_desc = {
        "backend": args.teacher,
        "model": args.teacher_model or (
            teacher_mod.backends.DEFAULT_ANTHROPIC_MODEL if args.teacher == "anthropic"
            else teacher_mod.backends.DEFAULT_GEMINI_MODEL if args.teacher == "gemini"
            else "qwen2.5:3b-instruct"
        ),
    }
    teacher_fn = teacher_mod.make_teacher_fn(args.teacher, args.teacher_model)
    print(
        f"Distilling {len(sources)} games with {args.teacher} "
        f"({teacher_desc['model']}) — ~{len(sources)} teacher calls.",
        file=sys.stderr,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    kept = grounded = 0
    with args.out.open("w", encoding="utf-8") as fh:
        for i, source in enumerate(sources, 1):
            print(f"[{i}/{len(sources)}] {source.pgn.name}#{source.game_index}...",
                  file=sys.stderr)
            report = analyze_source(source, args.depth)
            record = build_record(source, report, teacher_fn, teacher_desc)
            fh.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
            kept += 1
            grounded += record.quality["grounded"]

    print(
        f"Wrote {kept} records to {args.out}  "
        f"({grounded}/{kept} teacher-grounded; filter/split with `python -m training.dataset`).",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
