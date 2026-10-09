"""Tests for the teacher's board tools and the tool loop. No API calls."""

from __future__ import annotations

import json

from training import board_tools, teacher

# 1.e4 d5, White to move; the engine prefers exd5, the student played Nc3.
MOVE = {"fen_before": "rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
        "san": "Nc3", "best_san": "exd5"}


def _tools():
    return board_tools.BoardTools({}, "white", MOVE)


def test_piece_at_and_positions():
    t = _tools()
    assert t.piece_at("e4", "before_your_move") == "White pawn on e4"
    assert t.piece_at("c3", "after_your_move") == "White knight on c3"
    assert t.piece_at("e4", "after_preferred_move") == "e4 is empty"


def test_attackers_and_defenders_name_the_pieces():
    t = _tools()
    assert t.attackers_and_defenders("e4", "before_your_move") == (
        "White pawn on e4; attacked by: Black pawn on d5; defended by: none")
    assert t.attackers_and_defenders("e4", "after_your_move").endswith(
        "defended by: White knight on c3")


def test_reaches_reports_blockers():
    t = _tools()
    # The queen on d1 looks down the d-file at d5, but the d2 pawn is in the way.
    assert t.reaches("d1", "d5", "before_your_move") == (
        "no: the White queen on d1 is blocked by the White pawn on d2")
    assert t.reaches("c3", "e4", "after_your_move") == (
        "yes: the White knight on c3 defends the White pawn on e4")
    assert t.reaches("b1", "e4", "before_your_move").startswith("no: the White knight on b1")


def test_play_line_marks_captures_and_illegal_moves():
    t = _tools()
    assert t.play_line(["exd5", "Qxd5"], "before_your_move").startswith(
        "2.exd5 (takes their pawn) Qxd5 (takes your pawn); material at the end")
    assert t.play_line(["exd5", "Qxa1"], "before_your_move").startswith("Qxa1 is not legal")


def test_bad_calls_come_back_as_text_and_are_counted():
    t = _tools()
    assert t.run("piece_at", json.dumps({"square": "z9", "position": "before_your_move"})
                 ).startswith("error:")
    assert t.run("nope", "{}").startswith("error:")
    assert t.calls == 2


def test_tool_loop_runs_calls_then_returns_only_the_answer(monkeypatch):
    replies = [
        {"content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {
            "name": "reaches",
            "arguments": json.dumps({"from_square": "c3", "to_square": "e4",
                                     "position": "after_your_move"})}}]},
        {"content": "Your knight on c3 defends your pawn on e4."},
    ]
    sent = []

    def fake_post(body):
        sent.append(body)
        return replies[len(sent) - 1]

    monkeypatch.setattr(teacher, "_deepseek_post", fake_post)
    t = _tools()
    out = teacher.deepseek_tool_backend([{"role": "user", "content": "x"}], t)
    assert out == "Your knight on c3 defends your pawn on e4."
    assert t.calls == 1 and "tools" in sent[0]
    assert sent[0]["tool_choice"] == "required" and sent[1]["tool_choice"] == "auto"
    tool_msg = sent[1]["messages"][-1]
    assert tool_msg["role"] == "tool" and tool_msg["content"].startswith("yes:")


def test_tool_loop_withdraws_tools_after_the_round_limit(monkeypatch):
    call = {"content": "", "tool_calls": [{"id": "c", "type": "function", "function": {
        "name": "piece_at", "arguments": json.dumps({"square": "e4",
                                                    "position": "before_your_move"})}}]}
    sent = []

    def fake_post(body):
        sent.append(body)
        return {"content": "done"} if "tools" not in body else call

    monkeypatch.setattr(teacher, "_deepseek_post", fake_post)
    assert teacher.deepseek_tool_backend([{"role": "user", "content": "x"}], _tools()) == "done"
    assert len(sent) == teacher.DEEPSEEK_MAX_TOOL_ROUNDS + 1
