"""Thin wrapper around a local Ollama chat model.

Keeps the rest of the coach package ignorant of the transport: it just hands us a
list of chat messages and gets back a string. Errors that the user can actually fix
(server down, model not pulled) are turned into clear, actionable messages instead of
raw connection tracebacks.
"""

from __future__ import annotations

import os
import re

import ollama

# The project's own fine-tune, and the best grounded coach we have measured: 0.965
# grounding against the prompted base's 0.923. The old default was the Phase-2 Qwen2.5-3B
# baseline, which was retired as a reference in August 2026 — every CLI call passed
# --model explicitly, so nothing caught that the default had gone stale until the web UI
# used it and produced coaching with five invented moves out of nine.
#
# Override with COACH_MODEL for a machine that has something else pulled. `qwen3:8b` is
# the un-fine-tuned base: same judged quality, slightly worse citation hygiene, but it is
# `ollama pull`-able, whereas the fine-tune has to be built from the training notebook.
DEFAULT_MODEL = os.environ.get("COACH_MODEL", "qwen-coach-8b-v2")

# Low but non-zero: we want faithful, grounded coaching, not creative variation, while
# still avoiding the robotic repetition of temperature 0.
DEFAULT_TEMPERATURE = 0.3

# Qwen3-family coaches are hybrid reasoners trained here in non-thinking mode, but a
# raw-GGUF Ollama import can still emit a leading <think> block. We strip it rather
# than pass Ollama's `think` flag, which errors on models not registered as thinking-
# capable (e.g. the baseline Qwen2.5 and our own GGUF imports).
_THINK_BLOCK = re.compile(r"\A\s*<think>.*?</think>", re.DOTALL)


class CoachModelError(RuntimeError):
    """Raised when the Ollama model can't be reached — with a fixable-cause message."""


def chat(
    messages: list[dict],
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
) -> str:
    """Send ``messages`` to the model and return the assistant's text.

    Raises :class:`CoachModelError` with guidance if the server is down or the model
    hasn't been pulled, so callers (and the CLI) can surface something useful.
    """
    try:
        response = ollama.chat(
            model=model,
            messages=messages,
            options={"temperature": temperature},
        )
    except ConnectionError as exc:
        raise CoachModelError(
            "Could not reach the Ollama server. Start it with `ollama serve` "
            "(or open the Ollama app), then retry."
        ) from exc
    except ollama.ResponseError as exc:
        # The most common ResponseError is a missing model.
        if "not found" in str(exc).lower():
            raise CoachModelError(
                f"Model {model!r} isn't available locally. Pull it with "
                f"`ollama pull {model}`."
            ) from exc
        raise CoachModelError(f"Ollama returned an error: {exc}") from exc

    return _THINK_BLOCK.sub("", response["message"]["content"]).strip()
