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

**Invented placement.** The coach asserts where a piece stood — *"you moved your rook from
b7 to b8"*, when that rook came from a8 and b7 held a pawn. The facts block carries no
piece placement whatsoever, so these claims are pure invention unless the game bears them
out; replaying the analyzed positions settles it for free. This is the failure the
bare-square parser used to catch *by accident*, flagging "b7" as a phantom pawn move: once
that false positive was fixed in #41, nothing was left watching for it.

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

import chess

from coach import prompts
from eval import grounding

# Semantics version for this metric — see ``eval.grounding.METRIC_VERSION`` for the
# contract. Bump whenever a check is added, removed, or retuned, since any of those change
# what a score means.
#   1  (#43, #45) role inversion, invented castling, invented placement.
#   2  (2026-09-26) fewer false accusations, found by hand-auditing DeepSeek-V4 Pro text:
#      a role claim naming the opponent ("after White played 7.Nxe4") is not checked
#      against the coached side's roles; placement claims skip hypotheticals ("the queen
#      on e2 would have been..."), targeting ("pointing the knight at f7"), conditional
#      advice ("when your opponent has a pawn on d5") and -ing forms of advice verbs
#      ("getting the bishop to e7").
METRIC_VERSION = 2

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

# --- board-state claims ----------------------------------------------------------
# "your knight on f5", "the pawn on c2", "your rook from b7" — the coach asserting where
# a piece stood. The facts block carries no piece placement at all, so every one of these
# is invented unless the game happens to bear it out. Replaying the analyzed positions
# settles it for free.
_PIECES = {
    "pawn": "p", "knight": "n", "bishop": "b",
    "rook": "r", "queen": "q", "king": "k",
}
_PIECE_CLAIM_RE = re.compile(
    r"\b(?P<owner>your|the|a|an|his|her|their)\s+"
    r"(?:\w+\s+){0,2}?"                       # optional adjectives: "the passive rook"
    r"(?P<piece>pawn|knight|bishop|rook|queen|king)s?\s+"
    r"(?P<prep>on|at|from|to)\s+"
    r"(?P<square>[a-h][1-8])\b",
    re.IGNORECASE,
)

# Recommendations, not observations: "knights belong on f3", "put your rook on d1",
# "getting the bishop to e7". Same trap as the role cues — a suggestion about where a
# piece *should* go says nothing false about where it *was*. "keeping" is deliberately
# absent: "the engine preferred keeping the bishop on f4" asserts the bishop was on f4.
_ADVICE_RE = re.compile(
    r"\b(?:belong|belongs|put|putting|place|placing|should|could|would|want|wants|wanted|"
    r"try|trying|aim|aiming|bring|bringing|develop|developing|reroute|rerouting|swing|"
    r"swinging|maneuver|maneuvering|manoeuvre|manoeuvring|prefer|prefers|better|ideally|"
    r"instead|consider|considering|imagine|keep|get|getting|route|routing)"
    r"\b[^.;:!?]{0,40}\Z",
    re.IGNORECASE,
)

# A piece pointed *at* a square is a target, not a placement: "pointing the knight at f7".
_TARGETING_RE = re.compile(
    r"\b(?:point|points|pointing|pointed|aim|aims|aimed|eye|eyes|eyeing|target|targets|"
    r"targeting|targeted)\b[^.;:!?]{0,20}\Z",
    re.IGNORECASE,
)

# A modal right after the claim makes it hypothetical: "the queen on e2 would have been
# more harmonious" describes the engine's alternative, not the game.
_HYPOTHETICAL_AFTER_RE = re.compile(
    r"\A[^.;:!?]{0,15}?\b(?:would|could|might|should)\b", re.IGNORECASE
)


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


_COACHED_SIDE_RE = re.compile(r"You are coaching the (WHITE|BLACK) player")


def _cue_before(text: str, start: int) -> tuple[str, str]:
    """The role cue governing the move at ``start``, or ``""`` if none governs it.

    The cue need not be adjacent — "you chose a passive rook move (Rc8)" puts a whole noun
    phrase in between — but the search stops at **another move citation**, because that
    move takes the cue for itself: in "the engine preferred Nh5 instead of Re8", Nh5 owns
    the "preferred" and Re8 is left ungoverned rather than mis-attributed. It also stops at
    a clause boundary, and the cue must carry a named agent. Coordination is stripped
    first, so "you played Nf3 or g3" still governs both.

    Returns ``(cue, agent)``, or ``("", "")`` when nothing governs the move.
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
            return "", ""
        if word not in _PLAYED_CUES and word not in _PREFERRED_CUES:
            continue
        agent = words[i - 1].group(1).lower() if i else ""
        agents = _PLAYED_CUES if word in _PLAYED_CUES else _PREFERRED_CUES
        expected = _PLAYED_AGENTS if agents is _PLAYED_CUES else _PREFERRED_AGENTS
        if agent not in expected:
            continue
        if any(grounding.iter_move_citations(window[cue_match.end():])):
            return "", ""
        return word, agent
    return "", ""


def _excerpt(text: str, start: int, end: int, pad: int = 45) -> str:
    return " ".join(text[max(0, start - pad):end + pad].split())


def check_roles(coaching_text: str, facts_text: str) -> ClaimResult:
    """Check every role assertion in ``coaching_text`` against the roles in ``facts_text``."""
    played, preferred = parse_roles(facts_text)
    result = ClaimResult()
    if not played and not preferred:
        return result
    side = _COACHED_SIDE_RE.search(facts_text)
    opponent = ({"WHITE": "black", "BLACK": "white"}[side.group(1)] if side else "")

    for move, match in grounding.iter_move_citations(coaching_text):
        cue, agent = _cue_before(coaching_text, match.start())
        if opponent and agent == opponent:
            # The facts only assign roles to the coached side's moves. "After White played
            # 7.Nxe4" describes the opponent's move, which can share its SAN with the
            # coached side's engine-preferred move.
            continue
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


def occupied_squares(report: dict) -> set[tuple[bool, str, str]]:
    """Every ``(is_white, piece_letter, square)`` the game ever contained.

    Built from each move's ``fen_before``, plus the position after the final move, which
    no ``fen_before`` represents. A piece/square pair absent from this set was never on
    the board — the only thing strong enough to call a placement claim invented.
    """
    import chess

    seen: set[tuple[bool, str, str]] = set()

    def absorb(board: "chess.Board") -> None:
        for square, piece in board.piece_map().items():
            seen.add((piece.color, piece.symbol().lower(), chess.square_name(square)))

    moves = report.get("moves", [])
    board = None
    for move in moves:
        fen = move.get("fen_before")
        if not fen:
            continue
        board = chess.Board(fen)
        absorb(board)
    if board is not None and moves:
        try:  # the final position: push the last move onto the last recorded FEN
            board.push_san(moves[-1]["san"])
            absorb(board)
        except (ValueError, KeyError):
            pass  # a report whose last SAN will not parse simply contributes nothing
    return seen


def check_board_state(
    coaching_text: str, report: dict, coached_side: str
) -> ClaimResult:
    """Flag piece-placement claims the game never bore out.

    Conservative on three axes, because the facts block gives the coach nothing to go on
    here and a false accusation is worse than a miss:

    * a claim is only wrong if that piece and colour were **never** on that square at any
      point in the game, not merely at the moment under discussion;
    * "the rook on b7" (no possessive) is checked against **both** colours, and passes if
      either could have stood there;
    * advice, hypotheticals and targets are skipped — "knights belong on f3", "when your
      opponent has a pawn on d5", "the queen on e2 would have been better", "pointing the
      knight at f7" say nothing about where a piece actually was.
    """
    result = ClaimResult()
    occupancy = occupied_squares(report)
    if not occupancy:
        return result
    coached_white = coached_side == "white"

    for match in _PIECE_CLAIM_RE.finditer(coaching_text):
        before = coaching_text[: match.start()]
        if (
            _ADVICE_RE.search(before)
            or _HYPOTHETICAL_RE.search(before)
            or (match.group("prep").lower() == "at" and _TARGETING_RE.search(before))
            or _HYPOTHETICAL_AFTER_RE.search(coaching_text[match.end():])
        ):
            continue
        piece = _PIECES[match.group("piece").lower()]
        square = match.group("square").lower()
        owner = match.group("owner").lower()
        colors = [coached_white] if owner == "your" else [True, False]

        result.checked += 1
        if any((color, piece, square) in occupancy for color in colors):
            continue
        whose = "your" if owner == "your" else "a"
        result.violations.append(
            ClaimViolation(
                kind="invented_placement",
                move="",
                claimed=f"{whose} {match.group('piece').lower()} on {square}",
                actual=f"no {match.group('piece').lower()} ever stood on {square}",
                excerpt=_excerpt(coaching_text, match.start(), match.end()),
            )
        )
    return result


# The position facts' evaluation line, in its words form ("you are worse by about 3.1
# pawns") or the earlier signed form ("(in pawns; + favours you): ... -3.1, ... -8.9").
_EVAL_LINE_RE = re.compile(
    r"^- Engine evaluation[^:\n]*: with the preferred move,? (?P<before>[^;,\n]+)[;,] "
    r"after your move,? (?P<after>[^.\n]+(?:\.\d+[^.\n]*)?)\.$",
    re.MULTILINE,
)
_EVAL_WORDS_RE = re.compile(r"you are (better|worse) by about (\d+(?:\.\d+)?) pawns")
EVAL_CLEAR_PAWNS = 1.0  # a side is clearly better from a full pawn

_MODIFIERS = r"(?:already|still|clearly|much|slightly|comfortably|objectively|well)\s+"
# "you were already better", "left you clearly better", "your position remains better",
# "a clearly winning position". Material ("ahead", "up a pawn") is left out: the facts
# give material separately, and a side can be up material and still worse.
_BETTER_CLAIM_RE = re.compile(
    rf"\b(?:you(?:'re| are| were| remain| remained| stay| stayed| stand| stood)|"
    rf"(?:left|leaves|leave|keeps|keep|kept) you|"
    rf"your position (?:is|was|remains|remained|stays|stayed))\s+(?:{_MODIFIERS})*"
    rf"(?:better|winning|on top)\b(?!\s+(?:off|to|than|or)\b)(?!\s+(?:a|an|the|back|"
    rf"material|your|their|two|three)\b)"
    rf"|\b(?:clearly|slightly|much|comfortably)\s+(?:better|winning)\s+position\b",
    re.IGNORECASE,
)
_WORSE_CLAIM_RE = re.compile(
    rf"\b(?:you(?:'re| are| were| stand| stood)|your position (?:is|was))\s+"
    rf"(?:{_MODIFIERS})*(?:worse|losing|lost)\b(?!\s+(?:off|than)\b)(?!\s+(?:a|an|the|"
    rf"material|your|their|two|three)\b)",
    re.IGNORECASE,
)


_CONDITIONAL_RE = re.compile(r"\b(?:when|whenever|if|once|while)\s+\Z", re.IGNORECASE)


def _eval_pawns(phrase: str) -> float | None:
    """The coached side's evaluation in pawns from one phrase of the evaluation line."""
    phrase = phrase.strip()
    if "forced mate for you" in phrase or phrase == "you have a forced mate":
        return 100.0
    if "forced mate for the opponent" in phrase or phrase == "the opponent has a forced mate":
        return -100.0
    if phrase == "the position is about level":
        return 0.0
    m = _EVAL_WORDS_RE.fullmatch(phrase)
    if m:
        return float(m.group(2)) * (1 if m.group(1) == "better" else -1)
    try:
        return float(phrase)
    except ValueError:
        return None


def check_eval_sign(coaching_text: str, facts_text: str) -> ClaimResult:
    """Flag a student called better or winning when the evaluation says they were worse.

    The 8 Oct 2026 spot-check found this in 5 of 10 confirmed errors: "you were already
    better" at -3.1. Calling the student better is false when even the engine's preferred
    move left them a pawn or more worse (a mistake only makes it worse, and a hypothetical
    "would have left you better" describes exactly that preferred move); calling them
    worse or losing is false when they stayed a pawn or more better after the move played.
    Facts without an evaluation line (whole-game facts) check nothing.
    """
    result = ClaimResult()
    m = _EVAL_LINE_RE.search(facts_text)
    if not m:
        return result
    before, after = _eval_pawns(m.group("before")), _eval_pawns(m.group("after"))
    if before is None or after is None:
        return result
    checks = [
        (_BETTER_CLAIM_RE, before <= -EVAL_CLEAR_PAWNS, "better", m.group("before")),
        (_WORSE_CLAIM_RE, after >= EVAL_CLEAR_PAWNS, "worse", m.group("after")),
    ]
    for pattern, false_here, claimed, actual in checks:
        for claim in pattern.finditer(coaching_text):
            if _CONDITIONAL_RE.search(coaching_text[: claim.start()]):
                continue  # advice: "when you're winning, keep it simple"
            result.checked += 1
            if false_here:
                result.violations.append(
                    ClaimViolation(
                        kind="eval_sign",
                        move="",
                        claimed=f"student {claimed}",
                        actual=f"evaluation: {actual.strip()}",
                        excerpt=_excerpt(coaching_text, claim.start(), claim.end()),
                    )
                )
    return result


# --- defence claims ---------------------------------------------------------------
# "the knight on c6 no longer protects the queen", "supporting your knight on g6". The 8 Oct clear-cut spot-check found 4 of its 6 confirmed
# errors misstating what defends what. A position row's facts list every piece, so the
# boards before and after the move (and after the preferred move) settle these claims.
_PIECE_NAMES = r"pawn|knight|bishop|rook|queen|king"
_MENTION_RE = re.compile(
    rf"\b(?:(?P<owner>your|the|their|black's|white's|opponent's|an?)\s+"
    rf"(?:(?!(?:{_PIECE_NAMES})\b)[a-z]+\s+){{0,2}}?)?"
    rf"(?:(?P<sq1>[a-h][1-8])[- ])?(?P<piece>{_PIECE_NAMES})\b"
    # not "the rook's capture", "your pawns", "that bishop sacrifice"
    rf"(?!'s|s\b|\s+(?:sacrifice|capture|move|trade|exchange|pair|check|ending)s?\b)"
    rf"(?:\s+(?:on|at|from)\s+(?P<sq2>[a-h][1-8]))?\b",
    re.IGNORECASE,
)
# A move names the piece on its destination square: "Qd5 … defends" is the queen on d5,
# which stands there on the board after that move (when the facts describe one).
_SAN_MENTION_RE = re.compile(
    r"(?<![\w.])(?:\d+\.+\s*)?(?P<piece>[KQRBN])[a-h]?[1-8]?x?(?P<sq>[a-h][1-8])[+#]?(?![\w])"
)
_SAN_PIECES = {"K": "king", "Q": "queen", "R": "rook", "B": "bishop", "N": "knight"}
# "it defends", "which still protected": the subject is the nearest piece or move before.
_PRONOUN_SUBJECT_RE = re.compile(
    r"\b(?:it|which)\s+(?:(?:also|still|already|now|then|only|directly|was|is|had|has|"
    r"been|no\s+longer)\s+){0,2}(?=(?:defend|protect|guard|support)(?:s|ed|ing)?\b)",
    re.IGNORECASE,
)
# "defended the b7 pawn indirectly": an x-ray, which direct coverage cannot settle.
_INDIRECT_RE = re.compile(r"\A[^.;:!?]{0,40}\b(?:indirectly|x-ray|through)\b", re.IGNORECASE)


@dataclass(frozen=True)
class _Mention:
    """One piece the text names: "your knight on g6", a move ("Qd5"), or a pronoun
    standing for the nearest of those before it."""
    start: int
    end: int
    text: str
    owner: str
    piece: str
    square: str | None


def _mentions(sentence: str) -> list[_Mention]:
    found = [_Mention(m.start(), m.end(), m.group(0), (m.group("owner") or "").lower(),
                      m.group("piece").lower(), m.group("sq1") or m.group("sq2"))
             for m in _MENTION_RE.finditer(sentence)]
    found += [_Mention(m.start(), m.end(), m.group(0), "", _SAN_PIECES[m.group("piece")],
                       m.group("sq"))
              for m in _SAN_MENTION_RE.finditer(sentence)]
    if re.search(r"\b(?:enemy|opponent's|opposing)\b", sentence, re.IGNORECASE):
        found = [m if not re.search(r"\b(?:enemy|opponent's|opposing)\b", m.text, re.I)
                 else _Mention(m.start, m.end, m.text, "their", m.piece, m.square)
                 for m in found]
    return sorted(found, key=lambda m: m.start)


_DEFEND_RE = re.compile(
    r"\b(?:defend|protect|guard|support)(?:s|ed|ing)?\b"
    r"(?P<by>\s+(?:only\s+|solely\s+|just\s+|now\s+)?(?:by|with)\b)?", re.IGNORECASE
)
# Hypotheticals and purposes say nothing about the board: "Qd7 would protect the knight",
# "you needed to guard f2", "if the rook defended g6".
_MODAL_RE = re.compile(
    r"(?:\b(?:would|could|might|should|can|will|must|may|if|whether|unless)\b[^.;:!?]{0,30}"
    r"|\bto\s+)\Z",
    re.IGNORECASE,
)
_NEGATION_RE = re.compile(r"\b(?:not|never|nothing|no one|none)\s+(?:\w+\s+)?\Z|n't\s+\Z",
                          re.IGNORECASE)
_PIECE_TYPES = {name: chess.PIECE_NAMES.index(name) for name in _PIECE_NAMES.split("|")}
_SIDE_LIST_RE = re.compile(r"^- (?:Your|Opponent's) pieces \((White|Black)\): (.+)\.$",
                           re.MULTILINE)
_TO_MOVE_RE = re.compile(r"^The position before your move \((White|Black) to move\):$",
                         re.MULTILINE)
_MOVE_LINE_RES = (re.compile(r"^- Your move (\S+) ", re.MULTILINE),
                  re.compile(r"^- The preferred move (\S+) ", re.MULTILINE))


def facts_boards(facts_text: str) -> tuple[chess.Color, list[chess.Board]] | None:
    """The coached colour and the boards a position row's facts describe: before the move,
    after the move played and after the preferred move (each when it parses)."""
    to_move = _TO_MOVE_RE.search(facts_text)
    sides = _SIDE_LIST_RE.findall(facts_text)
    if not to_move or len(sides) != 2:
        return None
    board = chess.Board(None)
    for color_name, pieces in sides:
        color = color_name == "White"
        for part in pieces.split(", "):
            name, _, square = part.partition(" on ")
            if name not in _PIECE_TYPES or len(square) != 2:
                return None
            board.set_piece_at(chess.parse_square(square), chess.Piece(_PIECE_TYPES[name], color))
    board.turn = to_move.group(1) == "White"
    boards = [board]
    for line_re in _MOVE_LINE_RES:
        m = line_re.search(facts_text)
        if m:
            after = board.copy(stack=False)
            try:
                after.push_san(m.group(1))
            except ValueError:
                continue
            boards.append(after)
    return board.turn, boards


def _spec(m: _Mention, you: chess.Color, same_as: chess.Color | None = None
          ) -> tuple[chess.PieceType, list[chess.Color], chess.Square | None]:
    """What a piece mention names: its type, the colours it could be, and its square when
    the text gives one ("your knight on g6", "the f4-pawn", "Qd5"). ``same_as`` settles an
    unowned mention's colour: in "the knight no longer protects the queen" both pieces are
    the defender's side's."""
    owner = m.owner
    colors = ([you] if owner == "your" else [not you] if owner in ("their", "opponent's")
              else [chess.WHITE] if owner == "white's" else [chess.BLACK]
              if owner == "black's" else [same_as] if same_as is not None
              else [chess.WHITE, chess.BLACK])
    return (_PIECE_TYPES[m.piece], colors,
            chess.parse_square(m.square.lower()) if m.square else None)


def _squares(board: chess.Board, spec, color: chess.Color) -> list[chess.Square]:
    piece, _, square = spec
    if square is None:
        return list(board.pieces(piece, color))
    return [square] if board.piece_at(square) == chess.Piece(piece, color) else []


def _defends(boards: list[chess.Board], defender, target) -> bool | None:
    """Whether a piece matching ``defender`` covers one matching ``target`` (same colour)
    on any board, or None when no board holds both. A mention without a square matches
    every such piece, so "your queen defends the knight" passes if it does on any board,
    wherever the queen stood."""
    seen = False
    for b in boards:
        for color in set(defender[1]) & set(target[1]):
            for d in _squares(b, defender, color):
                for t in _squares(b, target, color):
                    if d != t:
                        seen = True
                        if t in b.attacks(d):
                            return True
    return False if seen else None


# Between the subject and the verb, a modal, a purpose ("to"), a relocation ("putting it
# on e1 supports") or a pronoun that may point elsewhere makes the claim not about the
# piece as it stood.
_GAP_SKIP_RE = re.compile(
    r"\b(?:would|could|might|should|can|will|must|may|if|whether|unless|to|it|they|"
    r"when|once|after|before)\b|\b(?:on|into)\s+[a-h][1-8]\b",
    re.IGNORECASE,
)
_COUNT_RE = re.compile(r"\s+(?:only\s+)?(?:once|twice|\w+\s+times|well|enough|adequately)\b",
                       re.IGNORECASE)
_PASSIVE_RE = re.compile(r"\b(?:is|was|are|were|be|been|being|remains?|stays?)\s+"
                         r"(?:\w+\s+){0,2}\Z", re.IGNORECASE)


def check_defence_claims(coaching_text: str, facts_text: str) -> ClaimResult:
    """Flag "X defends Y" claims the board refutes.

    Conservative, as the placement check is. A defence claim is false only if no piece
    matching the defender covers one matching the target on any board the facts describe
    (before the move, after it, after the preferred move). Kings as targets are skipped
    ("the f7 pawn defends your king" means shelter), as are passives without "by" ("was
    defended only once" is a count, not a pairing), negations ("no longer" is kept: it
    asserts the piece did), hypotheticals, purposes and relocations. "Hanging" is not
    checked: the coaching uses it loosely for a piece that loses an exchange, which direct
    attacker and defender counts cannot settle. A move names the piece on its destination
    ("Qd5 defends" is the queen on d5, after that move), and "it" or "which" right before
    the verb stands for the nearest earlier piece or move that is not itself an object.
    Facts without a board check nothing.
    """
    result = ClaimResult()
    parsed = facts_boards(facts_text)
    if not parsed:
        return result
    you, boards = parsed
    starts = [0] + [m.end() for m in _SENTENCE_BREAK_RE.finditer(coaching_text)]
    ends = starts[1:] + [len(coaching_text)]
    for start, end in zip(starts, ends):
        sentence = coaching_text[start:end]
        mentions = _mentions(sentence)
        verbs = list(_DEFEND_RE.finditer(sentence))
        # In "defending your king and supporting your knight on g6" the king is an
        # object, not the subject of "supporting".
        objects = {next(m.start for m in mentions if m.start >= v.end())
                   for v in verbs if any(m.start >= v.end() for m in mentions)}
        objects = {o for o in objects for v in verbs
                   if 0 <= o - v.end() <= 20
                   and not re.search(r"[,;:()\u2014]", sentence[v.end():o])}
        # "it" or "which" before a defence verb stands for the nearest earlier subject: in
        # "your queen … it defended your knight, it defended your pawn" both are the queen.
        for p in _PRONOUN_SUBJECT_RE.finditer(sentence):
            earlier = [m for m in mentions if m.end <= p.start() and m.start not in objects]
            if earlier:
                a = earlier[-1]
                mentions.append(_Mention(p.start(), p.start() + len(p.group(0).split()[0]),
                                         a.text, a.owner, a.piece, a.square))
        mentions.sort(key=lambda m: m.start)
        for verb in verbs:
            before = sentence[: verb.start()]
            if _MODAL_RE.search(before) or _NEGATION_RE.search(before):
                continue
            if (_PASSIVE_RE.search(before) or _COUNT_RE.match(sentence, verb.end())) \
                    and not verb.group("by"):
                continue
            prior = [m for m in mentions if m.end <= verb.start()
                     and m.start not in objects and verb.start() - m.end <= 60]
            after = [m for m in mentions if m.start >= verb.end()
                     and m.start - verb.end() <= 20
                     and not re.search(r"[,;:()\u2014]", sentence[verb.end():m.start])]
            if (not prior or not after
                    or re.match(r"\s+(?:it|them|itself|both)\b", sentence[verb.end():], re.I)):
                continue  # "protecting it": the pronoun's piece is not the next mention
            first, second = prior[-1], after[0]
            if _GAP_SKIP_RE.search(sentence[first.end: verb.start()]):
                continue
            if verb.group("by") and re.search(r"\bby\b[^.;:!?]{0,30}\Z", sentence[:first.start]):
                continue  # "attacked by your queen and your rook, defended only by the king"
            if _INDIRECT_RE.search(sentence[verb.end():]):
                continue
            defender_m, target_m = (second, first) if verb.group("by") else (first, second)
            if defender_m.owner in ("a", "an"):
                continue  # generic: "an active rook that supports your passed pawn"
            defender = _spec(defender_m, you)
            target = _spec(target_m, you, defender[1][0] if len(defender[1]) == 1 else None)
            if target[0] == chess.KING:
                continue
            if (target[2] is None and target[0] == defender[0]
                    and _SAN_MENTION_RE.fullmatch(defender_m.text.strip(" *"))):
                continue  # "Ne2, which defended the knight": saved it, not a pairing
            verdict = _defends(boards, defender, target)
            if verdict is None:
                continue
            result.checked += 1
            if not verdict:
                result.violations.append(ClaimViolation(
                    kind="invented_defence", move="",
                    claimed=f"{defender_m.text} defends {target_m.text}",
                    actual="no such piece covers the other on any board in the facts",
                    excerpt=_excerpt(coaching_text, start + min(defender_m.start, target_m.start),
                                     start + max(defender_m.end, target_m.end))))
    return result


def _merge(*results: ClaimResult) -> ClaimResult:
    merged = ClaimResult()
    for r in results:
        merged.checked += r.checked
        merged.violations.extend(r.violations)
    return merged


def check_claims_from_report(
    coaching_text: str,
    report: dict,
    coached_side: str | None = None,
    max_mistakes: int = 6,
    facts: str | None = None,
) -> ClaimResult:
    """Full check: role inversion, invented castling, invented placement.

    Mirrors :func:`eval.grounding.grounding_from_report` — the facts block is rebuilt
    exactly as the coach received it, so the roles checked are the roles it was given.
    Pass ``facts`` when the caller already holds that exact block, to skip re-deriving it.
    """
    if coached_side is None:
        coached_side = prompts.choose_coached_side(report)
    if facts is None:
        facts = prompts.format_report_facts(report, coached_side, max_mistakes)
    return _merge(
        check_roles(coaching_text, facts),
        check_castling(coaching_text, report, coached_side),
        check_board_state(coaching_text, report, coached_side),
    )
