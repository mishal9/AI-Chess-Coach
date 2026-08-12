"""Re-score a committed eval report's grounding offline, after a change to the metric.

When the grounding metric is corrected, every historical number becomes incomparable with
every new one — but re-running ``eval.run`` costs GPU time, Stockfish time and (with a
judge) real money, and would score *fresh* coaching rather than the coaching those reports
actually contain. Since the coaching text is stored, grounding can be recomputed exactly
where the allowed-move set is recoverable.

Reports written before this module stored only ``score``/``grounded``/``hallucinated``.
For those, the allowed set is reconstructed on the identity ``hallucinated = cited -
allowed``: re-extract ``cited`` with the *old* parser, and any token the new parser still
cites which was flagged before is still hallucinated. This is exact **only** while the
change leaves facts-side extraction untouched — which the bare-square fix does (verified:
0 of 1367 allowed tokens across the v2 distillation set changed). ``--verify`` re-derives
each stored score from the stored fields and refuses to run if any disagrees, so a report
this assumption does not hold for cannot be silently mis-scored.

Newer reports persist ``cited`` and ``allowed`` directly (see ``eval.run``), so they are
re-scored straight from the stored allowed set with no reconstruction at all.

Usage:
    python -m eval.rescore eval/reports/8b_v2_2026-08-10.json           # print the diff
    python -m eval.rescore eval/reports/*.json --out eval/reports/rescored_2026-08-11.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from eval import grounding

# The parser as it stood before bare-square disambiguation: every SAN-shaped token counts.
_LEGACY_SAN_RE = re.compile(
    r"(?<![\w])"
    r"(?:[O0]-[O0](?:-[O0])?"
    r"|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?)"
    r"[+#]?"
)


def legacy_extract_moves(text: str) -> set[str]:
    """Reproduce the pre-fix extractor, for reconstructing historical ``cited`` sets."""
    return {grounding._normalize(m) for m in _LEGACY_SAN_RE.findall(text)}


def rescore_game(game: dict) -> dict:
    """Return ``{score, grounded, hallucinated}`` for one stored game under the current
    metric. Uses the persisted allowed set when present, else reconstructs it."""
    coaching = game["coaching"]
    stored = game["grounding"]
    cited = grounding.extract_moves(coaching)

    if "allowed" in stored:
        hallucinated = cited - set(stored["allowed"])
    else:
        # cited - allowed == hallucinated, and the new cited set is a subset of the old,
        # so anything still cited that was flagged before remains unaccounted for.
        hallucinated = cited & set(stored["hallucinated"])

    score = 1.0 if not cited else 1.0 - len(hallucinated) / len(cited)
    return {
        "score": round(score, 3),
        "grounded": not hallucinated,
        "hallucinated": sorted(hallucinated),
        "cited": sorted(cited),
    }


def verify_reconstruction(game: dict) -> bool:
    """Does the stored score follow from the stored fields under the legacy parser?

    If not, the report was written by a different metric than we assume and its allowed
    set cannot be reconstructed.
    """
    stored = game["grounding"]
    if "allowed" in stored:
        return True
    cited = legacy_extract_moves(game["coaching"])
    hallucinated = set(stored["hallucinated"])
    if hallucinated - cited:
        return False
    expected = 1.0 if not cited else 1.0 - len(hallucinated) / len(cited)
    return abs(expected - stored["score"]) <= 1.1e-3  # stored scores are rounded to 3dp


def rescore_report(report: dict) -> dict:
    """Re-score every game and recompute the two grounding aggregates."""
    games = [dict(g, grounding=rescore_game(g)) for g in report["games"]]
    n = len(games) or 1
    aggregate = dict(report.get("aggregate", {}))
    aggregate["grounding_mean"] = round(
        sum(g["grounding"]["score"] for g in games) / n, 3
    )
    aggregate["grounded_rate"] = round(
        sum(g["grounding"]["grounded"] for g in games) / n, 3
    )
    return dict(report, games=games, aggregate=aggregate)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Re-score committed eval reports under the current grounding metric."
    )
    parser.add_argument("reports", type=Path, nargs="+", help="eval report JSON files")
    parser.add_argument(
        "--out", type=Path, default=None,
        help="write the re-scored report here (single input only; default: print only)",
    )
    parser.add_argument(
        "--no-verify", action="store_true",
        help="skip the reconstruction check (only for reports with a stored allowed set)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.out and len(args.reports) > 1:
        print("--out takes a single report.", file=sys.stderr)
        return 1

    print(f"{'report':<32}{'old':>8}{'new':>8}{'delta':>8}   grounded games")
    for path in args.reports:
        report = json.loads(path.read_text(encoding="utf-8"))
        games = report["games"]

        if not args.no_verify:
            bad = [g["pgn"] for g in games if not verify_reconstruction(g)]
            if bad:
                print(
                    f"\n{path.name}: cannot reconstruct the allowed set for "
                    f"{len(bad)} game(s) (e.g. {bad[0]}) — the stored score does not "
                    "follow from the stored fields, so this report predates the metric "
                    "this tool assumes. Re-run eval.run instead.",
                    file=sys.stderr,
                )
                return 1

        new = rescore_report(report)
        n = len(games) or 1
        old_mean = sum(g["grounding"]["score"] for g in games) / n
        old_grounded = sum(g["grounding"]["grounded"] for g in games)
        new_mean = new["aggregate"]["grounding_mean"]
        new_grounded = sum(g["grounding"]["grounded"] for g in new["games"])
        print(
            f"{path.stem:<32}{old_mean:>8.3f}{new_mean:>8.3f}{new_mean - old_mean:>+8.3f}"
            f"   {old_grounded}/{n} -> {new_grounded}/{n}"
        )

        if args.out:
            new["rescored_from"] = path.name
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(new, indent=2) + "\n", encoding="utf-8")
            print(f"\nWrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
