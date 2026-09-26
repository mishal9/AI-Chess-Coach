"""The analysis cache returns a saved report only when nothing that shapes it has changed."""

from __future__ import annotations

import io

import chess.pgn
import pytest

from engine import cache

PGN = '[White "a"]\n[Black "b"]\n[Result "1-0"]\n\n1. e4 e5 2. Qh5 Nc6 3. Bc4 Nf6 4. Qxf7# 1-0\n'


def _game(pgn: str = PGN) -> chess.pgn.Game:
    return chess.pgn.read_game(io.StringIO(pgn))


class CountingAnalyzer:
    def __init__(self):
        self.calls = 0

    def __call__(self, game, depth):
        self.calls += 1
        return {"depth_seen": depth, "call": self.calls}


def _run(tmp_path, game=None, depth=18, engine_id="Stockfish 17", analyze=None):
    return cache.analyze_cached(game or _game(), depth, cache_dir=tmp_path,
                                analyze=analyze, engine_id=engine_id)


def test_a_second_request_is_served_from_disk(tmp_path):
    analyze = CountingAnalyzer()
    first = _run(tmp_path, analyze=analyze)
    second = _run(tmp_path, analyze=analyze)
    assert analyze.calls == 1
    assert first == second
    assert len(list((tmp_path / "18").glob("*.json"))) == 1


@pytest.mark.parametrize("change", [
    {"depth": 15},
    {"engine_id": "Stockfish 16"},
    {"game": _game(PGN.replace("Nf6", "d6"))},
    {"game": _game(PGN.replace('[White "a"]', '[White "c"]'))},
])
def test_anything_that_shapes_the_report_misses_the_cache(tmp_path, change):
    analyze = CountingAnalyzer()
    _run(tmp_path, analyze=analyze)
    _run(tmp_path, analyze=analyze, **change)
    assert analyze.calls == 2


def test_a_change_to_the_analyzer_code_misses_the_cache():
    key = cache.cache_key(_game(), 18, "Stockfish 17", "code-a")
    assert key != cache.cache_key(_game(), 18, "Stockfish 17", "code-b")


def test_the_cache_can_be_switched_off(tmp_path, monkeypatch):
    monkeypatch.setenv("ANALYSIS_CACHE", "off")
    analyze = CountingAnalyzer()
    _run(tmp_path, analyze=analyze)
    _run(tmp_path, analyze=analyze)
    assert analyze.calls == 2
    assert not tmp_path.joinpath("18").exists()


def test_a_failed_analysis_leaves_no_file(tmp_path):
    def broken(game, depth):
        raise RuntimeError("engine died")

    with pytest.raises(RuntimeError):
        _run(tmp_path, analyze=broken)
    assert not list(tmp_path.rglob("*.json"))
