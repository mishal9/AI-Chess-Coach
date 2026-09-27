"""One Stockfish depth for all research analysis, and old reports re-checked at theirs.

Facts blocks change with depth. Training at one depth and scoring at another, or
re-judging a stored report against facts rebuilt at a different depth, would silently
compare a coach against facts it never saw. These tests pin the defaults so a script
cannot drift away from the shared constant.
"""

from __future__ import annotations

import json

import pytest

from engine.analyzer import DEFAULT_DEPTH
from eval import expand_heldout, human_rating, recheck, rejudge
from eval import run as eval_run
from memory.store import SYNC_DEPTH
from training import distill, n2_eval


def test_research_depth_is_18():
    assert DEFAULT_DEPTH == 18


def test_the_app_analyzes_at_15():
    assert SYNC_DEPTH == 15


@pytest.mark.parametrize("module", [eval_run, expand_heldout, n2_eval, distill])
def test_research_scripts_default_to_the_shared_depth(module):
    assert module.build_parser().get_default("depth") == DEFAULT_DEPTH


@pytest.mark.parametrize("module", [recheck, rejudge, human_rating])
def test_tools_that_reread_a_report_take_its_depth_by_default(module):
    assert module.build_parser().get_default("depth") is None


def test_report_depth_uses_the_stored_depth():
    assert recheck.report_depth({"depth": 15}) == 15


def test_report_depth_needs_an_override_when_nothing_is_stored():
    with pytest.raises(ValueError, match="does not record"):
        recheck.report_depth({})
    assert recheck.report_depth({}, 15) == 15


def test_report_depth_refuses_an_override_that_contradicts_the_report():
    with pytest.raises(ValueError, match="depth 15, not 18"):
        recheck.report_depth({"depth": 15}, 18)


def test_recheck_refuses_reports_run_at_different_depths(tmp_path, capsys):
    paths = []
    for name, depth in (("a", 15), ("b", 18)):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps({"depth": depth, "games": []}))
        paths.append(str(path))
    assert recheck.main(paths) == 1
    assert "different depths" in capsys.readouterr().err


def test_distilled_rows_record_their_depth():
    from tests.test_coach import SAMPLE_REPORT
    from tests.test_distill import _source

    rec = distill.build_record(_source(), SAMPLE_REPORT, lambda r, s: "ok",
                               {"backend": "fake", "model": "m"}, depth=18)
    assert rec.source["depth"] == 18
    assert rec.to_dict()["source"]["depth"] == 18
