"""N2: score an open-weights teacher as a *coach* on the held-out games.

Runs the same evaluation ``eval.run`` does — same games, same Stockfish depth, same Opus
judge, same claim checks, same report format — with one change: the coach is a DeepSeek
model reached through ``training.teacher.deepseek_backend``. ``eval.run`` itself only knows
local Ollama coaches, and ``eval/`` is frozen while the paper is open, so this reuses its
functions instead of editing them.

The coach gets the *student* prompt (no teacher "excellence" layer), because N2 asks
whether the model can coach from the facts block the student sees. By default that is the
v2-era system prompt, so the result is comparable with the 8B arms in ``eval/reports``.

Usage:
    python -m training.n2_eval --out eval/reports/deepseek_v4_pro_2026-09-25.json
    python -m training.n2_eval --limit 3 --out /tmp/smoke.json      # cheap smoke test
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from coach import prompts
from engine.analyzer import DEFAULT_DEPTH
from engine.cache import engine_label
from eval import backends, claims, grounding
from eval.run import (
    DEFAULT_MANIFEST, aggregate, analyze_case, append_partial, evaluate_case,
    format_summary, load_cases, load_partial, make_judge_fn,
)
from training import teacher
from training.prompts_v2 import V2_ERA_SYSTEM_PROMPT


def make_deepseek_coach(model: str, prompt: str):
    """A coach fn over DeepSeek. ``prompt`` is ``v2-era`` or ``current``."""

    def coach_fn(report: dict, coached_side: str) -> str:
        messages = prompts.build_messages(report, coached_side)
        if prompt == "v2-era":
            messages = [{"role": "system", "content": V2_ERA_SYSTEM_PROMPT}, *messages[1:]]
        return teacher.deepseek_backend(messages, model=model)

    return coach_fn


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Score a DeepSeek coach on the held-out set.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--model", default=teacher.DEFAULT_DEEPSEEK_MODEL)
    parser.add_argument("--thinking", choices=["enabled", "disabled"], default="disabled")
    parser.add_argument("--temperature", type=float, default=0.0,
                        help="0 matches the other arms' reproducible baseline")
    parser.add_argument("--prompt", choices=["v2-era", "current"], default="v2-era")
    parser.add_argument("--judge-model", default=None)
    parser.add_argument("--no-judge", action="store_true")
    parser.add_argument("--depth", type=int, default=DEFAULT_DEPTH, help="Stockfish search depth")
    parser.add_argument("--limit", type=int, default=None, help="only the first N games")
    parser.add_argument("--max-judge-calls", type=int, default=50)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cases = load_cases(args.manifest)[: args.limit]
    if not args.no_judge and len(cases) > args.max_judge_calls:
        print(f"Refusing: {len(cases)} judge calls exceeds --max-judge-calls "
              f"{args.max_judge_calls}.", file=sys.stderr)
        return 1

    teacher.DEEPSEEK_THINKING = args.thinking
    teacher.DEEPSEEK_TEMPERATURE = args.temperature
    coach_fn = make_deepseek_coach(args.model, args.prompt)
    judge_fn = None if args.no_judge else make_judge_fn(
        backends.anthropic_backend, args.judge_model
    )
    judge_desc = args.judge_model or backends.DEFAULT_ANTHROPIC_MODEL
    coach_desc = args.model

    done = load_partial(args.out, coach_desc, judge_desc) if args.resume else {}
    records = []
    for i, case in enumerate(cases, 1):
        key = (case.pgn.name, case.game_index, case.coached_side)
        if key in done:
            records.append(done[key])
            continue
        print(f"[{i}/{len(cases)}] {case.pgn.name} (coach {case.coached_side})...",
              file=sys.stderr, flush=True)
        record = evaluate_case(case, analyze_case(case, args.depth), coach_fn, judge_fn)
        records.append(record)
        append_partial(args.out, record, coach_desc, judge_desc)

    agg = aggregate(records)
    print(format_summary(agg, coach_desc, judge_desc if judge_fn else "none"))
    u = teacher.DEEPSEEK_USAGE
    print(f"DeepSeek usage: {u['calls']} calls, {u['prompt_tokens']} in + "
          f"{u['completion_tokens']} out tokens; model(s): {sorted(u['models'])}",
          file=sys.stderr)

    payload = {
        "coach_model": coach_desc,
        "coach_temperature": args.temperature,
        "coach_prompt": args.prompt,
        "coach_thinking": args.thinking,
        "coach_models_reported": sorted(u["models"]),
        "judge": "anthropic" if judge_fn else None,
        "judge_model": judge_desc if judge_fn else None,
        "depth": args.depth,
        "stockfish": engine_label(),
        "metric_versions": {"grounding": grounding.METRIC_VERSION,
                            "claims": claims.METRIC_VERSION},
        "date": date.today().isoformat(),
        "aggregate": agg,
        "games": records,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
