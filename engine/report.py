"""CLI: analyze a PGN game and emit an objective mistake report.

This is the Phase-1 deliverable — a command-line tool that takes a PGN and produces
the structured "what went wrong" report (JSON) plus a human-readable summary, entirely
from engine analysis (no LLM yet).

Usage:
    python -m engine.report game.pgn                     # readable summary
    python -m engine.report game.pgn --json report.json  # + write full JSON
    python -m engine.report game.pgn --json -            # write JSON to stdout
    python -m engine.report game.pgn --game-index 2 --depth 18 --top 8
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from engine.analyzer import DEFAULT_DEPTH, GameReport, MoveAnalysis, analyze_game
from engine.loader import iter_games
from engine.scoring import MoveQuality

# Moves worth surfacing in the "notable mistakes" list, worst first.
_MISTAKE_QUALITIES = {
    MoveQuality.INACCURACY,
    MoveQuality.MISTAKE,
    MoveQuality.BLUNDER,
}


def _move_label(m: MoveAnalysis) -> str:
    """Chess-notation move number, e.g. '12.' for White or '12...' for Black."""
    return f"{m.move_number}." if m.side == "white" else f"{m.move_number}..."


def _format_move_line(m: MoveAnalysis) -> str:
    best = f", best {m.best_san}" if m.best_san and m.best_san != m.san else ""
    return (
        f"  {_move_label(m)} {m.san}{m.quality.symbol}"
        f"  ({m.side}, {m.quality.value})  "
        f"cp -{m.cp_loss}, win% -{m.win_prob_loss * 100:.0f}{best}"
    )


def format_summary(report: GameReport, depth: int, top: int) -> str:
    """Render a human-readable summary of the report."""
    s = report.summary
    lines = [
        f"{report.white} vs {report.black}   {report.result}"
        f"   | {report.eco} {report.opening}",
        f"{len(report.moves)} plies analyzed at depth {depth}",
        "",
        f"ACPL   White: {s['acpl_white']}   Black: {s['acpl_black']}",
        f"Blunders: {s['blunders']}   Mistakes: {s['mistakes']}"
        f"   Inaccuracies: {s['inaccuracies']}",
    ]

    worst = s["worst_move"]
    if worst is not None:
        best = f" (best {worst['best']})" if worst["best"] else ""
        lines.append(
            f"Worst move: {worst['move_number']}. {worst['side']} played "
            f"{worst['played']}{best} — win% -{worst['win_prob_loss'] * 100:.0f}"
        )

    notable = sorted(
        (m for m in report.moves if m.quality in _MISTAKE_QUALITIES),
        key=lambda m: m.win_prob_loss,
        reverse=True,
    )[:top]
    if notable:
        lines.append("")
        lines.append(f"Top {len(notable)} mistakes:")
        lines.extend(_format_move_line(m) for m in notable)

    return "\n".join(lines)


def load_game(pgn_path: Path, game_index: int):
    """Return the game at ``game_index`` (0-based) in ``pgn_path``, or ``None``."""
    for i, game in enumerate(iter_games(pgn_path)):
        if i == game_index:
            return game
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Analyze a PGN game and emit an objective mistake report."
    )
    parser.add_argument("pgn", help="path to a .pgn file")
    parser.add_argument(
        "--depth", type=int, default=DEFAULT_DEPTH, help="Stockfish search depth"
    )
    parser.add_argument(
        "--game-index", type=int, default=0, help="0-based index of the game to analyze"
    )
    parser.add_argument(
        "--json",
        metavar="PATH",
        help="write the full JSON report to PATH (use '-' for stdout)",
    )
    parser.add_argument(
        "--top", type=int, default=5, help="how many notable mistakes to list"
    )
    args = parser.parse_args(argv)

    path = Path(args.pgn)
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        print("Tip: run `python -m engine.fetch_data --sample` first.", file=sys.stderr)
        return 1

    game = load_game(path, args.game_index)
    if game is None:
        print(
            f"No game at index {args.game_index} in {path}.", file=sys.stderr
        )
        return 1

    report = analyze_game(game, depth=args.depth)

    if args.json:
        payload = json.dumps(report.to_dict(), indent=2)
        if args.json == "-":
            print(payload)
        else:
            Path(args.json).write_text(payload, encoding="utf-8")
            print(f"Wrote JSON report to {args.json}", file=sys.stderr)

    # Always print the readable summary (to stderr when JSON goes to stdout, so the
    # two streams stay cleanly separable for piping).
    stream = sys.stderr if args.json == "-" else sys.stdout
    print(format_summary(report, args.depth, args.top), file=stream)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
