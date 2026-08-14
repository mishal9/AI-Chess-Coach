"""Deterministic claim checking: does the coaching say *true things* about the moves?

``eval.grounding`` answers "did the coach only talk about moves it was given?" — a
set-membership test over cited moves. It is blind to what is then *asserted* about them,
and that blind spot is where the judged factual score actually goes: across the 29-game
held-out set, two games scored grounding **1.00** and judged factual **2**, and
*r*(grounding, factual) is only +0.39. See
``docs/experiments/2026-08-11-grounding-metric-audit.md``.

This module checks the assertions. Two classes, both drawn from the failures that audit
found, and both deterministic — no engine, no model, no judge:

**Role inversion.** Every flagged mistake gives the coach two moves: the one the player
played and the one the engine preferred. The coach swaps them — *"when you played g3"*
when g3 is the engine's move, *"you chose a passive rook move (Rc8)"* when Rc8 is the
engine's and the player played Bc6. Both moves are in the facts, so grounding is content.

**Invented castling.** The coach reads a king move to the h- or g-file as castling —
*"29.Kh1 … you castled king-side"* — because king moves and castling co-occur constantly
in pretraining text. ``Kh1`` is in the facts, so grounding is content here too.

A move is only checked when the facts assign it a role, so a citation of something outside
the facts stays grounding's business and is not double-counted here. Assertions are matched
by *immediate adjacency* — the cue word next to the move, markdown allowed — rather than by
scanning a window: "the engine preferred Nh5 instead of Re8" must not read Re8 as
engine-preferred, and a window would. Coordination inherits the cue, so "you played Nf3 or
g3" attributes both.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from coach import prompts
from eval import grounding

# A flagged-mistake line from the facts block, e.g.
#   - 12...Re8?! (inaccuracy): the engine preferred Nh5; cost about 10% win probability...
_FACT_LINE_RE = re.compile(
    r"^-\s*\d+\.(?:\.\.)?\s*"
    r"(?P<played>[^\s?!]+)[?!]*\s*"
    r"\([^)]*\):\s*the engine preferred\s+(?P<preferred>[^\s;,.]+)",
    re.MULTILINE,
)

# Reuse the citation parser's tolerance for markdown sitting between words.
_SKIP = r"[\s*_`\"'()\[\]-]"
_COORD_RE = re.compile(rf"[^\s*_`\"'()\[\]-]+{_SKIP}+(?:and|or){_SKIP}+\Z")
_CUE_WORD_RE = re.compile(r"([A-Za-z]+)")

# How far back a cue may sit from the move it governs. Wide enough for "chose a passive
# rook move (Rc8)", short enough not to reach across a clause into unrelated prose.
_MAX_CUE_DISTANCE = 60

# A cue does not carry across a sentence boundary. Move numbers ("12...Re8") are safe:
# the split needs whitespace after the period.
_SENTENCE_BREAK_RE = re.compile(r"(?<=[.;:!?])\s+(?=[A-Z])|\n")

# Words that attribute the next move to the player. **Past tense only** — the present
# tense is generic advice, not a claim about this game: "when you play 3...exd4, you win a
# central pawn" describes a line, while "when you played 3...exd4" describes the game.
_PLAYED_CUES = frozenset("played chose chosen picked selected opted".split())
# ...and to the engine.
_PREFERRED_CUES = frozenset(
    """preferred prefer prefers preferring recommended recommend recommends suggested
    suggest suggests wanted wants liked likes""".split()
)

# A cue only asserts a role when its **agent is named right before it** — "you played",
# "the engine preferred". Without that, the same verbs are recommendations or negations
# rather than claims about what happened: "the engine wanted you *to play* Bxc3", "by
# *not playing* f5", "the chance *to play* b5". Requiring the agent rejects all three,
# and lets "wanted" (agent: engine) carry the sentence instead — which is the true role.
_PLAYED_AGENTS = frozenset("you player black white".split())
_PREFERRED_AGENTS = frozenset("engine stockfish computer".split())

# A cue governs only its own clause: in "you chose a capture when the quiet c4 was
# stronger", c4 belongs to "was stronger", not to "chose".
_CLAUSE_BREAK = frozenset(
    """when while because although though if since but whereas unless after before
    until whether that which who instead rather""".split()
)

# Only an *assertion that this player castled* counts. Merely mentioning castling is
# usually correct: "you played d4 instead of castling", "work on castling first" — the
# second of those is advice, and the first explicitly says the player did not castle.
_CASTLING_CLAIM_RE = re.compile(
    r"\b(?:you|your\s+king)\b(?:\s*(?:'ve|'d|have|had|were|was|already|just|then))*"
    r"\s+castl(?:ed|ing)\b",
    re.IGNORECASE,
)

# ...and not when the assertion is hypothetical or interrogative: "ask yourself whether
# you've castled", "if you had castled".
_HYPOTHETICAL_RE = re.compile(
    r"\b(?:whether|if|when|once|unless|until|before|after|should|would|could)\b"
    r"[^.;:!?]{0,30}\Z",
    re.IGNORECASE,
)
_CASTLING_MOVES = frozenset({"O-O", "O-O-O"})


@dataclass(frozen=True)
class ClaimViolation:
    """One assertion the facts contradict."""

    kind: str            # "role_inversion" | "invented_castling"
    move: str            # the move the assertion is about ("" when none is identified)
    claimed: str         # what the coaching says it is
    actual: str          # what the facts say it is
    excerpt: str         # surrounding text, for the report

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "move": self.move,
            "claimed": self.claimed,
            "actual": self.actual,
            "excerpt": self.excerpt,
        }


@dataclass
class ClaimResult:
    """Outcome of checking a coaching text's assertions against its facts."""

    checked: int = 0                                    # assertions actually testable
    violations: list[ClaimViolation] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True iff no assertion contradicted the facts."""
        return not self.violations

    @property
    def score(self) -> float:
        """Fraction of testable assertions that were correct (1.0 = clean).

        Coaching that makes no testable assertion scores 1.0, exactly as grounding treats
        coaching that cites no moves: this measures whether claims are *right*, not
        whether enough of them were made.
        """
        if not self.checked:
            return 1.0
        return 1.0 - len(self.violations) / self.checked

    def to_dict(self) -> dict:
        return {
            "score": round(self.score, 3),
            "ok": self.ok,
            "checked": self.checked,
            "violations": [v.to_dict() for v in self.violations],
        }


def parse_roles(facts_text: str) -> tuple[set[str], set[str]]:
    """Return ``(played, preferred)`` — the moves the facts attribute to each side of the
    comparison. A move appearing in both roles is dropped from both: it cannot arbitrate.
    """
    played, preferred = set(), set()
    for match in _FACT_LINE_RE.finditer(facts_text):
        played.add(grounding._normalize(match.group("played")))
        preferred.add(grounding._normalize(match.group("preferred")))
    ambiguous = played & preferred
    return played - ambiguous, preferred - ambiguous


def _cue_before(text: str, start: int) -> str:
    """The role cue governing the move at ``start``, or ``""`` if none governs it.

    The cue need not be adjacent — "you chose a passive rook move (Rc8)" puts a whole noun
    phrase in between — but the search stops at **another move citation**, because that
    move takes the cue for itself: in "the engine preferred Nh5 instead of Re8", Nh5 owns
    the "preferred" and Re8 is left ungoverned rather than mis-attributed. It also stops at
    a clause boundary, and the cue must carry a named agent. Coordination is stripped
    first, so "you played Nf3 or g3" still governs both.
    """
    before = text[:start]
    coord = _COORD_RE.search(before)
    if coord:
        before = before[: coord.start()]

    window = before[-_MAX_CUE_DISTANCE:]
    window = _SENTENCE_BREAK_RE.split(window)[-1]
    words = list(_CUE_WORD_RE.finditer(window))

    for i, cue_match in reversed(list(enumerate(words))):
        word = cue_match.group(1).lower()
        if word in _CLAUSE_BREAK:
            return ""
        if word not in _PLAYED_CUES and word not in _PREFERRED_CUES:
            continue
        agent = words[i - 1].group(1).lower() if i else ""
        agents = _PLAYED_CUES if word in _PLAYED_CUES else _PREFERRED_CUES
        expected = _PLAYED_AGENTS if agents is _PLAYED_CUES else _PREFERRED_AGENTS
        if agent not in expected:
            continue
        if any(grounding.iter_move_citations(window[cue_match.end():])):
            return ""
        return word
    return ""


def _excerpt(text: str, start: int, end: int, pad: int = 45) -> str:
    return " ".join(text[max(0, start - pad):end + pad].split())


def check_roles(coaching_text: str, facts_text: str) -> ClaimResult:
    """Check every role assertion in ``coaching_text`` against the roles in ``facts_text``."""
    played, preferred = parse_roles(facts_text)
    result = ClaimResult()
    if not played and not preferred:
        return result

    for move, match in grounding.iter_move_citations(coaching_text):
        cue = _cue_before(coaching_text, match.start())
        if cue in _PLAYED_CUES:
            claimed = "played"
        elif cue in _PREFERRED_CUES:
            claimed = "engine-preferred"
        else:
            continue
        actual = "played" if move in played else (
            "engine-preferred" if move in preferred else ""
        )
        if not actual:
            continue  # not role-bearing in the facts — grounding's business, not ours
        result.checked += 1
        if actual != claimed:
            result.violations.append(
                ClaimViolation(
                    kind="role_inversion",
                    move=move,
                    claimed=claimed,
                    actual=actual,
                    excerpt=_excerpt(coaching_text, match.start(), match.end()),
                )
            )
    return result


def check_castling(coaching_text: str, report: dict, coached_side: str) -> ClaimResult:
    """Flag castling attributed to a player who never castled.

    Deliberately conservative: it fires only when the coached side played no castling move
    *anywhere* in the game, so a coach that merely mislocates a real castle is not
    penalised. That is enough to catch the observed failure, where a king move to the h- or
    g-file is narrated as castling.
    """
    result = ClaimResult()
    matches = [
        m
        for m in _CASTLING_CLAIM_RE.finditer(coaching_text)
        if not _HYPOTHETICAL_RE.search(coaching_text[: m.start()])
    ]
    if not matches:
        return result

    result.checked = 1
    castled = any(
        move["side"] == coached_side and grounding._normalize(move["san"]) in _CASTLING_MOVES
        for move in report.get("moves", [])
    )
    if castled:
        return result
    result.violations.append(
        ClaimViolation(
            kind="invented_castling",
            move="",
            claimed="the player castled",
            actual="no castling move by this side in the game",
            excerpt=_excerpt(coaching_text, matches[0].start(), matches[0].end()),
        )
    )
    return result


def _merge(*results: ClaimResult) -> ClaimResult:
    merged = ClaimResult()
    for r in results:
        merged.checked += r.checked
        merged.violations.extend(r.violations)
    return merged


def check_claims(coaching_text: str, facts_text: str) -> ClaimResult:
    """Role checking from text alone — the form the distillation gate can use, where the
    facts block is at hand but the analyzed report may not be."""
    return check_roles(coaching_text, facts_text)


def check_claims_from_report(
    coaching_text: str,
    report: dict,
    coached_side: str | None = None,
    max_mistakes: int = 6,
) -> ClaimResult:
    """Full check: role inversion plus invented castling.

    Mirrors :func:`eval.grounding.grounding_from_report` — the facts block is rebuilt
    exactly as the coach received it, so the roles checked are the roles it was given.
    """
    if coached_side is None:
        coached_side = prompts.choose_coached_side(report)
    facts = prompts.format_report_facts(report, coached_side, max_mistakes)
    return _merge(
        check_roles(coaching_text, facts),
        check_castling(coaching_text, report, coached_side),
    )
