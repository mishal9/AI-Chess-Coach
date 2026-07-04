"""Coaching-quality rubric: the axes an engine can't score, and their data model.

Grounding (``eval.grounding``) catches invented moves deterministically. The rubric
covers the *subjective* qualities that need judgment — is the coaching correct, clear,
actionable, and does it identify the single key mistake? These are scored by an LLM judge
(``eval.judge``); this module just defines the axes, the 1-5 scale, and a validated
container so a judge verdict can't silently produce a malformed score.
"""

from __future__ import annotations

from dataclasses import dataclass, field

SCALE_MIN = 1
SCALE_MAX = 5

# Axis -> what a judge is rating. Order is the reporting order.
RUBRIC_AXES: dict[str, str] = {
    "factual_correctness": (
        "Does the coaching match the engine facts and avoid inventing moves, "
        "evaluations, or tactics? 1 = fabricates or contradicts the facts; "
        "5 = fully consistent with them."
    ),
    "clarity": (
        "Is it clear, well-organized, and understandable to an improving player? "
        "1 = confusing or rambling; 5 = crisp and easy to follow."
    ),
    "actionability": (
        "Does it give concrete, useful things to work on? "
        "1 = vague or no advice; 5 = specific and directly actionable."
    ),
    "identifies_key_mistake": (
        "Does it correctly identify and lead with the single most important mistake "
        "(or correctly recognize there was no single big error)? "
        "1 = misses or misranks it; 5 = nails the key moment."
    ),
}


class RubricError(ValueError):
    """A judge verdict was missing axes or otherwise unusable."""


def _clamp(value: int) -> int:
    return max(SCALE_MIN, min(SCALE_MAX, value))


@dataclass
class RubricScore:
    """A validated per-axis rubric score with a free-text rationale."""

    scores: dict[str, int] = field(default_factory=dict)
    rationale: str = ""

    @property
    def overall(self) -> float:
        """Mean across the rubric axes (0.0 if somehow empty)."""
        if not self.scores:
            return 0.0
        return round(sum(self.scores.values()) / len(self.scores), 2)

    def to_dict(self) -> dict:
        return {
            "scores": dict(self.scores),
            "overall": self.overall,
            "rationale": self.rationale,
        }

    @classmethod
    def from_judge_json(cls, data: dict) -> "RubricScore":
        """Build (and validate) a score from a judge's parsed JSON verdict.

        Every rubric axis must be present and integer-coercible; values are clamped to
        the 1-5 scale. A missing or non-numeric axis is a hard error, so a broken judge
        surfaces loudly instead of scoring 0 silently.
        """
        scores: dict[str, int] = {}
        for axis in RUBRIC_AXES:
            if axis not in data:
                raise RubricError(f"judge verdict missing axis {axis!r}")
            try:
                scores[axis] = _clamp(int(data[axis]))
            except (TypeError, ValueError) as exc:
                raise RubricError(
                    f"axis {axis!r} is not an integer: {data[axis]!r}"
                ) from exc
        return cls(scores=scores, rationale=str(data.get("rationale", "")))
