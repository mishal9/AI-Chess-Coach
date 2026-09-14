"""CLI: turn a game into natural-language coaching.

End-to-end "PGN in -> coaching text out" with the local Ollama coach model. Can also coach
from a JSON report already produced by ``python -m engine.report --json``, which skips
re-running Stockfish.

Usage:
    python -m coach.coach game.pgn                       # analyze + coach (auto side)
    python -m coach.coach game.pgn --side black          # coach a specific side
    python -m coach.coach game.pgn --depth 18 --game-index 1
    python -m coach.coach --from-json report.json        # coach a saved report
    python -m coach.coach game.pgn --show-facts          # print the facts block only

    # coach against the player's stored history, then remember this game too
    python -m coach.coach game.pgn --user mshah509 --remember
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from coach import client, prompts
from engine.analyzer import DEFAULT_DEPTH, analyze_game
from engine.pgn import load_game


def report_from_pgn(pgn_path: Path, game_index: int, depth: int) -> dict:
    """Analyze a game from a PGN file and return the report dict.

    Stockfish is only launched here, so ``--from-json`` works without it installed.
    """
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
    parser.add_argument(
        "--depth", type=int, default=DEFAULT_DEPTH, help="Stockfish search depth"
    )
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
    parser.add_argument(
        "--user",
        help="coach against this player's stored history (see memory.store)",
    )
    parser.add_argument(
        "--db", help="memory database to read history from (default: data/memory.db)"
    )
    parser.add_argument(
        "--last",
        type=int,
        help="only summarise this many most-recent games in the history",
    )
    parser.add_argument(
        "--remember",
        action="store_true",
        help="also store this game in --user's memory after coaching",
    )
    return parser


def load_profile(args: argparse.Namespace) -> str | None:
    """Plain-text history for ``--user``, or ``None`` (see :func:`memory.profile.profile_text`)."""
    if not args.user:
        return None
    # Imported lazily so plain coaching needs neither sqlite nor the memory package.
    from memory.profile import profile_text
    from memory.store import DEFAULT_DB, connect

    return profile_text(connect(args.db or DEFAULT_DB), args.user, args.last)


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

    if args.user:
        # Resolve the side from the player's name where possible, so `--user` coaches
        # *you* rather than whoever happened to play worse.
        from memory.store import resolve_side

        coached_side = resolve_side(report, args.user, args.side)
    else:
        coached_side = args.side or prompts.choose_coached_side(report)

    # Built before this game is stored: a history that already included the game being
    # coached would let "the fourth time" count itself.
    profile = load_profile(args)
    messages = prompts.build_messages(report, coached_side, args.max_mistakes, profile)

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

    if args.remember:
        remember(args, report, coached_side)
    return 0


def remember(args: argparse.Namespace, report: dict, coached_side: str) -> None:
    """Store the just-coached game in the player's memory, if we can identify it."""
    if not args.user:
        print("Nothing remembered: --remember needs --user.", file=sys.stderr)
        return
    if not args.pgn:
        # A saved JSON report has no movetext, and movetext is the dedup key.
        print(
            "Nothing remembered: --remember needs the PGN (not --from-json).",
            file=sys.stderr,
        )
        return

    from memory.store import DEFAULT_DB, connect, ingest_game
    from engine.pgn import split_pgn

    games = split_pgn(Path(args.pgn).read_text(encoding="utf-8"))
    if args.game_index >= len(games):  # pragma: no cover - load_report already checked
        return
    conn = connect(args.db or DEFAULT_DB)
    stored = ingest_game(
        conn,
        games[args.game_index],
        report,
        args.user,
        side=coached_side,
        depth=args.depth,
    )
    print(
        f"Remembered this game for {args.user}."
        if stored
        else f"Already in {args.user}'s memory — not counted twice.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    raise SystemExit(main())
