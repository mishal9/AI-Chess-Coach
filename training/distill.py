"""Distillation pipeline: analyzed games → grounding-checked coaching pairs (raw JSONL).

For each source game: run Stockfish, build the deterministic facts, have the teacher write
coaching for those facts, then **self-check the teacher's grounding** against the same facts
before keeping the pair. The output is a raw JSONL of :class:`~training.schema.DistillRecord`
that ``training.dataset`` later filters and splits into train/val/test.

v2 emits two row shapes per game: one whole-game row (the deployed task) plus up to
``--positions-per-game`` single-position rows (worst mistakes first) whose tight facts
blocks train citation discipline. Outputs that fail strict grounding are re-rolled up to
``--retries`` times (the anthropic teacher is nondeterministic) keeping the best attempt.

Usage:
    python -m training.distill --sources data/games/manifest.json --out data/distill/raw.jsonl
    python -m training.distill --sources data/games/ --teacher anthropic \
        --positions-per-game 4 --retries 1 --max-teacher-calls 2500

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
from engine.analyzer import DEFAULT_DEPTH
from eval import grounding
from training import teacher as teacher_mod
from training.schema import DistillRecord

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
        from engine.pgn import load_game

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
        if m["side"] == coached_side and m["quality"] in prompts.MISTAKE_QUALITIES
    )
    return {
        "num_mistakes": n_mistakes,
        "acpl": report["summary"].get(f"acpl_{coached_side}"),
    }


def _best_grounded_attempt(generate, check, retries: int):
    """Generate up to ``1 + retries`` completions, stopping at the first perfectly
    grounded one; return ``(completion, grounding_result)`` of the best-scoring attempt.

    Retrying is meaningful because the default (anthropic) teacher runs at its default
    temperature — a re-roll genuinely differs, and the grounding gate later drops
    anything that never rolled clean.
    """
    best = None
    for _ in range(1 + max(0, retries)):
        completion = generate()
        g = check(completion)
        if best is None or g.score > best[1].score:
            best = (completion, g)
        if g.score >= 1.0:
            break
    return best


def _depth_field(depth: int | None) -> dict:
    return {} if depth is None else {"depth": depth}


def build_record(
    source: SourceGame,
    report: dict,
    teacher_fn: teacher_mod.TeacherFn,
    teacher_desc: dict,
    retries: int = 0,
    depth: int | None = None,
) -> DistillRecord:
    """Coach one game with the teacher and package the grounding-checked training pair.

    ``depth`` is the Stockfish depth ``report`` was analyzed at. It is stored in the row's
    ``source`` so a dataset can show which depth its facts came from.
    """
    coached_side = source.coached_side or prompts.choose_coached_side(report)
    messages = prompts.build_messages(report, coached_side)
    facts = prompts.format_report_facts(report, coached_side)
    completion, g = _best_grounded_attempt(
        lambda: teacher_fn(report, coached_side),
        lambda c: grounding.grounding_from_report(c, report, coached_side),
        retries,
    )
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
            **_depth_field(depth),
        },
        coached_side=coached_side,
        facts=facts,
        prompt=messages,
        completion=completion,
        teacher=teacher_desc,
        quality=quality,
        kind="game",
    )


def build_position_record(
    source: SourceGame,
    report: dict,
    move: dict,
    position_teacher_fn: teacher_mod.PositionTeacherFn,
    teacher_desc: dict,
    retries: int = 0,
    depth: int | None = None,
) -> DistillRecord:
    """Coach ONE critical position and package the tight-citation training pair.

    Grounding is checked against the *position* facts block: a move that exists
    elsewhere in the game but not in this block still counts as hallucinated — that
    strictness is the entire point of position rows.
    """
    coached_side = source.coached_side or prompts.choose_coached_side(report)
    messages = prompts.build_position_messages(report, coached_side, move)
    facts = prompts.format_position_facts(report, coached_side, move)
    completion, g = _best_grounded_attempt(
        lambda: position_teacher_fn(report, coached_side, move),
        lambda c: grounding.score_grounding(c, facts),
        retries,
    )
    quality = {
        "grounding": round(g.score, 3),
        "grounded": g.grounded,
        "hallucinated": sorted(g.hallucinated),
        "move_quality": move["quality"],
        "win_prob_loss": move["win_prob_loss"],
    }
    return DistillRecord(
        source={
            "pgn": source.pgn.name,
            "game_index": source.game_index,
            "coached_side": coached_side,
            "move_number": move["move_number"],
            "move_san": move["san"],
            **_depth_field(depth),
        },
        coached_side=coached_side,
        facts=facts,
        prompt=messages,
        completion=completion,
        teacher=teacher_desc,
        quality=quality,
        kind="position",
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
                        choices=["ollama", "anthropic", "gemini", "deepseek"])
    parser.add_argument("--teacher-model", default=None, help="override the teacher's model")
    parser.add_argument(
        "--teacher-thinking", choices=["enabled", "disabled"], default=None,
        help="deepseek only: send an explicit thinking mode (default: the API's own); "
        "recorded in each row's teacher metadata",
    )
    parser.add_argument("--depth", type=int, default=DEFAULT_DEPTH, help="Stockfish search depth")
    parser.add_argument(
        "--positions-per-game", type=int, default=4,
        help="also emit up to N per-position rows (worst mistakes first) per game; "
        "0 = whole-game rows only (v1 behavior)",
    )
    parser.add_argument(
        "--retries", type=int, default=1,
        help="re-roll a teacher output up to N times if it fails strict grounding "
        "(best attempt is kept)",
    )
    parser.add_argument(
        "--no-game-rows", action="store_true",
        help="emit ONLY position rows (skip the whole-game row) — for topping up an "
        "existing game-row run without paying for it twice",
    )
    parser.add_argument(
        "--max-teacher-calls", type=int, default=100,
        help="refuse to start if the WORST-CASE teacher calls — "
        "games x (1 + positions-per-game) x (1 + retries) — exceed this (spend guard)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    sources = load_sources(args.sources)
    if not sources:
        print(f"No source games found at {args.sources}", file=sys.stderr)
        return 1
    game_calls = 0 if args.no_game_rows else 1
    worst_case = len(sources) * (game_calls + args.positions_per_game) * (1 + args.retries)
    if worst_case > args.max_teacher_calls:
        print(
            f"Refusing to start: worst case {worst_case} teacher calls "
            f"({len(sources)} games x ({game_calls} + {args.positions_per_game} positions) x "
            f"(1 + {args.retries} retries)) exceeds "
            f"--max-teacher-calls {args.max_teacher_calls}.",
            file=sys.stderr,
        )
        return 1

    teacher_desc = {
        "backend": args.teacher,
        "model": args.teacher_model or (
            teacher_mod.backends.DEFAULT_ANTHROPIC_MODEL if args.teacher == "anthropic"
            else teacher_mod.backends.DEFAULT_GEMINI_MODEL if args.teacher == "gemini"
            else teacher_mod.DEFAULT_DEEPSEEK_MODEL if args.teacher == "deepseek"
            else "qwen2.5:3b-instruct"
        ),
    }
    if args.teacher == "deepseek":
        teacher_mod.DEEPSEEK_THINKING = args.teacher_thinking
        teacher_desc["temperature"] = teacher_mod.DEEPSEEK_TEMPERATURE
        teacher_desc["thinking"] = args.teacher_thinking or "api-default"
    teacher_fn = teacher_mod.make_teacher_fn(args.teacher, args.teacher_model)
    position_teacher_fn = teacher_mod.make_position_teacher_fn(
        args.teacher, args.teacher_model
    )
    print(
        f"Distilling {len(sources)} games with {args.teacher} "
        f"({teacher_desc['model']}) — worst case {worst_case} teacher calls "
        f"(game rows + up to {args.positions_per_game} position rows each, "
        f"{args.retries} grounding retries).",
        file=sys.stderr,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    kept = {"game": 0, "position": 0}
    grounded = {"game": 0, "position": 0}

    def emit(fh, record: DistillRecord) -> None:
        fh.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
        kept[record.kind] += 1
        grounded[record.kind] += record.quality["grounded"]

    with args.out.open("w", encoding="utf-8") as fh:
        for i, source in enumerate(sources, 1):
            print(f"[{i}/{len(sources)}] {source.pgn.name}#{source.game_index}...",
                  file=sys.stderr)
            report = analyze_source(source, args.depth)
            coached_side = source.coached_side or prompts.choose_coached_side(report)
            source = SourceGame(source.pgn, source.game_index, coached_side)

            if not args.no_game_rows:
                emit(fh, build_record(source, report, teacher_fn, teacher_desc,
                                      retries=args.retries, depth=args.depth))
            mistakes = prompts.coachable_mistakes(report, coached_side)
            for move in mistakes[: args.positions_per_game]:
                emit(fh, build_position_record(source, report, move,
                                               position_teacher_fn, teacher_desc,
                                               retries=args.retries, depth=args.depth))

    if args.teacher == "deepseek":
        u = teacher_mod.DEEPSEEK_USAGE
        print(
            f"DeepSeek usage: {u['calls']} calls, {u['prompt_tokens']} prompt + "
            f"{u['completion_tokens']} completion tokens "
            f"({u['reasoning_tokens']} of them reasoning); "
            f"model(s) reported: {sorted(u['models']) or 'none'}.",
            file=sys.stderr,
        )
    total_kept = sum(kept.values())
    total_grounded = sum(grounded.values())
    print(
        f"Wrote {total_kept} records to {args.out}  "
        f"(game {grounded['game']}/{kept['game']} grounded, "
        f"position {grounded['position']}/{kept['position']} grounded, "
        f"{total_grounded}/{total_kept} total; "
        "filter/split with `python -m training.dataset`).",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
