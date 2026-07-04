"""Tests for the pluggable judge backends.

Provider SDKs are imported lazily inside each backend, so these tests exercise the
provider-neutral plumbing (system/turns split, default wiring) without installing
`anthropic` or `google-genai` or hitting any network.
"""

from __future__ import annotations

from eval import backends


def test_split_system_separates_system_from_turns():
    messages = [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "U1"},
        {"role": "user", "content": "U2"},
    ]
    system, turns = backends._split_system(messages)
    assert system == "SYS"
    assert [t["content"] for t in turns] == ["U1", "U2"]
    assert all(t["role"] != "system" for t in turns)


def test_split_system_handles_no_system_message():
    system, turns = backends._split_system([{"role": "user", "content": "U"}])
    assert system is None
    assert len(turns) == 1


def test_default_backend_is_ollama():
    assert backends.DEFAULT_BACKEND is backends.ollama_backend


def test_ollama_backend_calls_local_client(monkeypatch):
    captured = {}

    def fake_chat(messages, model, temperature):
        captured["model"] = model
        captured["temperature"] = temperature
        return "ok"

    from coach import client

    monkeypatch.setattr(client, "chat", fake_chat)
    out = backends.ollama_backend([{"role": "user", "content": "hi"}], model="m")
    assert out == "ok"
    assert captured["model"] == "m"
    assert captured["temperature"] == 0.0  # deterministic grading
