"""Pure scoring logic for move quality — no engine, no I/O, easy to unit-test.

Everything here works in **centipawns from White's point of view** (the convention
``python-chess`` uses via ``score.white()``): positive = good for White, negative =
good for Black. ``+100`` is roughly "up one pawn".

Three ideas live here:

1. *Centipawn loss* — how much a played move worsened the position, measured from the
   mover's own perspective. Always >= 0 (a move can't do better than the engine's best,
   and small negatives from search noise are clamped to 0). Kept for display + ACPL.
2. *Win probability* — a sigmoid mapping centipawns onto a [0, 1] win chance. Loss is then
   measured as the drop in the mover's *win probability*, which naturally clamps
   already-decided positions: going +900 → +600 barely changes the win chance, and a forced
   mate (±MATE_CP) saturates near 1/0 so it can't explode into a fake blunder.
3. *Classification* — bucketing the win-probability loss into the familiar inaccuracy /
   mistake / blunder labels, mirroring how Lichess judges moves.
"""

from __future__ import annotations

import math
from enum import Enum

# A forced mate is worth more than any material count. The analyzer maps "mate in N" onto
# ``MATE_CP - N`` (python-chess's ``Score.score(mate_score=MATE_CP)``, so closer mates score
# slightly higher) and all the arithmetic below works on plain integers. 10000cp = 100
# pawns, unreachable by normal material.
MATE_CP = 10_000


class MoveQuality(str, Enum):
    """Move quality labels, ordered from best to worst."""

    BEST = "best"
    GOOD = "good"
    INACCURACY = "inaccuracy"  # ?!
    MISTAKE = "mistake"        # ?
    BLUNDER = "blunder"        # ??

    @property
    def symbol(self) -> str:
        return {
            MoveQuality.BEST: "",
            MoveQuality.GOOD: "",
            MoveQuality.INACCURACY: "?!",
            MoveQuality.MISTAKE: "?",
            MoveQuality.BLUNDER: "??",
        }[self]


# Lower bound (inclusive) of *win-probability* loss for each label, in [0, 1]. Tunable.
# A move that hands the opponent a 30-percentage-point swing in win chance is a blunder.
INACCURACY_WP = 0.10
MISTAKE_WP = 0.20
BLUNDER_WP = 0.30

# Logistic steepness mapping centipawns → win probability. This is Lichess's fitted
# constant; cp=0 → 0.5, and ±MATE_CP saturates to ~1/~0.
WIN_PROB_K = 0.00368208

# For *average* centipawn loss (ACPL) we cap each eval before differencing so a decided
# position (huge eval) doesn't dominate the average. Conventional bound: ±10 pawns.
EVAL_CAP = 1000


def centipawn_loss(
    eval_before_best: int,
    eval_after: int,
    mover_is_white: bool,
) -> int:
    """How many centipawns the played move gave up, from the mover's perspective.

    Both inputs are White-POV centipawns:
    - ``eval_before_best``: the engine's best achievable eval *before* the move.
    - ``eval_after``: the eval of the position that actually resulted from the move.

    For White, value drops when the White-POV eval falls; for Black it's the mirror.
    Negative results (the move looked better than "best" due to search depth differences)
    are clamped to 0.
    """
    if mover_is_white:
        loss = eval_before_best - eval_after
    else:
        loss = eval_after - eval_before_best
    return max(0, loss)


def capped_centipawn_loss(
    eval_before_best: int,
    eval_after: int,
    mover_is_white: bool,
) -> int:
    """Like :func:`centipawn_loss` but with each eval capped to ``±EVAL_CAP`` first.

    Used for ACPL so a single decided position (e.g. a forced mate at ±MATE_CP) can't
    swamp the average.
    """
    lo, hi = -EVAL_CAP, EVAL_CAP
    before = max(lo, min(hi, eval_before_best))
    after = max(lo, min(hi, eval_after))
    return centipawn_loss(before, after, mover_is_white)


def win_prob(cp: int) -> float:
    """White's win probability in ``(0, 1)`` for a White-POV centipawn eval.

    Logistic sigmoid: ``cp=0 → 0.5``; large magnitudes saturate toward 1 (White winning)
    or 0 (Black winning), so decided positions can't produce large win-prob swings.
    """
    return 1.0 / (1.0 + math.exp(-WIN_PROB_K * cp))


def win_prob_loss(
    eval_before_best: int,
    eval_after: int,
    mover_is_white: bool,
) -> float:
    """Drop in the *mover's* win probability caused by the played move, clamped to ``>= 0``.

    Both inputs are White-POV centipawns. The mover's win probability is White's if White
    moved, else its complement. Because win probability is bounded in ``(0, 1)``, this is the
    self-clamping loss metric that drives move classification.
    """
    before = win_prob(eval_before_best)
    after = win_prob(eval_after)
    if not mover_is_white:
        before, after = 1.0 - before, 1.0 - after
    return max(0.0, before - after)


def classify(wp_loss: float) -> MoveQuality:
    """Bucket a (non-negative) win-probability loss into a MoveQuality label."""
    if wp_loss >= BLUNDER_WP:
        return MoveQuality.BLUNDER
    if wp_loss >= MISTAKE_WP:
        return MoveQuality.MISTAKE
    if wp_loss >= INACCURACY_WP:
        return MoveQuality.INACCURACY
    if wp_loss <= 0.0:
        return MoveQuality.BEST
    return MoveQuality.GOOD
