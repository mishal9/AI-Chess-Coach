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

# Sensible default judge models per provider. Flagships, because grading reliability
# matters more than cost here (a judge call is a fraction of a cent) — see eval/README.md.
DEFAULT_ANTHROPIC_MODEL = "claude-opus-4-8"
DEFAULT_GEMINI_MODEL = "gemini-2.5-pro"


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

    Needs credentials (``ANTHROPIC_API_KEY`` or an ``ant auth login`` profile). Note the
    Opus/Sonnet models reject a ``temperature`` parameter, so we omit it and rely on the
    model default — fine for a small structured verdict. (Adaptive thinking would improve
    grading quality at extra token cost; left off here to keep judge cost predictable.)
    """
    import anthropic

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

    Needs ``GEMINI_API_KEY`` / ``GOOGLE_API_KEY``. Gemini accepts ``temperature`` (so we
    pin it to 0) and can enforce a JSON response server-side, which makes the verdict
    reliably parseable.
    """
    from google import genai

    system, turns = _split_system(messages)
    client = genai.Client()
    response = client.models.generate_content(
        model=model or DEFAULT_GEMINI_MODEL,
        contents="\n\n".join(m["content"] for m in turns),
        config=genai.types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.0,
            response_mime_type="application/json",
        ),
    )
    return response.text.strip()


# The offline, dependency-free default so tests and CI never need a network or a key.
DEFAULT_BACKEND = ollama_backend
