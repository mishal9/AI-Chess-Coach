"""LLM-as-judge: score a coaching text against the engine facts on the rubric.

The judge is shown the same objective facts the coach received plus the coaching it
produced, and must return a strict-JSON verdict (one integer per rubric axis + a short
rationale). We parse that defensively — models like to wrap JSON in prose or code fences
— and validate it through :class:`eval.rubric.RubricScore`.

Note: the default judge is the same small local model as the coach, which makes it a
*weak* judge (fine for a $0 local baseline harness). Grading is provider-pluggable — pass
``backend=backends.anthropic_backend`` (or ``gemini_backend``) to judge with a frontier
model instead; see :mod:`eval.backends`.
"""

from __future__ import annotations

import json
import re
from typing import Callable

from coach import prompts
from eval import backends, rubric

# A backend is any callable that takes chat messages (+ optional model) and returns text.
Backend = Callable[..., str]


class JudgeError(RuntimeError):
    """The judge's output could not be parsed into a verdict."""


def _axis_lines() -> str:
    return "\n".join(f"- {axis}: {desc}" for axis, desc in rubric.RUBRIC_AXES.items())


def build_judge_messages(coaching_text: str, facts_text: str) -> list[dict]:
    """Build the ``[system, user]`` messages asking the judge to score the coaching."""
    axes = ", ".join(rubric.RUBRIC_AXES)
    system = (
        "You are a strict, fair evaluator of chess coaching quality. You are given the "
        "objective engine facts about a game and a coaching write-up produced from them. "
        "Score the coaching on each rubric axis using an integer from "
        f"{rubric.SCALE_MIN} (worst) to {rubric.SCALE_MAX} (best).\n\n"
        f"Rubric axes:\n{_axis_lines()}\n\n"
        "Judge factual_correctness ONLY against the provided facts — if the coaching "
        "mentions a move or evaluation not in the facts, that is fabrication and must be "
        "penalized. Do not reward fluent writing that isn't grounded in the facts.\n\n"
        "Respond with ONLY a JSON object, no prose or code fences, with these exact "
        f"integer keys ({axes}) plus a short \"rationale\" string. Example:\n"
        '{"factual_correctness": 4, "clarity": 5, "actionability": 3, '
        '"identifies_key_mistake": 4, "rationale": "..."}'
    )
    user = (
        "ENGINE FACTS:\n"
        f"{facts_text}\n\n"
        "COACHING TO EVALUATE:\n"
        f"{coaching_text}\n\n"
        "Return the JSON verdict now."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def parse_verdict(raw: str) -> rubric.RubricScore:
    """Extract and validate a rubric score from the judge's raw text output.

    Tolerant of code fences and surrounding prose: pulls the outermost ``{...}`` block and
    parses that. Raises :class:`JudgeError` if nothing parseable is found.
    """
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise JudgeError(f"no JSON object found in judge output: {raw!r}")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise JudgeError(f"judge output was not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise JudgeError(f"judge JSON was not an object: {data!r}")
    try:
        return rubric.RubricScore.from_judge_json(data)
    except rubric.RubricError as exc:
        raise JudgeError(str(exc)) from exc


def judge_coaching(
    coaching_text: str,
    report: dict,
    coached_side: str | None = None,
    backend: Backend | None = None,
    model: str | None = None,
    max_mistakes: int = 6,
) -> rubric.RubricScore:
    """Score a coaching text by judging it against the facts rebuilt from ``report``.

    ``backend`` selects the provider (defaults to the local Ollama judge); ``model``
    overrides that backend's default model. The backend owns provider-specific concerns
    like temperature, so callers don't have to.
    """
    if coached_side is None:
        coached_side = prompts.choose_coached_side(report)
    if backend is None:
        backend = backends.DEFAULT_BACKEND
    facts = prompts.format_report_facts(report, coached_side, max_mistakes)
    messages = build_judge_messages(coaching_text, facts)
    raw = backend(messages, model=model)
    return parse_verdict(raw)
