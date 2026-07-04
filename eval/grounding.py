"""Deterministic grounding metric for coaching text.

"Grounding" = did the coach only talk about moves it was actually given? A small model
tends to confabulate plausible-looking chess when the facts are thin (the Phase-2
finding). We measure that without an LLM: extract every move the coaching text cites,
diff it against the moves present in the facts block the model received, and anything
left over is a hallucinated move.

Move detection is a heuristic SAN regex — it can't know chess legality, only shape — but
that's enough to catch a coach inventing "16...Nbd7" or a "queen sacrifice" that never
appeared in the facts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from coach import prompts

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


def _normalize(move: str) -> str:
    """Canonical form for comparison: unify castling zeros, drop check/mate marks."""
    return move.replace("0", "O").rstrip("+#")


def extract_moves(text: str) -> set[str]:
    """Return the set of normalized SAN moves cited anywhere in ``text``."""
    return {_normalize(m) for m in _SAN_RE.findall(text)}


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
