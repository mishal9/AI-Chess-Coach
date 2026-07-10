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
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Callable

HELDOUT_DIR = Path(__file__).resolve().parent.parent / "eval" / "heldout"
DEFAULT_OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "games"

# A game record in a PGN begins with its [Event ...] tag.
_EVENT_RE = re.compile(r"(?=^\[Event )", re.MULTILINE)
_GAMEID_RE = re.compile(r'^\[GameId\s+"([^"]+)"\]', re.MULTILINE)
_SITE_RE = re.compile(r'^\[Site\s+"([^"]+)"\]', re.MULTILINE)
_TAG_LINE_RE = re.compile(r"^\[.*\]\s*$", re.MULTILINE)
_COMMENT_RE = re.compile(r"\{[^}]*\}")  # inline PGN comments, e.g. Lichess { [%eval ...] }

# A fetcher takes (user, max_games) and returns the raw multi-game PGN text.
FetchFn = Callable[[str, int], str]


def split_pgn(text: str) -> list[str]:
    """Split a multi-game PGN blob into individual game strings (each with its tags)."""
    return [g.strip() for g in _EVENT_RE.split(text) if g.strip()]


def _normalized_movetext(pgn: str) -> str:
    """Movetext with tags and comments stripped and whitespace collapsed.

    Gives two exports of the *same* game one identity even if one carries ``%eval``
    comments or a different tag set than the other.
    """
    body = _TAG_LINE_RE.sub("", pgn)
    body = _COMMENT_RE.sub(" ", body)
    return " ".join(body.split())


def game_key(pgn: str) -> str:
    """A stable identity for one game, preferring its Lichess id, else a movetext hash.

    Returned keys are namespaced (``id:`` / ``moves:``) so an id and a hash never collide.
    """
    m = _GAMEID_RE.search(pgn)
    if not m:
        site = _SITE_RE.search(pgn)
        if site and "lichess.org/" in site.group(1):
            m_id = site.group(1).rstrip("/").rsplit("/", 1)[-1]
            if m_id:
                return f"id:{m_id}"
    if m:
        return f"id:{m.group(1)}"
    digest = hashlib.sha256(_normalized_movetext(pgn).encode("utf-8")).hexdigest()[:16]
    return f"moves:{digest}"


def heldout_fingerprints(heldout_dir: Path = HELDOUT_DIR) -> set[str]:
    """Every identity a held-out game can be recognized by: its id *and* its movetext hash.

    Returning both means a corpus game collides if it shares *either* with any held-out
    game — so a re-export that dropped the ``GameId`` tag is still caught by its moves.
    """
    prints: set[str] = set()
    for pgn_file in sorted(heldout_dir.glob("*.pgn")):
        for game in split_pgn(pgn_file.read_text(encoding="utf-8")):
            prints.add(game_key(game))
            digest = hashlib.sha256(
                _normalized_movetext(game).encode("utf-8")
            ).hexdigest()[:16]
            prints.add(f"moves:{digest}")
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
        digest = hashlib.sha256(
            _normalized_movetext(game).encode("utf-8")
        ).hexdigest()[:16]
        move_key = f"moves:{digest}"
        if key in seen or move_key in seen:
            continue
        if _ply_count(game) < min_plies:
            continue
        seen.add(key)
        seen.add(move_key)
        kept.append(game)
    return kept


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
    """Default fetcher: pull a user's games as PGN via Lichess (reuses engine.fetch_data)."""
    import tempfile

    from engine.fetch_data import fetch_lichess_games

    with tempfile.NamedTemporaryFile("r", suffix=".pgn", delete=True) as tmp:
        fetch_lichess_games(user, max_games, Path(tmp.name))
        return Path(tmp.name).read_text(encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Assemble a distillation corpus disjoint from the held-out set."
    )
    parser.add_argument("--user", action="append", default=[],
                        help="Lichess username to fetch (repeatable)")
    parser.add_argument("--input", type=Path, action="append", default=[],
                        help="use an existing .pgn file instead of fetching (repeatable)")
    parser.add_argument("--max", type=int, default=20,
                        help="max games to fetch per --user (default: 20)")
    parser.add_argument("--min-plies", type=int, default=10,
                        help="drop games shorter than this many half-moves (default: 10)")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR,
                        help="write corpus.pgn + manifest.json here (default: data/games/)")
    return parser


def main(argv: list[str] | None = None, fetch_fn: FetchFn = _lichess_fetch) -> int:
    args = build_parser().parse_args(argv)
    if not args.user and not args.input:
        print("Nothing to do: pass at least one --user or --input.", file=sys.stderr)
        return 1

    raw: list[str] = []
    for path in args.input:
        raw.extend(split_pgn(path.read_text(encoding="utf-8")))
    for user in args.user:
        print(f"Fetching up to {args.max} games for '{user}'...", file=sys.stderr)
        raw.extend(split_pgn(fetch_fn(user, args.max)))

    heldout = heldout_fingerprints()
    games = assemble(raw, heldout, min_plies=args.min_plies)
    if not games:
        print(f"No games survived assembly ({len(raw)} fetched).", file=sys.stderr)
        return 1

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
