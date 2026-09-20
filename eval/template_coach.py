"""A coach with no model in it: the control arm that asks whether the LLM adds anything.

Every other arm is handed the engine's facts block and asked to turn it into coaching. This
one turns the same facts into coaching with string formatting alone. It reads exactly what an
LLM coach reads (:func:`engine.report.coachable_mistakes` and the report summary), names only
the moves that block lists, and states no tactic, motif or evaluation the block does not.

That makes it a floor. It cannot hallucinate, so it should score at or near the ceiling on
grounding and on the claim checkers; what is left to measure is whether the judged clarity,
actionability and pedagogy of the LLM arms are worth having over a script. Placed under the
prompted and fine-tuned 8B arms and the teacher, it says how much of any judged score is
carried by the engine facts alone.

Wire-up: ``python -m eval.run --coach-model template`` (see :func:`eval.run.make_coach_fn`).
It is deterministic, so it needs no seed and no temperature, and costs nothing to generate.
"""

from __future__ import annotations

from engine.report import coachable_mistakes, move_label
from engine.scoring import MoveQuality

# The ``--coach-model`` value that selects this coach instead of an Ollama model.
NAME = "template"

# Same threshold the facts block uses to call a mistake-free game "clean".
_CLEAN_ACPL = 20.0

_QUALITY_WORD = {"blunder": "a blunder", "mistake": "a mistake", "inaccuracy": "an inaccuracy"}


def _win_pct(m: dict) -> int:
    return round(m["win_prob_loss"] * 100)


def _played(m: dict) -> str:
    return f"{move_label(m['move_number'], m['side'])}{m['san']}{MoveQuality(m['quality']).symbol}"


def _alternative(m: dict) -> str:
    """The recommended-move clause, or empty when the engine agreed with the move played."""
    if m.get("best_san") and m["best_san"] != m["san"]:
        return f" The engine preferred {m['best_san']}."
    return ""


def _worst(m: dict) -> str:
    return (
        f"The most costly moment was {_played(m)}, {_QUALITY_WORD[m['quality']]}. "
        f"It cost about {_win_pct(m)}% win probability.{_alternative(m)}"
    )


def _other(m: dict) -> str:
    alt = f" (the engine preferred {m['best_san']})" if _alternative(m) else ""
    return f"{_played(m)}{alt}, about {_win_pct(m)}%"


def template_coaching(report: dict, coached_side: str, max_mistakes: int = 6) -> str:
    """Coaching for one side of a game, built only from the facts an LLM coach is given."""
    summary = report["summary"]
    opponent = "black" if coached_side == "white" else "white"
    acpl = summary[f"acpl_{coached_side}"]
    opp_acpl = summary[f"acpl_{opponent}"]
    mistakes = coachable_mistakes(report, coached_side)[:max_mistakes]

    opening = (
        f"Your average centipawn loss was {acpl}, against {opp_acpl} for your opponent "
        "(lower is better)."
    )

    if not mistakes:
        if acpl <= _CLEAN_ACPL:
            return (
                f"{opening}\n\n"
                "The engine flagged no inaccuracies, mistakes or blunders on your side, and "
                "your average loss was low, so this was a clean game.\n\n"
                "To keep improving, keep checking each opponent move for a threat before you "
                "play, and review the game for ideas to repeat."
            )
        return (
            f"{opening}\n\n"
            "There was no single flagged blunder or mistake, but your average loss was high: "
            "you lost ground gradually through many small imprecisions rather than one big "
            "error.\n\n"
            "To improve, slow down in equal positions and compare two or three candidate "
            "moves before committing."
        )

    paragraphs = [opening, _worst(mistakes[0])]
    rest = mistakes[1:]
    if rest:
        paragraphs.append("The other costly moves were " + "; ".join(_other(m) for m in rest) + ".")

    if len(mistakes) > 1:
        advice = (
            f"You had {len(mistakes)} flagged moves in this game. Before each move, check "
            "what your opponent's last move threatens, and compare it with the engine's "
            "preferred move afterwards."
        )
    else:
        advice = (
            "Before your next game, spend a moment on each move checking what your "
            "opponent's last move threatens, then review this moment against the engine's "
            "preferred move."
        )
    paragraphs.append(advice)
    return "\n\n".join(paragraphs)
