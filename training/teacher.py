"""Claude-as-teacher: generate the gold coaching a record is built around.

The teacher sees the **same facts block** the small student sees at inference (built by
``coach.prompts``), so every pair is a faithful ``deployed-input → gold-output`` mapping —
we are not teaching the student to answer a richer prompt than it will ever get. What
differs is the *system* instruction: the teacher gets the student's strict grounding rules
plus an "excellence" layer that asks for the clearest, most pedagogically useful coaching
those exact facts support. Fine-tuning then transfers that quality onto the standard prompt.

The teacher runs through the pluggable ``eval.backends`` seam, so distillation defaults to
Claude (``anthropic``) but can be pointed at any backend without touching this module.
"""

from __future__ import annotations

from typing import Callable

from coach import prompts
from eval import backends

# A teacher takes (report, coached_side) and returns the coaching text. Injectable so the
# pipeline is unit-testable with a canned teacher — no API key, no network.
TeacherFn = Callable[[dict, str], str]

# The student's grounding contract, hardened with a quality bar. We keep every STRICT
# GROUNDING rule verbatim from the deployed prompt (a hallucinated target is worse than
# no target) and add only what raises the ceiling of an already-grounded answer.
TEACHER_SYSTEM_PROMPT = prompts.SYSTEM_PROMPT + """

YOU ARE THE GOLD-STANDARD TEACHER (your output becomes training data):
- Stay ruthlessly within the facts — a single invented move poisons the dataset. When the \
facts under-determine something, teach the principle instead of guessing the position.
- Explain the *why* a strong human coach would: what the mistake conceded, what the better \
move accomplishes, and the reusable idea behind it — not just a restatement of the numbers.
- Model the exact voice and shape we want the student model to imitate: warm, direct, \
concise, a few short paragraphs ending in one or two concrete things to work on."""


def build_teacher_messages(report: dict, coached_side: str) -> list[dict]:
    """Teacher messages: the student's exact facts/user turn under the teacher system prompt.

    Reuses :func:`coach.prompts.build_messages` for the user turn so the teacher is grounded
    on byte-identical facts, then swaps in :data:`TEACHER_SYSTEM_PROMPT`.
    """
    student = prompts.build_messages(report, coached_side)
    return [{"role": "system", "content": TEACHER_SYSTEM_PROMPT}, *student[1:]]


def make_teacher_fn(backend_name: str = "anthropic", model: str | None = None) -> TeacherFn:
    """A teacher that generates coaching via the named ``eval.backends`` backend.

    ``backend_name`` is one of ``ollama`` / ``anthropic`` / ``gemini`` (default Claude, the
    quality source). ``model`` overrides that backend's default. Credentials and lazy SDK
    imports are handled inside the backend exactly as they are for the eval judge.
    """
    backend = {
        "ollama": backends.ollama_backend,
        "anthropic": backends.anthropic_backend,
        "gemini": backends.gemini_backend,
    }[backend_name]

    def teacher_fn(report: dict, coached_side: str) -> str:
        messages = build_teacher_messages(report, coached_side)
        return backend(messages, model=model)

    return teacher_fn
