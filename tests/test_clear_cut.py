"""Tests for the clear-cut filter on position rows' facts blocks."""

from __future__ import annotations

import json

from tests.test_qc import GOOD, _record
from training import clear_cut
from training.qc import load_records

QUIET = """\
- After your move, your pieces under attack: pawn on d4 (attackers 1, defenders 1).
- Engine's best line after your move: 7...Nc6 8.Nf3 (takes their pawn) Qxa1; material at the end: you 33, opponent 35"""

REPLY_CAPTURES = """\
- After your move, your pieces under attack: pawn on d4 (attackers 1, defenders 1).
- Engine's best line after your move: 7...Qxa1 (takes your rook) 8.Kd1; material at the end: you 33, opponent 35"""

UNDEFENDED = """\
- After your move, your pieces under attack: rook on a1 (attackers 1, defenders 0), pawn on d4 (attackers 1, defenders 1).
- Engine's best line after your move: 7...Nc6 8.Nf3; material at the end: you 33, opponent 35"""


def test_quiet_position_is_not_clear_cut():
    # A capture later in the line, or one by the student, does not count.
    assert not clear_cut.is_clear_cut(QUIET)


def test_opponent_reply_captures():
    assert clear_cut.reply_captures(REPLY_CAPTURES)
    assert clear_cut.is_clear_cut(REPLY_CAPTURES)


def test_move_leaves_a_piece_undefended():
    assert clear_cut.left_undefended(UNDEFENDED)
    assert not clear_cut.reply_captures(UNDEFENDED)
    assert clear_cut.is_clear_cut(UNDEFENDED)


def test_undefended_before_the_move_does_not_count():
    facts = "- Your pieces under attack: rook on a1 (attackers 1, defenders 0).\n" + QUIET
    assert not clear_cut.is_clear_cut(facts)


def test_defenders_10_is_not_defenders_0():
    facts = QUIET.replace("defenders 1)", "defenders 10)")
    assert not clear_cut.left_undefended(facts)


def test_main_keeps_clear_cut_position_rows(tmp_path):
    rows = tmp_path / "rows.jsonl"
    recs = [_record(GOOD, move_number=1), _record(GOOD, move_number=2),
            _record(GOOD, move_number=3), _record(GOOD, kind="game", move_number=4)]
    recs[1].facts += "\n" + REPLY_CAPTURES
    recs[2].facts += "\n" + QUIET
    recs[3].facts += "\n" + REPLY_CAPTURES  # game rows are never kept
    rows.write_text("".join(json.dumps(r.to_dict()) + "\n" for r in recs), encoding="utf-8")
    out = tmp_path / "clear.jsonl"
    assert clear_cut.main([str(rows), "--out", str(out)]) == 0
    assert [r.source["move_number"] for r in load_records(out)] == [2]
