"""Saved Stockfish analyses, so a game is analyzed once per depth instead of once per script.

At the research depth (18) a game takes about a second per move, and every evaluation
script (``eval.run``, ``eval.recheck``, ``eval.rejudge``, ``eval.human_rating``) used to
re-run Stockfish over the whole held-out set. Stockfish is deterministic at a fixed depth
with a fresh process per game, which is how :func:`engine.analyzer.analyze_game` runs it,
so a saved report is the same report a new run would produce.

A saved report is only reused when everything that shapes it matches:

* the game itself (every header and the mainline moves),
* the depth,
* the Stockfish build (its UCI ``id name``, e.g. ``Stockfish 17.1``),
* the analyzer code (a hash of ``engine/analyzer.py`` and ``engine/scoring.py``), so a
  change to move classification or PV handling invalidates old entries by itself.

Entries live under ``data/analysis/<depth>/`` as one JSON file per game, written atomically
so parallel runs cannot leave a half-written file. Set ``ANALYSIS_CACHE=off`` to bypass
the cache entirely.
"""

from __future__ import annotations

import functools
import hashlib
import json
import os
import tempfile
from pathlib import Path

import chess.pgn

ENGINE_DIR = Path(__file__).resolve().parent
DEFAULT_CACHE_DIR = ENGINE_DIR.parent / "data" / "analysis"

# The code whose output is cached. Editing either file changes every key.
_CODE_FILES = (ENGINE_DIR / "analyzer.py", ENGINE_DIR / "scoring.py")


def cache_enabled() -> bool:
    return os.environ.get("ANALYSIS_CACHE", "on").lower() not in {"off", "0", "false", "no"}


@functools.lru_cache(maxsize=1)
def code_fingerprint() -> str:
    digest = hashlib.sha256()
    for path in _CODE_FILES:
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


@functools.lru_cache(maxsize=1)
def stockfish_id() -> str:
    """The Stockfish build's UCI name. Starting the engine costs a few milliseconds."""
    import chess.engine

    from engine.analyzer import find_stockfish

    engine = chess.engine.SimpleEngine.popen_uci(find_stockfish())
    try:
        return engine.id.get("name", "unknown")
    finally:
        engine.quit()


def engine_label() -> str | None:
    """The Stockfish build for a report's provenance, or ``None`` when none is installed.

    Reports record it because the same depth on a different Stockfish build can give
    different facts; reports before 2026-09-26 do not say which build they used.
    """
    try:
        return stockfish_id()
    except FileNotFoundError:
        return None


def cache_key(game: chess.pgn.Game, depth: int, engine_id: str, code: str) -> str:
    identity = {
        "headers": dict(sorted(game.headers.items())),
        "moves": [move.uci() for move in game.mainline_moves()],
        "depth": depth,
        "engine": engine_id,
        "code": code,
    }
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()


def _write_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def analyze_cached(
    game: chess.pgn.Game,
    depth: int,
    cache_dir: Path | None = None,
    analyze=None,
    engine_id: str | None = None,
) -> dict:
    """Return ``analyze_game(game, depth).to_dict()``, from the cache when it is there.

    ``analyze`` and ``engine_id`` are injectable so the cache is testable without Stockfish.
    """
    if analyze is None:
        from engine.analyzer import analyze_game

        def analyze(g, d):
            return analyze_game(g, depth=d).to_dict()

    if not cache_enabled():
        return analyze(game, depth)

    key = cache_key(game, depth, engine_id or stockfish_id(), code_fingerprint())
    path = (cache_dir or DEFAULT_CACHE_DIR) / str(depth) / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    report = analyze(game, depth)
    _write_atomic(path, report)
    return report
