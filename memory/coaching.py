"""Generated coaching, stored with the facts it was generated from.

Storing the facts block alongside the text is the point of this module, not an extra. This
project has been bitten four separate times by artifacts that didn't record enough to know
whether they could be checked or compared — the missing ``cited``/``allowed`` sets, the
missing ``game_index``, the resume-key collision, and the cross-version ``eval.compare``
bug. Keeping the exact prompt facts means any stored coaching can be re-scored for
grounding later, for free, without regenerating anything.

It also pays off immediately: the page that shows coaching can say how many moves it cited
and whether all of them were ones the model was actually given.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class Coaching:
    id: int
    game_id: int
    coached_side: str
    model: str
    text: str
    facts: str
    used_profile: bool
    created_at: str

    def grounding(self):
        """Score this coaching against the facts it was actually given.

        Possible only because the facts were stored. Returns a
        :class:`eval.grounding.GroundingResult` — ``cited``, ``allowed``, ``hallucinated``.
        """
        from eval.grounding import score_grounding

        return score_grounding(self.text, self.facts)


def save(
    conn: sqlite3.Connection,
    game_id: int,
    coached_side: str,
    model: str,
    text: str,
    facts: str,
    used_profile: bool = False,
) -> int:
    """Store one generated coaching text. Returns its row id."""
    with conn:
        cursor = conn.execute(
            """
            INSERT INTO coaching (game_id, coached_side, model, text, facts,
                                  used_profile, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                game_id,
                coached_side,
                model,
                text,
                facts,
                int(used_profile),
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ),
        )
    return cursor.lastrowid


def latest(conn: sqlite3.Connection, game_id: int) -> Coaching | None:
    """The most recent coaching for a game, or ``None``.

    Most recent rather than only: regenerating keeps the old rows, so a change in model or
    prompt can be compared against what it replaced instead of overwriting the evidence.
    """
    row = conn.execute(
        "SELECT * FROM coaching WHERE game_id = ? ORDER BY id DESC LIMIT 1", (game_id,)
    ).fetchone()
    if row is None:
        return None
    fields = dict(row)
    fields["used_profile"] = bool(fields["used_profile"])
    return Coaching(**fields)
