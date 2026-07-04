"""Tests for the pluggable judge backends.

Provider SDKs are imported lazily inside each backend, so these tests exercise the
provider-neutral plumbing (system/turns split, default wiring) without installing
`anthropic` or `google-genai` or hitting any network.
"""

from __future__ import annotations

import os

import pytest

from eval import backends


def _dotenv_available() -> bool:
    try:
        import dotenv  # noqa: F401

        return True
    except ModuleNotFoundError:
        return False


requires_dotenv = pytest.mark.skipif(
    not _dotenv_available(), reason="python-dotenv not installed (eval extra)"
)


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


def test_load_dotenv_is_safe_without_package():
    # CI installs neither python-dotenv nor a key — .env loading must be a no-op, not a
    # crash, so the frontier backends still degrade to reading real env vars.
    backends._load_dotenv()  # should not raise


@requires_dotenv
def test_load_dotenv_reads_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("CHESS_EVAL_TEST_KEY=from-dotenv\n")
    monkeypatch.delenv("CHESS_EVAL_TEST_KEY", raising=False)
    try:
        backends._load_dotenv(path=str(env_file))
        assert os.environ.get("CHESS_EVAL_TEST_KEY") == "from-dotenv"
    finally:
        os.environ.pop("CHESS_EVAL_TEST_KEY", None)


@requires_dotenv
def test_shell_env_takes_precedence_over_dotenv(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("CHESS_EVAL_TEST_KEY=from-dotenv\n")
    monkeypatch.setenv("CHESS_EVAL_TEST_KEY", "from-shell")
    backends._load_dotenv(path=str(env_file))
    assert os.environ["CHESS_EVAL_TEST_KEY"] == "from-shell"  # override=False
