"""CLI: turn a game into natural-language coaching (Phase 2 deliverable).

End-to-end "PGN in -> coaching text out", using only prompting of a local base model.
Can also coach from a JSON report already produced by ``python -m engine.report --json``,
which skips re-running Stockfish.

Usage:
    python -m coach.coach game.pgn                       # analyze + coach (auto side)
    python -m coach.coach game.pgn --side black          # coach a specific side
    python -m coach.coach game.pgn --depth 18 --game-index 1
    python -m coach.coach --from-json report.json        # coach a saved report
    python -m coach.coach game.pgn --show-facts          # print the facts block only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from coach import client, prompts


def report_from_pgn(pgn_path: Path, game_index: int, depth: int) -> dict:
    """Analyze a game from a PGN file and return the report dict."""
    # Imported lazily so `--from-json` works without a Stockfish install.
    from engine.analyzer import analyze_game
    from engine.report import load_game

    game = load_game(pgn_path, game_index)
    if game is None:
        raise SystemExit(f"No game at index {game_index} in {pgn_path}.")
    return analyze_game(game, depth=depth).to_dict()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate natural-language coaching for a chess game."
    )
    parser.add_argument("pgn", nargs="?", help="path to a .pgn file to analyze")
    parser.add_argument(
        "--from-json",
        metavar="PATH",
        help="coach a saved JSON report instead of analyzing a PGN",
    )
    parser.add_argument(
        "--side",
        choices=("white", "black"),
        help="which side to coach (default: the side that played worse)",
    )
    parser.add_argument("--depth", type=int, default=15, help="Stockfish search depth")
    parser.add_argument(
        "--game-index", type=int, default=0, help="0-based index of the game in the PGN"
    )
    parser.add_argument(
        "--max-mistakes", type=int, default=6, help="how many mistakes to feed the model"
    )
    parser.add_argument(
        "--model", default=client.DEFAULT_MODEL, help="Ollama model tag"
    )
    parser.add_argument(
        "--temperature", type=float, default=client.DEFAULT_TEMPERATURE
    )
    parser.add_argument(
        "--show-facts",
        action="store_true",
        help="print the facts block sent to the model and exit (no LLM call)",
    )
    return parser


def load_report(args: argparse.Namespace) -> dict:
    """Resolve the report dict from either --from-json or a PGN path."""
    if args.from_json:
        return json.loads(Path(args.from_json).read_text(encoding="utf-8"))
    if not args.pgn:
        raise SystemExit("Provide a PGN path or --from-json PATH. See --help.")
    path = Path(args.pgn)
    if not path.exists():
        raise SystemExit(f"File not found: {path}")
    return report_from_pgn(path, args.game_index, args.depth)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = load_report(args)

    coached_side = args.side or prompts.choose_coached_side(report)
    messages = prompts.build_messages(report, coached_side, args.max_mistakes)

    if args.show_facts:
        # The user message carries the facts block; print it for inspection/debugging.
        print(messages[-1]["content"])
        return 0

    try:
        coaching = client.chat(
            messages, model=args.model, temperature=args.temperature
        )
    except client.CoachModelError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(coaching)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
