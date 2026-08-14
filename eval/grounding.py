"""Deterministic grounding metric for coaching text.

"Grounding" = did the coach only talk about moves it was actually given? A small model
tends to confabulate plausible-looking chess when the facts are thin (the Phase-2
finding). We measure that without an LLM: extract every move the coaching text cites,
diff it against the moves present in the facts block the model received, and anything
left over is a hallucinated move.

Move detection is a heuristic SAN regex — it can't know chess legality, only shape — but
that's enough to catch a coach inventing "16...Nbd7" or a "queen sacrifice" that never
appeared in the facts.

**Bare squares are disambiguated by context.** Pawn moves are written as the bare
destination square ("e4"), so the matcher must accept one as a move candidate — but the
same two characters are also how coaching prose names a *location* ("your rook on b7",
"control of the e5 square"). Counting those as claimed moves was the metric's dominant
error: 84-94% of every hallucination it ever flagged, and 64 of the 64 rows its strict
gate dropped from the v2 distillation set, were bare squares used as locations. See
``docs/experiments/2026-08-11-grounding-metric-audit.md``.

A bare square is therefore read as a move *unless* the adjacent words make it a location —
"on b7", "from b7 to b8", "the e5 square", "the b7 rook". Notation always wins over that
test, so "came on 12...e5?!" survives the "on". The same rule applies to the facts block
and the coaching text, so both sides score only tokens actually used as citations.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field

from coach import prompts

# Semantics version for this metric. Bump whenever a change makes a new score
# incomparable with an old one, and record what changed — ``eval.compare`` refuses to
# difference reports whose versions disagree.
#   1  original parser: every SAN-shaped token counted, so bare squares in prose ("your
#      rook on b7") scored as invented pawn moves. 84-94% of all flagged hallucinations.
#   2  (#41) bare squares are read as moves only when context does not make them a
#      location. See docs/experiments/2026-08-11-grounding-metric-audit.md.
METRIC_VERSION = 2

# Heuristic Standard Algebraic Notation matcher. Matches castling and normal moves
# (optional piece + optional disambiguation + optional capture + destination square +
# optional promotion + optional check/mate). Not preceded by a word char so it won't
# fire inside words like "Black" or "back". Backtracking lets an optional disambiguation
# file yield to the mandatory destination square (so "Be7" parses as B -> e7).
_SAN_RE = re.compile(
    r"(?<![\w])"
    r"(?:[O0]-[O0](?:-[O0])?"                       # O-O / O-O-O (0 tolerated)
    r"|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?)"  # normal move
    r"[+#]?"
)

# A candidate that is *only* a destination square — the shape a pawn move and a square
# reference share, and the only shape that needs context to tell those apart.
_BARE_SQUARE_RE = re.compile(r"[a-h][1-8]\Z")

# Coaching text is markdown, so emphasis and quoting sit between a cue word and the move
# it introduces ("the engine preferred **c5**"). Treat that punctuation as transparent
# when looking for the adjacent word in either direction.
_SKIP = r"[\s*_`\"'()\[\]-]"

# "12.e4" / "12...e5" / "12. e5" immediately before the square -> a move citation.
_MOVE_NUMBER_RE = re.compile(r"\d+\s*\.(?:\.\.)?\s*\Z")

# An annotation suffix ("e5?!", "**a2??**") -> notation, whatever the surrounding markup.
_ANNOTATION_RE = re.compile(rf"{_SKIP}*[!?]")

# The word immediately before the square, and the one immediately after it.
_PREV_WORD_RE = re.compile(rf"([A-Za-z]+){_SKIP}+\Z")
_NEXT_WORD_RE = re.compile(rf"{_SKIP}*([A-Za-z]+)")

# A coordinated square inherits the preposition governing the first: in "knights belong on
# f3 and f6", "f6" is as much a location as "f3". Strips one "<square> and/or" step so the
# governing word can be re-tested.
_COORD_RE = re.compile(rf"[a-h][1-8]{_SKIP}+(?:and|or){_SKIP}+\Z", re.I)

# Prepositions that mark the square as a *place on the board*, not a move.
_LOCATION_PREPS = frozenset(
    # "behind" is deliberately absent: "the idea behind e5" is about the move, not a square.
    """on at from to onto into along across around near toward towards over under
    beside via through""".split()
)

# A noun right after the square means the square is qualifying it ("the e5 square",
# "the b7 rook") rather than standing alone as a move.
_LOCATION_NOUNS = frozenset(
    """square squares pawn pawns file files rank ranks outpost outposts diagonal
    diagonals knight knights bishop bishops rook rooks queen queens king kings piece
    pieces""".split()
)


def _is_move_citation(text: str, match: re.Match[str]) -> bool:
    """Is this SAN candidate being used as a *move*, rather than as a square reference?

    Only bare destination squares are ambiguous — anything carrying a piece letter,
    capture, castling or promotion is unambiguously a move.

    A bare square is assumed to be a move unless the surrounding words say otherwise.
    Coaching prose cites moves in too many shapes to enumerate ("g4 preserved it", "d3 is
    passive", "why did g6 fall short?"), so an allowlist of cue verbs loses real citations;
    locational phrasing, by contrast, is a short and stable list.
    """
    token = match.group()
    if not _BARE_SQUARE_RE.match(token):
        return True

    before, after = text[: match.start()], text[match.end():]

    # Annotated ("e5?!", "**a2??**") or numbered ("12...e5") -> notation, beyond doubt.
    # Checked first so they survive a locational preposition: "came on 12...e5?!".
    if token[-1] in "+#" or _ANNOTATION_RE.match(after):
        return True
    if _MOVE_NUMBER_RE.search(before):
        return True

    # "the e5 square", "the b7 rook" — the square is qualifying the noun after it.
    next_word = _NEXT_WORD_RE.match(after)
    if next_word and next_word.group(1).lower() in _LOCATION_NOUNS:
        return False

    # "your rook on b7", "from b7 to b8" — a place, and any move involved is cited
    # separately in its own notation. Known cost: this also drops the genuine pawn move
    # in "pushed the pawn to e5", which is indistinguishable without piece tracking.
    coord = _COORD_RE.search(before)
    if coord:
        before = before[: coord.start()]
    prev_word = _PREV_WORD_RE.search(before)
    return not (prev_word and prev_word.group(1).lower() in _LOCATION_PREPS)


def _normalize(move: str) -> str:
    """Canonical form for comparison: unify castling zeros, drop check/mate marks."""
    return move.replace("0", "O").rstrip("+#")


def iter_move_citations(text: str) -> Iterator[tuple[str, re.Match[str]]]:
    """Yield ``(normalized_move, match)`` for every token used as a move citation.

    The match is included so callers can inspect the surrounding words — ``eval.claims``
    uses it to find which *role* the text assigns each move.
    """
    for match in _SAN_RE.finditer(text):
        if _is_move_citation(text, match):
            yield _normalize(match.group()), match


def extract_moves(text: str) -> set[str]:
    """Return the set of normalized SAN moves cited anywhere in ``text``.

    Bare squares are included only where context marks them as moves — see the module
    docstring.
    """
    return {move for move, _ in iter_move_citations(text)}


@dataclass
class GroundingResult:
    """Outcome of checking a coaching text against the facts it was given."""

    cited: set[str] = field(default_factory=set)        # moves the coaching mentions
    allowed: set[str] = field(default_factory=set)      # moves present in the facts
    hallucinated: set[str] = field(default_factory=set)  # cited but not in the facts

    @property
    def grounded(self) -> bool:
        """True iff the coaching invented no moves."""
        return not self.hallucinated

    @property
    def score(self) -> float:
        """Fraction of cited moves that were legitimately in the facts (1.0 = clean).

        A coach that cites no moves at all scores 1.0 — it can't have hallucinated one.
        Coverage (did it cite the *right* moves?) is a separate concern; see
        :func:`identifies_worst_move`.
        """
        if not self.cited:
            return 1.0
        return 1.0 - len(self.hallucinated) / len(self.cited)


def score_grounding(coaching_text: str, facts_text: str) -> GroundingResult:
    """Score a coaching text against the exact facts block that produced it."""
    cited = extract_moves(coaching_text)
    allowed = extract_moves(facts_text)
    return GroundingResult(
        cited=cited, allowed=allowed, hallucinated=cited - allowed
    )


def grounding_from_report(
    coaching_text: str,
    report: dict,
    coached_side: str | None = None,
    max_mistakes: int = 6,
) -> GroundingResult:
    """Score grounding by rebuilding the facts block the coach was given from ``report``.

    Mirrors :func:`coach.prompts.build_messages`: the allowed-move set is exactly what the
    model saw, so grounding means "stayed within what it was told."
    """
    if coached_side is None:
        coached_side = prompts.choose_coached_side(report)
    facts = prompts.format_report_facts(report, coached_side, max_mistakes)
    return score_grounding(coaching_text, facts)


def identifies_worst_move(coaching_text: str, report: dict) -> bool:
    """Deterministic proxy for 'identifies the key mistake': did the coach cite the
    engine's single worst move? Returns False when the report flags no worst move."""
    worst = report.get("summary", {}).get("worst_move")
    if not worst or not worst.get("played"):
        return False
    return _normalize(worst["played"]) in extract_moves(coaching_text)
