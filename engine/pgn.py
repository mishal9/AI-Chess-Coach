"""Reading PGN text: splitting it into games, and giving each game a stable identity.

One home for the PGN handling every layer needs — the app ingesting a player's chess.com
games, the coach CLI, and the research code building a training corpus. It lived in
``training.corpus`` until the app started importing it from there, which made the product
depend on the research package for something as basic as "split this file into games".
"""

from __future__ import annotations

import hashlib
import io
import re
from itertools import islice
from pathlib import Path
from typing import Iterator

import chess.pgn

# A game record in a PGN begins with its [Event ...] tag.
_EVENT_RE = re.compile(r"(?=^\[Event )", re.MULTILINE)
_GAMEID_RE = re.compile(r'^\[GameId\s+"([^"]+)"\]', re.MULTILINE)
_SITE_RE = re.compile(r'^\[Site\s+"([^"]+)"\]', re.MULTILINE)
_TAG_LINE_RE = re.compile(r"^\[.*\]\s*$", re.MULTILINE)
_COMMENT_RE = re.compile(r"\{[^}]*\}")  # inline PGN comments, e.g. Lichess { [%eval ...] }


def split_pgn(text: str) -> list[str]:
    """Split a multi-game PGN blob into individual game strings (each with its tags)."""
    return [g.strip() for g in _EVENT_RE.split(text) if g.strip()]


def read_game(pgn: str) -> chess.pgn.Game | None:
    """Parse one game's PGN text, or ``None`` if there is no game in it."""
    return chess.pgn.read_game(io.StringIO(pgn))


def iter_games(pgn_path: Path) -> Iterator[chess.pgn.Game]:
    """Yield each game in a PGN file."""
    with Path(pgn_path).open(encoding="utf-8") as fh:
        while (game := chess.pgn.read_game(fh)) is not None:
            yield game


def load_game(pgn_path: Path, game_index: int) -> chess.pgn.Game | None:
    """Return the game at ``game_index`` (0-based) in ``pgn_path``, or ``None``."""
    return next(islice(iter_games(pgn_path), game_index, None), None)


def normalized_movetext(pgn: str) -> str:
    """Movetext with tags and comments stripped and whitespace collapsed.

    Gives two exports of the *same* game one identity even if one carries ``%eval``
    comments or a different tag set than the other.
    """
    body = _TAG_LINE_RE.sub("", pgn)
    body = _COMMENT_RE.sub(" ", body)
    return " ".join(body.split())


def movetext_hash(pgn: str) -> str:
    """Source-independent identity for a game: a digest of its moves alone.

    Unlike :func:`game_key` this never prefers a site id, so the *same* game exported
    twice with different tags hashes the same both times. That is what makes it safe as
    a deduplication key for anything that counts games.
    """
    return hashlib.sha256(normalized_movetext(pgn).encode("utf-8")).hexdigest()[:16]


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
    return f"moves:{movetext_hash(pgn)}"
