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

import os
import time
from typing import Callable

import requests

from coach import prompts
from eval import backends

# A teacher takes (report, coached_side) and returns the coaching text. Injectable so the
# pipeline is unit-testable with a canned teacher — no API key, no network.
TeacherFn = Callable[[dict, str], str]

# A position teacher additionally takes the move dict (one entry of report["moves"]).
PositionTeacherFn = Callable[[dict, str, dict], str]

# The quality bar layered on top of the student's grounding contract. We keep every
# STRICT GROUNDING rule verbatim from the deployed prompts (a hallucinated target is
# worse than no target) and add only what raises the ceiling of a grounded answer.
_EXCELLENCE_LAYER = """

YOU ARE THE GOLD-STANDARD TEACHER (your output becomes training data):
- Stay ruthlessly within the facts — a single invented move poisons the dataset. When the \
facts under-determine something, teach the principle instead of guessing the position.
- Explain the *why* a strong human coach would: what the mistake conceded, what the better \
move accomplishes, and the reusable idea behind it — not just a restatement of the numbers.
- Model the exact voice and shape we want the student model to imitate: warm, direct, \
concise, a few short paragraphs ending in one or two concrete things to work on."""

TEACHER_SYSTEM_PROMPT = prompts.SYSTEM_PROMPT + _EXCELLENCE_LAYER
TEACHER_POSITION_SYSTEM_PROMPT = prompts.POSITION_SYSTEM_PROMPT + _EXCELLENCE_LAYER


def build_teacher_messages(report: dict, coached_side: str) -> list[dict]:
    """Teacher messages: the student's exact facts/user turn under the teacher system prompt.

    Reuses :func:`coach.prompts.build_messages` for the user turn so the teacher is grounded
    on byte-identical facts, then swaps in :data:`TEACHER_SYSTEM_PROMPT`.
    """
    student = prompts.build_messages(report, coached_side)
    return [{"role": "system", "content": TEACHER_SYSTEM_PROMPT}, *student[1:]]


def build_teacher_position_messages(
    report: dict, coached_side: str, move: dict
) -> list[dict]:
    """Position-row teacher messages: the student's exact single-moment user turn under
    the position teacher system prompt (same construction as whole-game rows)."""
    student = prompts.build_position_messages(report, coached_side, move)
    return [{"role": "system", "content": TEACHER_POSITION_SYSTEM_PROMPT}, *student[1:]]


# DeepSeek's own API (OpenAI-compatible). Its terms assign outputs to the caller and allow
# "training other models (such as model distillation)" — unlike the Anthropic terms this
# project's v2 rows were generated under (see PLAN.md, N1/N2). The docs name only the alias
# ``deepseek-v4-pro``, not a dated snapshot, so the model the response reports is recorded.
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-pro"
# Non-zero on purpose: a grounding retry only helps if a re-roll can differ.
DEEPSEEK_TEMPERATURE = 0.7
# ``None`` sends no ``thinking`` field and takes the API's default; "enabled"/"disabled"
# sends it explicitly. Set by ``training.distill --teacher-thinking`` and recorded there.
DEEPSEEK_THINKING: str | None = None
DEEPSEEK_MAX_ATTEMPTS = 5
DEEPSEEK_TIMEOUT_S = 300

# Running tally of what the API reported, so a run can print its real token bill.
DEEPSEEK_USAGE = {
    "calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0,
    "models": set(),
}


def deepseek_backend(messages: list[dict], model: str | None = None) -> str:
    """Chat with DeepSeek via its OpenAI-compatible endpoint; return the answer text only.

    Needs ``DEEPSEEK_API_KEY`` (environment or ``.env``). Only ``message.content`` is used:
    any ``reasoning_content`` is dropped, so a thinking-mode trace can never end up in a
    training target. 429 and 5xx responses are retried with backoff; anything else raises.
    """
    backends._load_dotenv()
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise SystemExit("DEEPSEEK_API_KEY is not set (environment or .env).")
    body = {
        "model": model or DEFAULT_DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": DEEPSEEK_TEMPERATURE,
        "stream": False,
    }
    if DEEPSEEK_THINKING:
        body["thinking"] = {"type": DEEPSEEK_THINKING}

    for attempt in range(1, DEEPSEEK_MAX_ATTEMPTS + 1):
        resp = requests.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json=body,
            timeout=DEEPSEEK_TIMEOUT_S,
        )
        if resp.status_code == 429 or resp.status_code >= 500:
            if attempt == DEEPSEEK_MAX_ATTEMPTS:
                resp.raise_for_status()
            time.sleep(min(2 ** attempt, 30))
            continue
        if resp.status_code >= 400:
            raise RuntimeError(f"DeepSeek API {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        usage = data.get("usage") or {}
        DEEPSEEK_USAGE["calls"] += 1
        DEEPSEEK_USAGE["prompt_tokens"] += usage.get("prompt_tokens", 0)
        DEEPSEEK_USAGE["completion_tokens"] += usage.get("completion_tokens", 0)
        DEEPSEEK_USAGE["reasoning_tokens"] += (
            (usage.get("completion_tokens_details") or {}).get("reasoning_tokens", 0)
        )
        if data.get("model"):
            DEEPSEEK_USAGE["models"].add(data["model"])
        return (data["choices"][0]["message"].get("content") or "").strip()
    raise RuntimeError("unreachable")  # pragma: no cover


def _backend(backend_name: str):
    return {
        "ollama": backends.ollama_backend,
        "anthropic": backends.anthropic_backend,
        "gemini": backends.gemini_backend,
        "deepseek": deepseek_backend,
    }[backend_name]


def make_teacher_fn(backend_name: str = "anthropic", model: str | None = None) -> TeacherFn:
    """A teacher that generates coaching via the named ``eval.backends`` backend.

    ``backend_name`` is one of ``ollama`` / ``anthropic`` / ``gemini`` (default Claude, the
    quality source). ``model`` overrides that backend's default. Credentials and lazy SDK
    imports are handled inside the backend exactly as they are for the eval judge.
    """
    backend = _backend(backend_name)

    def teacher_fn(report: dict, coached_side: str) -> str:
        messages = build_teacher_messages(report, coached_side)
        return backend(messages, model=model)

    return teacher_fn


def make_position_teacher_fn(
    backend_name: str = "anthropic", model: str | None = None
) -> PositionTeacherFn:
    """Like :func:`make_teacher_fn`, for single-position (``kind="position"``) rows."""
    backend = _backend(backend_name)

    def position_teacher_fn(report: dict, coached_side: str, move: dict) -> str:
        messages = build_teacher_position_messages(report, coached_side, move)
        return backend(messages, model=model)

    return position_teacher_fn
