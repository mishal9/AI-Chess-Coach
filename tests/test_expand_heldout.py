"""Tests for the held-out expansion / curation tool.

Classification is a pure function of an analyzed report, and fetch + analysis are injected,
so bucketing, top-up selection, and manifest writing are validated with no engine or network.
"""

from __future__ import annotations

import json

import pytest

from eval import expand_heldout as ex
from training import corpus


@pytest.fixture(autouse=True)
def _no_real_pacing_delay(monkeypatch):
    """Same fixture as tests/test_training_corpus.py: fake fetchers hit no real API, so
    the inter-user pacing delay (shared with training.corpus) would only slow the suite
    down for nothing."""
    monkeypatch.setattr(corpus, "FETCH_PACING_SECONDS", 0)


def make_report(acpl_white, acpl_black, white_q=(), black_q=(), result="*"):
    moves = [{"side": "white", "quality": q} for q in white_q]
    moves += [{"side": "black", "quality": q} for q in black_q]
    return {
        "summary": {"acpl_white": acpl_white, "acpl_black": acpl_black},
        "moves": moves,
        "result": result,
    }


# --- classify ----------------------------------------------------------------------

def test_classify_each_bucket():
    # worse side is white in all of these (higher ACPL)
    assert ex.classify(make_report(80, 20, white_q=("blunder", "blunder"))) == ("multi_blunder", "white")
    assert ex.classify(make_report(60, 20, white_q=("blunder", "inaccuracy"))) == ("one_blunder", "white")
    assert ex.classify(make_report(50, 20, white_q=("mistake", "mistake"))) == ("two_mistakes", "white")
    assert ex.classify(make_report(40, 20, white_q=("inaccuracy", "inaccuracy", "inaccuracy"))) == ("inaccuracies", "white")
    assert ex.classify(make_report(50, 20, result="0-1")) == ("slow_loss", "white")   # lost, high ACPL, no flags
    assert ex.classify(make_report(15, 10, result="1/2-1/2")) == ("clean_draw", "white")
    # clean_draw tolerates a single trivial inaccuracy (no blunder/mistake, low ACPL, not lost)
    assert ex.classify(make_report(18, 10, white_q=("inaccuracy",), result="1/2-1/2")) == ("clean_draw", "white")


def test_classify_severity_precedence():
    # a blunder AND inaccuracies -> a blunder bucket, not 'inaccuracies'
    r = make_report(70, 20, white_q=("blunder", "inaccuracy", "inaccuracy"))
    assert ex.classify(r)[0] == "one_blunder"


def test_classify_returns_none_in_the_gap():
    # no flags, ACPL between CLEAN and SLOW_LOSS, not lost -> fits no bucket
    assert ex.classify(make_report(30, 20, result="1/2-1/2")) is None
    # no flags, high ACPL but NOT lost -> not slow_loss (that bucket requires a loss)
    assert ex.classify(make_report(50, 20, result="1/2-1/2")) is None


def test_mistake_profile_counts_only_coached_side():
    r = make_report(60, 60, white_q=("blunder",), black_q=("mistake", "mistake"))
    p = ex.mistake_profile(r, "black")
    assert (p["blunders"], p["mistakes"], p["inaccuracies"]) == (0, 2, 0)
    assert p["acpl"] == 60


# --- existing_counts ---------------------------------------------------------------

def test_existing_counts_infers_bucket_from_filename_and_field():
    manifest = [
        {"pgn": "one_blunder.pgn", "game_index": 0, "coached_side": "white"},   # original: infer
        {"pgn": "one_blunder.pgn", "game_index": 1, "coached_side": "black",
         "bucket": "one_blunder"},                                              # new: explicit
        {"pgn": "clean_draw.pgn", "game_index": 0, "coached_side": "white"},
    ]
    counts = ex.existing_counts(manifest)
    assert counts["one_blunder"] == 2
    assert counts["clean_draw"] == 1
    assert counts["multi_blunder"] == 0


# --- select ------------------------------------------------------------------------

def _pgn(moves: str) -> str:
    slug = moves[:8].replace(" ", "")
    return (f'[Event "x"]\n[Site "https://lichess.org/{slug}"]\n'
            f'[White "Alice"]\n[Black "Bob"]\n\n{moves} 1-0')


def test_select_tops_up_to_target_and_respects_existing():
    candidates = [
        (_pgn("1. e4 e5 blunderA"), make_report(70, 20, white_q=("blunder",))),
        (_pgn("1. d4 d5 blunderB"), make_report(70, 20, white_q=("blunder",))),
        (_pgn("1. c4 c5 blunderC"), make_report(70, 20, white_q=("blunder",))),
    ]
    counts = {b: 0 for b in ex.BUCKETS}
    counts["one_blunder"] = 1  # already have one
    picked = ex.select(candidates, counts, per_bucket=2)
    assert len(picked["one_blunder"]) == 1  # topped 1 -> 2, stopped


def test_select_dedups_within_pool():
    dup = (_pgn("1. e4 e5 samegame"), make_report(70, 20, white_q=("blunder",)))
    picked = ex.select([dup, dup], {b: 0 for b in ex.BUCKETS}, per_bucket=5)
    assert len(picked["one_blunder"]) == 1


def test_select_skips_unclassifiable():
    cand = [(_pgn("1. e4 e5 quiet"), make_report(30, 20, result="1/2-1/2"))]  # in the gap
    picked = ex.select(cand, {b: 0 for b in ex.BUCKETS}, per_bucket=5)
    assert all(len(v) == 0 for v in picked.values())


# --- append_to_bucket_file ---------------------------------------------------------

def test_append_preserves_originals_and_returns_index(tmp_path):
    (tmp_path / "one_blunder.pgn").write_text('[Event "orig"]\n\n1. e4 e5 1-0\n')
    start = ex.append_to_bucket_file(tmp_path, "one_blunder", ['[Event "new"]\n\n1. d4 d5 0-1'])
    assert start == 1  # appended after the one original game
    games = ex.corpus.split_pgn((tmp_path / "one_blunder.pgn").read_text())
    assert len(games) == 2
    assert "orig" in games[0]


# --- main (fetch + analysis injected, HELDOUT_DIR redirected) ----------------------

def test_main_writes_games_and_extends_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(ex, "HELDOUT_DIR", tmp_path)
    (tmp_path / "manifest.json").write_text("[]")

    g_blunder = _pgn("1. e4 e5 2. Nf3 blunder")
    g_clean = _pgn("1. d4 Nf6 2. c4 clean")
    reports = {
        g_blunder: make_report(70, 20, white_q=("blunder",)),
        g_clean: make_report(15, 10, result="1/2-1/2"),
    }

    rc = ex.main(
        ["--per-bucket", "5"],
        fetch_fn=lambda user, mx: g_blunder + "\n\n" + g_clean,
        analyze_fn=lambda pgn: reports[pgn],
    )
    assert rc == 0

    manifest = json.loads((tmp_path / "manifest.json").read_text())
    buckets = sorted(e["bucket"] for e in manifest)
    assert buckets == ["clean_draw", "one_blunder"]
    assert (tmp_path / "one_blunder.pgn").exists()
    assert (tmp_path / "clean_draw.pgn").exists()
    # every new entry carries the fields eval.run and per-bucket analysis need
    for e in manifest:
        assert e["coached_side"] in ("white", "black")
        assert e["white"] and "note" in e


def test_main_paces_between_users(tmp_path, monkeypatch):
    monkeypatch.setattr(ex, "HELDOUT_DIR", tmp_path)
    (tmp_path / "manifest.json").write_text("[]")
    monkeypatch.setattr(corpus, "FETCH_PACING_SECONDS", 4.0)
    slept = []
    monkeypatch.setattr(corpus.time, "sleep", lambda s: slept.append(s))

    ex.main(
        ["--per-bucket", "1"],  # default roster: corpus.DEFAULT_USERS, 5 users
        fetch_fn=lambda user, mx: "",
        analyze_fn=lambda pgn: make_report(15, 10, result="1/2-1/2"),
    )
    assert slept == [4.0] * (len(corpus.DEFAULT_USERS) - 1)


def test_main_logs_progress_for_every_candidate_not_only_failures(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ex, "HELDOUT_DIR", tmp_path)
    (tmp_path / "manifest.json").write_text("[]")

    g_ok = _pgn("1. e4 e5 2. Nf3 ok")
    g_bad = _pgn("1. d4 d5 2. c4 bad")

    def analyze(pgn: str) -> dict:
        if pgn == g_bad:
            raise ValueError("boom")
        return make_report(15, 10, result="1/2-1/2")

    ex.main(["--per-bucket", "1", "--user", "someone"],
            fetch_fn=lambda user, mx: g_ok + "\n\n" + g_bad, analyze_fn=analyze)

    err = capsys.readouterr().err
    # every candidate gets a "[i/N] <identity>" line before it's attempted, win or lose —
    # not just the ones that fail, which is all the old logging ever showed.
    assert f"[1/2] {ex.corpus.game_key(g_ok)}" in err
    assert f"[2/2] {ex.corpus.game_key(g_bad)}" in err
    assert "[2/2] skipped (boom)" in err


def test_lichess_fetch_perf_passes_perf_type(monkeypatch):
    captured = {}

    def fake_fetch(user, max_games, perf_type=None):
        captured["perf_type"] = perf_type
        return '[Event "x"]\n\n1. e4 e5 1-0\n'

    monkeypatch.setattr("engine.fetch_data.fetch_lichess_games", fake_fetch)
    text = ex._lichess_fetch_perf("rapid,classical")("someone", 5)
    assert captured["perf_type"] == "rapid,classical"
    assert "[Event" in text


def test_main_dry_run_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(ex, "HELDOUT_DIR", tmp_path)
    (tmp_path / "manifest.json").write_text("[]")
    g = _pgn("1. e4 e5 blunder")
    rc = ex.main(
        ["--dry-run"],
        fetch_fn=lambda u, m: g,
        analyze_fn=lambda pgn: make_report(70, 20, white_q=("blunder",)),
    )
    assert rc == 0
    assert json.loads((tmp_path / "manifest.json").read_text()) == []  # untouched


# --- relabel -----------------------------------------------------------------------

def test_relabel_changes_only_the_label_and_keeps_the_old_one():
    entry = {"pgn": "slow_loss.pgn", "game_index": 3, "coached_side": "black", "note": "n"}
    report = make_report(20, 40, black_q=("inaccuracy", "inaccuracy"), result="1-0")
    new = ex.relabel_entry(entry, report, 18)
    assert new["bucket"] == "inaccuracies"
    assert new["bucket_previous"] == "slow_loss"
    assert new["bucket_depth"] == 18
    assert {k: new[k] for k in entry} == entry   # file, index, side and note untouched


def test_relabel_marks_a_game_that_fits_no_bucket_as_unsorted():
    entry = {"pgn": "clean_draw.pgn", "game_index": 0, "coached_side": "white",
             "bucket": "clean_draw"}
    new = ex.relabel_entry(entry, make_report(30, 20, result="1/2-1/2"), 18)
    assert new["bucket"] == ex.UNSORTED
    assert new["bucket_previous"] == "clean_draw"


def test_relabel_keeps_no_previous_label_when_nothing_changes():
    entry = {"pgn": "one_blunder.pgn", "game_index": 0, "coached_side": "white"}
    new = ex.relabel_entry(entry, make_report(60, 20, white_q=("blunder",)), 18)
    assert new["bucket"] == "one_blunder"
    assert "bucket_previous" not in new


def test_relabel_keeps_the_first_previous_label_across_reruns():
    entry = {"pgn": "slow_loss.pgn", "game_index": 0, "coached_side": "white",
             "bucket": "inaccuracies", "bucket_previous": "slow_loss"}
    report = make_report(40, 20, white_q=("mistake",))
    assert ex.relabel_entry(entry, report, 20)["bucket_previous"] == "slow_loss"


def test_main_relabel_rewrites_labels_without_moving_games(tmp_path, monkeypatch):
    monkeypatch.setattr(ex, "HELDOUT_DIR", tmp_path)
    games = [_pgn("1. e4 e5 2. Nf3 first"), _pgn("1. d4 d5 2. c4 second")]
    (tmp_path / "slow_loss.pgn").write_text("\n\n".join(games) + "\n")
    manifest = [{"pgn": "slow_loss.pgn", "game_index": i, "coached_side": "white"}
                for i in range(2)]
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    before = (tmp_path / "slow_loss.pgn").read_text()

    reports = {games[0]: make_report(50, 20, result="0-1"),
               games[1]: make_report(50, 20, white_q=("mistake",), result="0-1")}
    rc = ex.main(["--relabel", "--depth", "18"], fetch_fn=lambda u, n: "",
                 analyze_fn=lambda pgn: reports[pgn.strip()])
    assert rc == 0
    out = json.loads((tmp_path / "manifest.json").read_text())
    assert [e["bucket"] for e in out] == ["slow_loss", "two_mistakes"]
    assert (tmp_path / "slow_loss.pgn").read_text() == before
