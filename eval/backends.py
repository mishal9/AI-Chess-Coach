"""Pluggable chat backends for the LLM judge.

The judge only needs *a function that takes chat messages and returns text*. Isolating
that behind a small seam lets the grading run on a local model (the default — offline and
CI-friendly) or a frontier model (Claude, Gemini) with a one-argument swap, and nothing
in the rubric or verdict parsing changes. Provider SDKs are imported lazily, so the base
install needs none of them; install the extras only for the backend you use:

    uv pip install -e '.[eval]'   # anthropic + google-genai

Each backend takes ``messages`` (a ``[{"role","content"}, ...]`` list with one ``system``
entry and the rest ``user``) and an optional ``model`` override, and returns the raw text
of the model's reply for :func:`eval.judge.parse_verdict` to handle.
"""

from __future__ import annotations

import os
import re
import time

# Sensible default judge models per provider. Flagships, because grading reliability
# matters more than cost here (a judge call is a fraction of a cent) — see eval/README.md.
DEFAULT_ANTHROPIC_MODEL = "claude-opus-4-8"
# gemini-2.5-pro is closed to new API keys as of late 2026 ("no longer available to new
# users"). 3.1-pro is the peer-strength counterpart to the Anthropic judge, which is what a
# cross-judge check wants: disagreement should be attributable to rubric ambiguity, not to
# one judge being weaker. It needs billing enabled — at 1143 in / 217 out per judgement it
# costs about $0.005 a call, roughly $0.28 for a full 58-call cross-judge run.
#
# GEMINI_MODEL overrides it. `gemini-2.5-flash` is the free-tier fallback (5 requests a
# minute, 20 a day) at about a fifth the cost and noticeably more generous scoring; if you
# use it, say so in any write-up rather than implying a peer-level check.
DEFAULT_GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-pro-preview")

# Enough to ride out the free tier's per-minute window a few times over.
GEMINI_MAX_RETRIES = 6


class GeminiDailyQuotaExhausted(RuntimeError):
    """The daily free-tier cap is spent — waiting will not help before tomorrow."""

_dotenv_loaded = False


def _load_dotenv(path: str | None = None) -> None:
    """Load API keys from a ``.env`` file into the environment, so a key doesn't have to
    be exported in every shell. The provider SDKs then read it the usual way.

    ``.env`` is gitignored — real keys never get committed. A shell-exported variable
    always wins (``override=False``), so ``.env`` is a convenience, not an override. Safe
    no-op if ``python-dotenv`` isn't installed (install it via the ``eval`` extra) — env
    vars still work. The default (auto) load is cached; pass ``path`` to force a reload.
    """
    global _dotenv_loaded
    if _dotenv_loaded and path is None:
        return
    try:
        from dotenv import find_dotenv, load_dotenv
    except ModuleNotFoundError:
        _dotenv_loaded = True  # nothing to do; rely on real env vars
        return
    load_dotenv(path or find_dotenv(usecwd=True), override=False)
    if path is None:
        _dotenv_loaded = True


def _split_system(messages: list[dict]) -> tuple[str | None, list[dict]]:
    """Separate the single ``system`` message from the conversational turns.

    Ollama accepts a system message inline, but the Anthropic and Gemini SDKs take the
    system prompt as a dedicated top-level parameter — so backends for those providers
    need it lifted out.
    """
    system = next((m["content"] for m in messages if m["role"] == "system"), None)
    turns = [m for m in messages if m["role"] != "system"]
    return system, turns


def ollama_backend(messages: list[dict], model: str | None = None) -> str:
    """Local Ollama chat — the default judge. Deterministic (temperature 0)."""
    from coach import client

    return client.chat(messages, model=model or client.DEFAULT_MODEL, temperature=0.0)


def anthropic_backend(messages: list[dict], model: str | None = None) -> str:
    """Judge with Claude via the Anthropic SDK.

    Needs credentials: ``ANTHROPIC_API_KEY`` (from the environment or a ``.env`` file) or
    an ``ant auth login`` profile. Note the Opus/Sonnet models reject a ``temperature``
    parameter, so we omit it and rely on the model default — fine for a small structured
    verdict. (Adaptive thinking would improve grading quality at extra token cost; left
    off here to keep judge cost predictable.)
    """
    import anthropic

    _load_dotenv()
    system, turns = _split_system(messages)
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model or DEFAULT_ANTHROPIC_MODEL,
        max_tokens=1024,
        system=system,
        messages=[{"role": m["role"], "content": m["content"]} for m in turns],
    )
    return "".join(b.text for b in response.content if b.type == "text").strip()


def gemini_backend(messages: list[dict], model: str | None = None) -> str:
    """Judge with Gemini via the google-genai SDK.

    Needs ``GEMINI_API_KEY`` / ``GOOGLE_API_KEY`` (from the environment or a ``.env``
    file). Gemini accepts ``temperature`` (so we pin it to 0) and can enforce a JSON
    response server-side, which makes the verdict reliably parseable.
    """
    from google import genai

    _load_dotenv()
    system, turns = _split_system(messages)
    # Pass the key explicitly. The SDK prefers GOOGLE_API_KEY when both are set, so a
    # stale one left over in a shell silently shadows the key in .env — which presents
    # as a confusing auth or 404 error against the wrong project.
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    client = genai.Client(api_key=api_key) if api_key else genai.Client()
    config = genai.types.GenerateContentConfig(
        system_instruction=system,
        temperature=0.0,
        response_mime_type="application/json",
    )
    contents = "\n\n".join(m["content"] for m in turns)

    # The free tier allows 5 requests a minute, and a judged run is dozens of calls. A 429
    # is a "wait" not a failure, so honour the server's own retryDelay rather than losing
    # an hour of engine work to it.
    for attempt in range(GEMINI_MAX_RETRIES):
        try:
            return client.models.generate_content(
                model=model or DEFAULT_GEMINI_MODEL, contents=contents, config=config
            ).text.strip()
        except Exception as exc:  # noqa: BLE001 - re-raised below unless it is a 429
            message = str(exc)
            if "429" not in message or attempt == GEMINI_MAX_RETRIES - 1:
                raise
            if "PerDay" in message:
                # A per-minute limit is a wait; a per-day limit is a wall. Retrying it
                # just burns the remaining attempts and hides the real reason for hours.
                raise GeminiDailyQuotaExhausted(
                    "Gemini free-tier daily request quota is exhausted. The run cannot "
                    "continue today; resume tomorrow or use a paid key."
                ) from exc
            time.sleep(_retry_delay(message))
    raise RuntimeError("unreachable")  # pragma: no cover


def _retry_delay(message: str, default: float = 20.0) -> float:
    """Seconds to wait, taken from the API's own ``retryDelay`` when it gives one."""
    match = re.search(r"'retryDelay':\s*'(\d+(?:\.\d+)?)s'", message)
    return float(match.group(1)) + 1.0 if match else default


# The offline, dependency-free default so tests and CI never need a network or a key.
DEFAULT_BACKEND = ollama_backend
