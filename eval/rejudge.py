"""Re-score a committed report's coaching with a different judge.

``eval.run --judge gemini`` would regenerate the coaching as well as re-judge it, so the
new numbers would differ for two reasons at once — different judge *and* different
sampling — and neither could be attributed. This re-judges the **stored text**, leaving
the judge as the only thing that changed. That is what makes cross-judge agreement
measurable rather than merely suggestive.

The facts are rebuilt by re-analyzing each held-out game, exactly as :mod:`eval.recheck`
does, so the judge sees the same facts block the coach was given. Stockfish is
deterministic at a fixed depth, so this reproduces the original block rather than
approximating it.

The output is a normal report with ``judge_model`` restamped, which means
``eval.equivalence`` and ``eval.compare`` will refuse to mix it with the original — as
they should, since a rubric score is meaningless apart from its ruler.

Usage:
    python -m eval.rejudge eval/reports/8b_v2_2026-08-10.json \\
        --judge gemini --out eval/reports/8b_v2_gemini.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from eval.judge import judge_coaching
from eval.recheck import DEFAULT_MANIFEST, analyze_manifest, report_depth
from eval.run import _JUDGE_BACKENDS, aggregate

# Judge names exactly as `eval.run` spells them, so `--judge gemini` means the same thing
# in both tools.
JUDGES = dict(_JUDGE_BACKENDS)


def rejudge(
    report: dict,
    manifest_path: Path = DEFAULT_MANIFEST,
    judge: str = "gemini",
    judge_model: str | None = None,
    depth: int | None = None,
    limit: int | None = None,
    progress=None,
    out_path: Path | None = None,
) -> dict:
    """Return a copy of ``report`` with every rubric replaced by ``judge``'s scoring.

    ``out_path`` makes the run **resumable**: partial results are written after every
    judgement, and games already carrying a rubric from this judge are skipped on a later
    run. A free-tier daily quota is a hard stop that can land mid-run, and losing the
    judgements already paid for to it would be the same fragility ``eval.run`` was
    criticised for.
    """
    backend = JUDGES[judge]
    games = report["games"]
    analyzed = analyze_manifest(manifest_path, depth=report_depth(report, depth))

    if len(analyzed) != len(games):
        raise ValueError(
            f"manifest has {len(analyzed)} games but the report has {len(games)} — "
            "these are not the same evaluation set"
        )

    target_model = judge_model or _default_model_for(judge)

    # Resume from a partial file if one is there, so already-judged games are not redone.
    if out_path is not None and out_path.exists():
        out = json.loads(out_path.read_text(encoding="utf-8"))
    else:
        out = json.loads(json.dumps(report))  # deep copy; never mutate the input
    for i, (entry, game) in enumerate(zip(analyzed, out["games"])):
        if limit is not None and i >= limit:
            break
        # The same positional-join check eval.recheck makes: the manifest is the source of
        # order, but that assumption is verified rather than trusted.
        if game.get("pgn") and entry["pgn"] != game["pgn"]:
            raise ValueError(
                f"game {i}: manifest says {entry['pgn']!r}, report says {game['pgn']!r}"
            )
        text = game.get("coaching")
        if not text:
            continue
        if game.get("judged_by") == target_model:
            continue  # already scored by this judge on an earlier, interrupted run
        if progress:
            progress(i + 1, len(games), entry["pgn"])
        score = judge_coaching(
            text,
            entry["report"],
            game.get("coached_side"),
            backend=backend,
            model=judge_model,
        )
        game["rubric"] = {
            "scores": dict(score.scores),
            "overall": score.overall,
            "rationale": score.rationale,
        }
        game["judged_by"] = target_model
        if out_path is not None:
            _write(out_path, out)

    out["judge_model"] = target_model
    out["rejudged_from"] = report.get("judge_model")
    _reaggregate(out)
    return out


def _write(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def judged_count(report: dict, model: str) -> int:
    """How many games in this report carry a rubric from ``model``."""
    return sum(1 for g in report.get("games", []) if g.get("judged_by") == model)


def _default_model_for(judge: str) -> str:
    from eval import backends

    return {
        "anthropic": backends.DEFAULT_ANTHROPIC_MODEL,
        "gemini": backends.DEFAULT_GEMINI_MODEL,
    }.get(judge, getattr(backends, "DEFAULT_OLLAMA_MODEL", judge))


def _reaggregate(report: dict) -> None:
    """Recompute the summary from the per-game records, exactly as ``eval.run`` does.

    The summary must be rebuilt by that one definition: a parallel set of keys would leave
    the ``rubric_axis_means`` / ``rubric_overall_mean`` that readers use holding the
    *original* judge's numbers while the games carried the new judge's.
    """
    report["aggregate"] = aggregate(report["games"])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Re-judge a committed report's stored coaching with another judge."
    )
    parser.add_argument("report", type=Path)
    parser.add_argument("--judge", choices=sorted(JUDGES), default="gemini")
    parser.add_argument("--judge-model", default=None)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--depth", type=int, default=None,
                        help="Stockfish depth (default: the depth the report records)")
    parser.add_argument("--limit", type=int, default=None,
                        help="judge only the first N games (for a cheap smoke test)")
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = json.loads(args.report.read_text(encoding="utf-8"))

    def progress(i, total, name):
        print(f"[{i}/{total}] {name}", file=sys.stderr, flush=True)

    from eval.backends import GeminiDailyQuotaExhausted

    try:
        out = rejudge(
            report,
            manifest_path=args.manifest,
            judge=args.judge,
            judge_model=args.judge_model,
            depth=args.depth,
            limit=args.limit,
            progress=progress,
            out_path=args.out,
        )
    except GeminiDailyQuotaExhausted as exc:
        done = judged_count(
            json.loads(args.out.read_text(encoding="utf-8")) if args.out.exists() else {},
            args.judge_model or _default_model_for(args.judge),
        )
        print(f"\n{exc}\nKept {done} judgement(s) in {args.out}; re-run to continue.",
              file=sys.stderr)
        return 2

    _write(args.out, out)
    print(f"Wrote {args.out} (judge: {out['judge_model']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
