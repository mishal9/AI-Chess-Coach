"""Baseline eval runner — the scoreboard for the coaching model.

Scores a *coach* model across the fixed held-out set (``eval/heldout/``) and reports the
numbers a later fine-tune must beat: deterministic **grounding** plus the LLM-judged
**rubric**. Any coach model can be scored by any judge model — the coach is the subject,
the judge is only the ruler.

Usage:
    python -m eval.run                                  # local Qwen coach, local judge
    python -m eval.run --judge anthropic                # grade with Claude (the real number)
    python -m eval.run --no-judge                       # grounding only (free, offline)
    python -m eval.run --coach-model qwen2.5:3b-instruct --out eval/reports/baseline.json

The coach/judge calls are injectable (``coach_fn`` / ``judge_fn``) so the aggregation and
report logic is unit-tested with no engine, model, or API key.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable

from coach import client as coach_client, prompts
from eval import backends, grounding
from eval import judge as judge_mod
from eval.rubric import RUBRIC_AXES

HELDOUT_DIR = Path(__file__).resolve().parent / "heldout"
DEFAULT_MANIFEST = HELDOUT_DIR / "manifest.json"

# A coach turns (report, coached_side) -> coaching text; a judge grades that text.
CoachFn = Callable[[dict, str], str]
JudgeFn = Callable[[str, dict, str], "judge_mod.rubric.RubricScore"]

_JUDGE_BACKENDS = {
    "ollama": backends.ollama_backend,
    "anthropic": backends.anthropic_backend,
    "gemini": backends.gemini_backend,
}


@dataclass
class EvalCase:
    """One held-out game and how to evaluate it."""

    pgn: Path
    game_index: int
    coached_side: str
    note: str = ""


def load_cases(manifest_path: Path = DEFAULT_MANIFEST) -> list[EvalCase]:
    """Parse the held-out manifest into cases, resolving PGN paths relative to it."""
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    base = manifest_path.parent
    return [
        EvalCase(
            pgn=base / e["pgn"],
            game_index=e.get("game_index", 0),
            coached_side=e["coached_side"],
            note=e.get("note", ""),
        )
        for e in data
    ]


def make_coach_fn(model: str, temperature: float) -> CoachFn:
    """Default coach: the Phase-2 prompted pipeline over a local Ollama model."""

    def coach_fn(report: dict, coached_side: str) -> str:
        messages = prompts.build_messages(report, coached_side)
        return coach_client.chat(messages, model=model, temperature=temperature)

    return coach_fn


def make_judge_fn(backend, model: str | None) -> JudgeFn:
    """Default judge: score with the chosen backend via :func:`eval.judge.judge_coaching`."""

    def judge_fn(coaching: str, report: dict, coached_side: str):
        return judge_mod.judge_coaching(
            coaching, report, coached_side=coached_side, backend=backend, model=model
        )

    return judge_fn


def analyze_case(case: EvalCase, depth: int) -> dict:
    """Run Stockfish over a case's game and return the report dict (imported lazily so
    the rest of the module needs no engine)."""
    from engine.analyzer import analyze_game
    from engine.report import load_game

    game = load_game(case.pgn, case.game_index)
    if game is None:
        raise SystemExit(f"No game at index {case.game_index} in {case.pgn}")
    return analyze_game(game, depth=depth).to_dict()


def evaluate_case(
    case: EvalCase,
    report: dict,
    coach_fn: CoachFn,
    judge_fn: JudgeFn | None,
) -> dict:
    """Coach one game, then score it: grounding always, rubric when a judge is given."""
    coaching = coach_fn(report, case.coached_side)
    g = grounding.grounding_from_report(coaching, report, case.coached_side)
    record = {
        "pgn": case.pgn.name,
        "coached_side": case.coached_side,
        "note": case.note,
        "coaching": coaching,
        "grounding": {
            "score": round(g.score, 3),
            "grounded": g.grounded,
            "hallucinated": sorted(g.hallucinated),
            # Persist both sides of the diff so a later change to the metric can be
            # re-scored from the committed report alone — no engine, no model, no judge.
            # Their absence is why correcting the bare-square bug needed the allowed set
            # reconstructed by hand; see eval/rescore.py.
            "cited": sorted(g.cited),
            "allowed": sorted(g.allowed),
        },
        "identifies_worst_move": grounding.identifies_worst_move(coaching, report),
    }
    if judge_fn is not None:
        record["rubric"] = judge_fn(coaching, report, case.coached_side).to_dict()
    return record


def _partial_path(out: Path) -> Path:
    """Sidecar holding per-game results as they complete, so a killed run is resumable."""
    return out.with_suffix(out.suffix + ".partial.jsonl")


def load_partial(out: Path, coach: str, judge: str) -> dict[tuple[str, str], dict]:
    """Per-game records from a previous run, keyed by ``(pgn, coached_side)``.

    Refuses a sidecar written by a different coach/judge: silently mixing two models'
    scores into one report would produce a number that describes neither.
    """
    path = _partial_path(out)
    if not path.exists():
        return {}
    done = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            r = json.loads(line)
            got = (r.pop("_coach", None), r.pop("_judge", None))
            if got != (coach, judge):
                raise SystemExit(
                    f"Refusing to resume: {path} was written by coach={got[0]} judge={got[1]}, "
                    f"but this run is coach={coach} judge={judge}. Delete it or change --out."
                )
            done[(r["pgn"], r["coached_side"])] = r
    return done


def append_partial(out: Path, record: dict, coach: str, judge: str) -> None:
    """Append one finished game. Flushed immediately — the whole point is surviving a kill."""
    path = _partial_path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({**record, "_coach": coach, "_judge": judge},
                            ensure_ascii=False) + "\n")
        fh.flush()


def aggregate(records: list[dict]) -> dict:
    """Reduce per-game records to the headline baseline vector."""
    n = len(records)
    if n == 0:
        return {}
    agg = {
        "games": n,
        "grounding_mean": round(sum(r["grounding"]["score"] for r in records) / n, 3),
        "grounded_rate": round(sum(r["grounding"]["grounded"] for r in records) / n, 3),
        "worst_move_identified_rate": round(
            sum(r["identifies_worst_move"] for r in records) / n, 3
        ),
    }
    if all("rubric" in r for r in records):
        agg["rubric_axis_means"] = {
            ax: round(sum(r["rubric"]["scores"][ax] for r in records) / n, 2)
            for ax in RUBRIC_AXES
        }
        agg["rubric_overall_mean"] = round(
            sum(r["rubric"]["overall"] for r in records) / n, 2
        )
    return agg


def format_summary(agg: dict, coach_model: str, judge_desc: str) -> str:
    """Render the headline baseline vector as a readable block."""
    lines = [
        f"Baseline  ·  coach={coach_model}  ·  judge={judge_desc}  ·  {agg['games']} games",
        f"  Grounding      mean {agg['grounding_mean']:.2f}   "
        f"grounded {agg['grounded_rate'] * 100:.0f}%   "
        f"worst-move identified {agg['worst_move_identified_rate'] * 100:.0f}%",
    ]
    if "rubric_overall_mean" in agg:
        lines.append("  Rubric (mean, 1-5):")
        for ax, val in agg["rubric_axis_means"].items():
            lines.append(f"    {ax:<22} {val:.2f}")
        lines.append(f"    {'overall':<22} {agg['rubric_overall_mean']:.2f}")
    else:
        lines.append("  Rubric: skipped (--no-judge)")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Score a coach model over the held-out set.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--judge", choices=list(_JUDGE_BACKENDS), default="ollama",
        help="judge backend (default: ollama, offline)",
    )
    parser.add_argument("--judge-model", default=None, help="override the judge's model")
    parser.add_argument("--no-judge", action="store_true", help="grounding only, no LLM judge")
    parser.add_argument("--coach-model", default=coach_client.DEFAULT_MODEL)
    parser.add_argument(
        "--coach-temperature", type=float, default=0.0,
        help="coach sampling temperature (default 0 for a reproducible baseline)",
    )
    parser.add_argument("--depth", type=int, default=15, help="Stockfish search depth")
    parser.add_argument(
        "--max-judge-calls", type=int, default=50,
        help="refuse to start if the run would make more judge calls than this (spend guard)",
    )
    parser.add_argument("--out", type=Path, default=None, help="write the full JSON report here")
    parser.add_argument(
        "--resume", action="store_true",
        help="reuse per-game results already in the sidecar <out>.partial.jsonl and only "
        "evaluate the games missing from it (requires --out)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cases = load_cases(args.manifest)
    if not cases:
        print(f"No cases in {args.manifest}", file=sys.stderr)
        return 1

    coach_fn = make_coach_fn(args.coach_model, args.coach_temperature)
    judge_desc = "none"
    judge_fn = None
    if not args.no_judge:
        # Spend guard: one judge call per game. Fail fast before spending anything.
        if len(cases) > args.max_judge_calls:
            print(
                f"Refusing to start: {len(cases)} judge calls exceeds "
                f"--max-judge-calls {args.max_judge_calls}.",
                file=sys.stderr,
            )
            return 1
        backend = _JUDGE_BACKENDS[args.judge]
        judge_fn = make_judge_fn(backend, args.judge_model)
        judge_desc = args.judge_model or (
            backends.DEFAULT_ANTHROPIC_MODEL if args.judge == "anthropic"
            else backends.DEFAULT_GEMINI_MODEL if args.judge == "gemini"
            else args.coach_model  # ollama judge defaults to the coach model
        )
        if args.judge != "ollama":
            print(
                f"Judging {len(cases)} games with {args.judge} ({judge_desc}) — "
                f"~{len(cases)} API calls.",
                file=sys.stderr,
            )

    done = (load_partial(args.out, args.coach_model, judge_desc)
            if (args.resume and args.out) else {})
    if done:
        print(f"Resuming: {len(done)} game(s) already scored, "
              f"{len(cases) - len(done)} to go.", file=sys.stderr)

    records = []
    for i, case in enumerate(cases, 1):
        key = (case.pgn.name, case.coached_side)
        if key in done:
            print(f"[{i}/{len(cases)}] {case.pgn.name} (coach {case.coached_side}) — cached",
                  file=sys.stderr)
            records.append(done[key])
            continue
        print(f"[{i}/{len(cases)}] {case.pgn.name} (coach {case.coached_side})...",
              file=sys.stderr)
        report = analyze_case(case, args.depth)
        record = evaluate_case(case, report, coach_fn, judge_fn)
        records.append(record)
        if args.out:
            append_partial(args.out, record, args.coach_model, judge_desc)

    agg = aggregate(records)
    summary = format_summary(agg, args.coach_model, judge_desc)
    print(summary)

    if args.out:
        payload = {
            "coach_model": args.coach_model,
            "coach_temperature": args.coach_temperature,
            "judge": args.judge if not args.no_judge else None,
            "judge_model": judge_desc if not args.no_judge else None,
            "depth": args.depth,
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
