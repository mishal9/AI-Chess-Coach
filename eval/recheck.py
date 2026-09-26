"""Backfill engine-dependent deterministic metrics onto a committed eval report.

``eval.rescore`` recomputes grounding from what a report already stores. The claim checks
(``eval.claims``) need the *analyzed game* as well — piece placement is settled by
replaying positions, and castling by the full move list — so backfilling them means
re-running Stockfish over the held-out set. That costs CPU time and nothing else: no
model, no judge, no API key.

Two uses, both of which have already come up once:

* reports written before :mod:`eval.claims` existed (#43) carry no ``claims`` block, so a
  new run has nothing to be compared against;
* a later change to the claim checker makes old numbers incomparable, exactly as the
  bare-square fix did to grounding.

**Joining a report to its games.** Reports written before #43 do not record
``game_index``, and a bucket file holds several games, so the name alone does not identify
one. They are instead joined *positionally*: ``eval.run`` iterates the manifest in order,
so record *i* is manifest entry *i* — the same assumption ``eval.compare`` already pairs
on. That is verified rather than trusted: each record's ``pgn`` and ``coached_side`` must
match its manifest entry, and its stored grounding score and hallucinated set must be
reproducible from the facts block that entry generates. A report failing either check is
refused.

Usage:
    python -m eval.recheck eval/reports/8b_v2_2026-08-10.json --out eval/reports/rechecked.json
    python -m eval.recheck eval/reports/*.json --summary-only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from coach import prompts
from eval import claims, rescore

HELDOUT_DIR = Path(__file__).resolve().parent / "heldout"
DEFAULT_MANIFEST = HELDOUT_DIR / "manifest.json"


def report_depth(report: dict, override: int | None = None) -> int:
    """The Stockfish depth to rebuild ``report``'s facts at: the depth it was run at.

    Facts blocks change with depth, so re-checking or re-judging a report at any other
    depth would score its coaching against facts it was never given. An ``override`` that
    disagrees with the stored depth is refused for the same reason; one is required only
    for a report that does not record its depth.
    """
    stored = report.get("depth")
    if override is None:
        if stored is None:
            raise ValueError("report does not record its Stockfish depth; pass --depth")
        return stored
    if stored is not None and stored != override:
        raise ValueError(
            f"report was run at depth {stored}, not {override}; its facts would not match"
        )
    return override


def analyze_manifest(manifest_path: Path, depth: int) -> list[dict]:
    """Analyze every game in the manifest, in manifest order.

    Returns one ``{pgn, game_index, coached_side, report, facts}`` per entry. The engine
    is imported lazily so importing this module needs no Stockfish.
    """
    from engine.analyzer import analyze_game
    from engine.pgn import load_game

    entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    base = manifest_path.parent
    out = []
    for i, entry in enumerate(entries, 1):
        game_index = entry.get("game_index", 0)
        game = load_game(base / entry["pgn"], game_index)
        if game is None:
            raise SystemExit(f"No game at index {game_index} in {entry['pgn']}")
        report = analyze_game(game, depth=depth).to_dict()
        side = entry.get("coached_side") or prompts.choose_coached_side(report)
        out.append({
            "pgn": entry["pgn"],
            "game_index": game_index,
            "coached_side": side,
            "report": report,
            "facts": prompts.format_report_facts(report, side),
        })
        print(f"[{i}/{len(entries)}] {entry['pgn']}#{game_index}", file=sys.stderr,
              flush=True)
    return out


def verify_alignment(games: list[dict], analyzed: list[dict]) -> list[str]:
    """Return the reasons a positional join is unsafe — empty when it holds.

    Checks identity (pgn + coached side) and, independently, that the stored grounding
    score and hallucinated set fall out of the matched facts block under the parser that
    wrote them.
    """
    problems = []
    if len(games) != len(analyzed):
        return [f"report has {len(games)} games, manifest has {len(analyzed)}"]

    for i, (game, entry) in enumerate(zip(games, analyzed)):
        if game["pgn"] != entry["pgn"] or game["coached_side"] != entry["coached_side"]:
            problems.append(
                f"[{i}] {game['pgn']}/{game['coached_side']} does not match manifest "
                f"{entry['pgn']}/{entry['coached_side']}"
            )
            continue
        if "game_index" in game and game["game_index"] != entry["game_index"]:
            problems.append(f"[{i}] {game['pgn']} game_index disagrees with manifest")
            continue
        cited = rescore.legacy_extract_moves(game["coaching"])
        hallucinated = cited - rescore.legacy_extract_moves(entry["facts"])
        score = 1.0 if not cited else 1.0 - len(hallucinated) / len(cited)
        stored = game["grounding"]
        if hallucinated != set(stored["hallucinated"]):
            problems.append(
                f"[{i}] {game['pgn']}: hallucinated set does not reproduce "
                f"({sorted(hallucinated)} vs {sorted(stored['hallucinated'])})"
            )
        elif abs(score - stored["score"]) > 1.1e-3:
            problems.append(
                f"[{i}] {game['pgn']}: grounding {score:.3f} does not reproduce "
                f"stored {stored['score']}"
            )
    return problems


def recheck_report(report: dict, analyzed: list[dict]) -> dict:
    """Attach a fresh ``claims`` block to every game and to the aggregate."""
    games = []
    for game, entry in zip(report["games"], analyzed):
        result = claims.check_claims_from_report(
            game["coaching"], entry["report"], entry["coached_side"],
            facts=entry["facts"],   # the exact block the join was verified against
        )
        games.append(dict(game, game_index=entry["game_index"], claims=result.to_dict()))

    n = len(games) or 1
    aggregate = dict(report.get("aggregate", {}))
    aggregate["claims_mean"] = round(sum(g["claims"]["score"] for g in games) / n, 3)
    aggregate["claims_ok_rate"] = round(sum(g["claims"]["ok"] for g in games) / n, 3)
    # Same reason as eval.rescore: mark which semantics these claim scores are on.
    versions = dict(report.get("metric_versions") or {})
    versions["claims"] = claims.METRIC_VERSION
    return dict(report, games=games, aggregate=aggregate, metric_versions=versions)


def violation_counts(report: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for game in report["games"]:
        for violation in game["claims"]["violations"]:
            counts[violation["kind"]] = counts.get(violation["kind"], 0) + 1
    return counts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backfill claim checks onto committed eval reports (engine, no API)."
    )
    parser.add_argument("reports", type=Path, nargs="+")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--depth", type=int, default=None,
                        help="Stockfish depth (default: the depth each report records)")
    parser.add_argument("--out", type=Path, default=None,
                        help="write the rechecked report here (single input only)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.out and len(args.reports) > 1:
        print("--out takes a single report.", file=sys.stderr)
        return 1

    reports = {path: json.loads(path.read_text(encoding="utf-8")) for path in args.reports}
    try:
        depths = {report_depth(r, args.depth) for r in reports.values()}
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if len(depths) > 1:
        print(f"These reports were run at different depths {sorted(depths)}; "
              "recheck them separately.", file=sys.stderr)
        return 1
    analyzed = analyze_manifest(args.manifest, depths.pop())

    print(f"\n{'report':<28}{'claims':>8}{'clean':>9}   violations")
    for path, report in reports.items():
        problems = verify_alignment(report["games"], analyzed)
        if problems:
            print(
                f"\n{path.name}: refusing to backfill — the positional join does not hold:\n  "
                + "\n  ".join(problems[:5]),
                file=sys.stderr,
            )
            return 1

        rechecked = recheck_report(report, analyzed)
        n = len(rechecked["games"])
        clean = sum(g["claims"]["ok"] for g in rechecked["games"])
        print(
            f"{path.stem:<28}{rechecked['aggregate']['claims_mean']:>8.3f}"
            f"{clean:>6}/{n}   {violation_counts(rechecked) or '-'}"
        )
        if args.out:
            rechecked["rechecked_from"] = path.name
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(rechecked, indent=2) + "\n", encoding="utf-8")
            print(f"\nWrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
