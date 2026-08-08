"""Tests for the Phase-2 coaching layer.

The prompt-construction tests are pure and deterministic (no engine, no model). The
client tests mock the Ollama transport. A single live smoke test actually calls the
local model and is skipped automatically when Ollama or the model isn't available
(e.g. in CI), so the suite stays green without a GPU or a running server.
"""

from __future__ import annotations

import pytest

from coach import client, prompts

# A hand-built report dict shaped exactly like GameReport.to_dict(). Black plays clearly
# worse than White and has the single worst move (17...Nxd4), so it's the side to coach.
SAMPLE_REPORT = {
    "white": "Alice",
    "black": "Bob",
    "result": "1-0",
    "eco": "C41",
    "opening": "Philidor Defense",
    "summary": {
        "blunders": 1,
        "mistakes": 1,
        "inaccuracies": 1,
        "acpl_white": 22.0,
        "acpl_black": 88.0,
        "worst_move": {
            "move_number": 17,
            "side": "black",
            "played": "Nxd4",
            "best": "Qe7",
            "cp_loss": 540,
            "win_prob_loss": 0.62,
        },
    },
    "moves": [
        {
            "ply": 33, "move_number": 17, "side": "black", "san": "Nxd4",
            "best_san": "Qe7", "eval_before": 40, "eval_after": 580,
            "cp_loss": 540, "win_prob_loss": 0.62, "quality": "blunder",
            "fen_before": "8/8/8/8/8/8/8/8 b - - 0 17",
        },
        {
            "ply": 23, "move_number": 12, "side": "black", "san": "h6",
            "best_san": "Be7", "eval_before": 10, "eval_after": 150,
            "cp_loss": 140, "win_prob_loss": 0.18, "quality": "mistake",
            "fen_before": "8/8/8/8/8/8/8/8 b - - 0 12",
        },
        {
            "ply": 15, "move_number": 8, "side": "white", "san": "a3",
            "best_san": "O-O", "eval_before": 30, "eval_after": -20,
            "cp_loss": 50, "win_prob_loss": 0.09, "quality": "inaccuracy",
            "fen_before": "8/8/8/8/8/8/8/8 w - - 0 8",
        },
    ],
}


def test_choose_coached_side_prefers_worse_player():
    # Black's ACPL (88) is far worse than White's (22), so Black is coached.
    assert prompts.choose_coached_side(SAMPLE_REPORT) == "black"


def test_choose_coached_side_tie_breaks_to_loser():
    report = {
        "result": "0-1",
        "summary": {"acpl_white": 50.0, "acpl_black": 50.0},
    }
    assert prompts.choose_coached_side(report) == "white"


def test_facts_block_mentions_key_facts():
    facts = prompts.format_report_facts(SAMPLE_REPORT, "black")
    # Grounds the model in the concrete worst move and its recommended replacement.
    assert "17...Nxd4" in facts
    assert "Qe7" in facts
    assert "Philidor" in facts
    assert "BLACK" in facts
    # The coached side's ACPL is surfaced.
    assert "88" in facts


def test_facts_block_excludes_opponent_mistakes():
    # Coaching Black: White's 8.a3 inaccuracy must not appear in the "your mistakes" list.
    facts = prompts.format_report_facts(SAMPLE_REPORT, "black")
    assert "a3" not in facts


def test_facts_block_respects_max_mistakes():
    facts = prompts.format_report_facts(SAMPLE_REPORT, "black", max_mistakes=1)
    assert "17...Nxd4" in facts   # worst kept
    assert "12...h6" not in facts  # trimmed


def test_clean_game_when_no_mistakes_and_low_acpl():
    # No flagged moves and a low ACPL -> genuinely clean.
    report = {
        **SAMPLE_REPORT,
        "moves": [],
        "summary": {**SAMPLE_REPORT["summary"], "acpl_white": 12.0},
    }
    facts = prompts.format_report_facts(report, "white")
    assert "clean game" in facts.lower()


def test_no_flagged_but_high_acpl_says_ground_down():
    # No flagged moves but a high ACPL (Opera-Game situation) must NOT be called clean.
    report = {
        **SAMPLE_REPORT,
        "moves": [],
        "summary": {**SAMPLE_REPORT["summary"], "acpl_black": 79.8},
    }
    facts = prompts.format_report_facts(report, "black")
    assert "clean game" not in facts.lower()
    assert "gradually" in facts.lower()


def test_build_messages_structure():
    messages = prompts.build_messages(SAMPLE_REPORT, "black")
    assert [m["role"] for m in messages] == ["system", "user"]
    assert "chess coach" in messages[0]["content"].lower()
    assert "17...Nxd4" in messages[1]["content"]


def test_build_messages_rejects_bad_side():
    with pytest.raises(ValueError):
        prompts.build_messages(SAMPLE_REPORT, "green")


def test_client_chat_passes_model_and_returns_text(monkeypatch):
    captured = {}

    def fake_chat(model, messages, options):
        captured["model"] = model
        captured["options"] = options
        return {"message": {"content": "  Nice game, but watch that knight.  "}}

    monkeypatch.setattr(client.ollama, "chat", fake_chat)
    out = client.chat([{"role": "user", "content": "hi"}], model="m", temperature=0.7)
    assert out == "Nice game, but watch that knight."   # stripped
    assert captured["model"] == "m"
    assert captured["options"]["temperature"] == 0.7


def test_client_strips_leading_think_block(monkeypatch):
    def fake_chat(model, messages, options):
        return {
            "message": {
                "content": "<think>\nLet me check the facts block.\n</think>\n\n"
                "12...Qxb2 dropped your queen to the pin."
            }
        }

    monkeypatch.setattr(client.ollama, "chat", fake_chat)
    out = client.chat([{"role": "user", "content": "hi"}])
    assert out == "12...Qxb2 dropped your queen to the pin."


def test_client_keeps_think_mentions_mid_text(monkeypatch):
    def fake_chat(model, messages, options):
        return {"message": {"content": "Think before you trade: <think> is not stripped here."}}

    monkeypatch.setattr(client.ollama, "chat", fake_chat)
    out = client.chat([{"role": "user", "content": "hi"}])
    assert out.startswith("Think before you trade")


def test_client_missing_model_raises_coach_error(monkeypatch):
    def fake_chat(model, messages, options):
        raise client.ollama.ResponseError("model 'x' not found")

    monkeypatch.setattr(client.ollama, "chat", fake_chat)
    with pytest.raises(client.CoachModelError, match="[Pp]ull it"):
        client.chat([{"role": "user", "content": "hi"}])


# --- Live smoke test (skipped when the local model isn't reachable) -----------------

def _model_available() -> bool:
    try:
        import ollama

        tags = ollama.list()
        names = {m.get("model", m.get("name", "")) for m in tags.get("models", [])}
        return any(client.DEFAULT_MODEL.split(":")[0] in n for n in names)
    except Exception:
        return False


requires_model = pytest.mark.skipif(
    not _model_available(), reason="Ollama model not available locally"
)


@requires_model
def test_live_coaching_is_grounded():
    messages = prompts.build_messages(SAMPLE_REPORT, "black")
    text = client.chat(messages)
    assert len(text) > 80  # a real paragraph, not an empty/emoji reply
