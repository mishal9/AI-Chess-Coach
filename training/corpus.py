"""Assemble a distillation *training corpus* — CC0 games disjoint from the held-out set.

Phase 3 needs source games to distill coaching from. They must be **strictly disjoint**
from ``eval/heldout/`` — any overlap leaks the scoreboard and makes the Phase-4 win
meaningless. This module is the guard: it fetches public CC0 games (Lichess), splits the
multi-game PGN into individual games, and drops every game that collides with a held-out
game — matched by both its Lichess ``GameId`` *and* a normalized-movetext hash, so a game
with stripped tags can't sneak through. What survives is written to ``data/games/`` as a
single ``corpus.pgn`` plus a ``manifest.json`` that ``training.distill`` consumes directly.

The fetch is injectable and every filtering step is a pure function, so disjointness, the
dedup, and the length filter are unit-tested with no network.

Usage:
    # fetch from Lichess (CC0 game exports), dedup against held-out, write the corpus
    python -m training.corpus --user DrNykterstein --user Sharkfang --max 40

    # or assemble from PGN files you already have
    python -m training.corpus --input data/raw/sample.pgn --input more.pgn
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Callable

from engine import fetch_data
from engine.pgn import game_key, movetext_hash, split_pgn
from engine.pgn import normalized_movetext as _normalized_movetext

# Lichess's own guidance is "only run 1 request at a time" — this is the gap between
# sequential per-user fetches in a multi-user loop (here, and in eval.expand_heldout,
# which fetches the same way). A burst of back-to-back calls with no gap is exactly what
# earns a 429, and repeated 429s into an active block have been observed to extend it far
# past the base ~1-minute cooldown, rather than reset it. Tests monkeypatch this to 0 so
# an injected fake fetcher doesn't slow the suite down.
FETCH_PACING_SECONDS = 3.0


def _paced(users: list[str]):
    """Yield ``users``, sleeping ``FETCH_PACING_SECONDS`` before every one after the first."""
    for i, user in enumerate(users):
        if i > 0:
            time.sleep(FETCH_PACING_SECONDS)
        yield user

HELDOUT_DIR = Path(__file__).resolve().parent.parent / "eval" / "heldout"
DEFAULT_OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "games"

# A roster spanning the rating ladder, so the coach distills from mistakes at every level
# rather than near-clean GM play. The Maia bots play calibrated *human-like* moves at a fixed
# Elo, so their games carry the instructive errors a coaching model most needs to explain.
DEFAULT_USERS = [
    "maia1",          # ~1100 Elo bot (Maia) — beginner blunders, the richest coaching signal
    "maia5",          # ~1500 Elo bot — club level
    "maia9",          # ~1900 Elo bot — strong club
    "EricRosen",      # IM — instructive, human, well-annotated attacking games
    "DrNykterstein",  # Magnus Carlsen (super-GM) — near-clean reference games
]

# A fetcher takes (user, max_games) and returns the raw multi-game PGN text.
FetchFn = Callable[[str, int], str]


def heldout_fingerprints(heldout_dir: Path = HELDOUT_DIR) -> set[str]:
    """Every identity a held-out game can be recognized by: its id *and* its movetext hash.

    Returning both means a corpus game collides if it shares *either* with any held-out
    game — so a re-export that dropped the ``GameId`` tag is still caught by its moves.
    """
    prints: set[str] = set()
    for pgn_file in sorted(heldout_dir.glob("*.pgn")):
        for game in split_pgn(pgn_file.read_text(encoding="utf-8")):
            prints.add(game_key(game))
            prints.add(f"moves:{movetext_hash(game)}")
    return prints


def _ply_count(pgn: str) -> int:
    """Rough number of half-moves: count SAN-ish tokens in the (comment-stripped) movetext."""
    moves = _normalized_movetext(pgn)
    moves = re.sub(r"\d+\.(\.\.)?", " ", moves)          # drop move numbers "12." / "12..."
    moves = re.sub(r"\b(1-0|0-1|1/2-1/2|\*)\b", " ", moves)  # drop the result token
    return len([t for t in moves.split() if any(c.isalpha() for c in t)])


def assemble(
    games: list[str],
    heldout: set[str],
    *,
    min_plies: int = 10,
) -> list[str]:
    """Dedup ``games`` against the held-out set and each other, dropping games too short.

    Order is preserved; the first occurrence of a duplicate wins. A game is excluded when
    its :func:`game_key` *or* its movetext hash matches any held-out fingerprint.
    """
    kept: list[str] = []
    seen: set[str] = set(heldout)
    for game in games:
        key = game_key(game)
        move_key = f"moves:{movetext_hash(game)}"
        if key in seen or move_key in seen:
            continue
        if _ply_count(game) < min_plies:
            continue
        seen.add(key)
        seen.add(move_key)
        kept.append(game)
    return kept


def canonical_order(games: list[str], seed: int = 0) -> list[str]:
    """Order ``games`` by a stable hash of each game's own identity, not fetch order.

    ``assemble`` orders games however the fetcher happened to return them — for Lichess,
    newest-first on the day of the call, which drifts as a player keeps playing. A data-scale
    sweep needs its sizes **nested** (the 1,000-row tier is a superset of the 400-row tier)
    and **reproducible** months later against a corpus that has moved on. Sorting by
    :func:`training.dataset.bucket_value` of each game's :func:`~engine.pgn.game_key` gives
    an order that depends only on each game's own identity, so row-count prefixes of a raw
    JSONL distilled in this order are the same games every time, regardless of when the
    corpus was fetched or reassembled. See ``docs/experiments/paper-protocol.md``.
    """
    from training.dataset import bucket_value

    return sorted(games, key=lambda pgn: bucket_value(game_key(pgn), seed))


def write_corpus(games: list[str], out_dir: Path) -> Path:
    """Write ``games`` to ``out_dir/corpus.pgn`` + a distill-ready ``manifest.json``.

    The manifest points every entry at the single ``corpus.pgn`` by ``game_index`` and
    leaves ``coached_side`` null, so ``training.distill`` auto-picks the worse-playing
    side per game. Returns the manifest path.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    corpus_path = out_dir / "corpus.pgn"
    corpus_path.write_text("\n\n".join(games) + "\n", encoding="utf-8")

    manifest = [
        {"pgn": "corpus.pgn", "game_index": i, "coached_side": None}
        for i in range(len(games))
    ]
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def _lichess_fetch(user: str, max_games: int) -> str:
    """Default fetcher: pull a user's games as PGN via Lichess."""
    return fetch_data.fetch_lichess_games(user, max_games)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Assemble a distillation corpus disjoint from the held-out set."
    )
    parser.add_argument("--user", action="append", default=[],
                        help="Lichess username to fetch (repeatable); "
                             "defaults to a rating-spanning roster if omitted")
    parser.add_argument("--input", type=Path, action="append", default=[],
                        help="use an existing .pgn file instead of fetching (repeatable)")
    parser.add_argument("--max", type=int, default=20,
                        help="max games to fetch per --user (default: 20)")
    parser.add_argument("--min-plies", type=int, default=10,
                        help="drop games shorter than this many half-moves (default: 10)")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR,
                        help="write corpus.pgn + manifest.json here (default: data/games/)")
    parser.add_argument(
        "--canonical-seed", type=int, default=None,
        help="order games by a stable hash of game identity (see canonical_order) instead "
        "of fetch order, seeded by this value — for a reproducible data-scale sweep, "
        "where row-count prefixes of the resulting raw JSONL must stay the same games "
        "across re-fetches. Default: keep fetch order (unset).",
    )
    return parser


def main(argv: list[str] | None = None, fetch_fn: FetchFn = _lichess_fetch) -> int:
    args = build_parser().parse_args(argv)
    users = list(args.user)
    if not users and not args.input:
        users = list(DEFAULT_USERS)
        print(f"No --user/--input given; using the default rating-spanning roster: "
              f"{', '.join(users)}.", file=sys.stderr)

    raw: list[str] = []
    for path in args.input:
        raw.extend(split_pgn(path.read_text(encoding="utf-8")))
    for user in _paced(users):
        print(f"Fetching up to {args.max} games for '{user}'...", file=sys.stderr)
        raw.extend(split_pgn(fetch_fn(user, args.max)))

    heldout = heldout_fingerprints()
    games = assemble(raw, heldout, min_plies=args.min_plies)
    if not games:
        print(f"No games survived assembly ({len(raw)} fetched).", file=sys.stderr)
        return 1
    if args.canonical_seed is not None:
        games = canonical_order(games, args.canonical_seed)

    dropped = len(raw) - len(games)
    manifest_path = write_corpus(games, args.out_dir)
    print(
        f"Wrote {len(games)} games to {args.out_dir / 'corpus.pgn'} "
        f"({dropped} dropped as held-out/duplicate/too-short).\n"
        f"Manifest: {manifest_path}  —  distill with "
        f"`python -m training.distill --sources {manifest_path}`.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
