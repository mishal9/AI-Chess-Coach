"""Offline tests for the chess.com fetcher (network mocked, so they run in CI)."""

import pytest

from engine import fetch_data


class FakeResponse:
    def __init__(self, json_data):
        self._json = json_data

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


ARCHIVES = {
    "archives": [
        "https://api.chess.com/pub/player/bob/games/2024/01",
        "https://api.chess.com/pub/player/bob/games/2024/02",
    ]
}
# The API lists games within a month oldest-first.
JAN = {"games": [{"rules": "chess", "pgn": "PGN-J1"}, {"rules": "chess", "pgn": "PGN-J2"}]}
FEB = {
    "games": [
        {"rules": "chess", "pgn": "PGN-F1"},
        {"rules": "chess960", "pgn": "PGN-VARIANT"},  # must be skipped
        {"rules": "chess", "pgn": "PGN-F2"},
    ]
}


def _install_fake_api(monkeypatch, *, jan=JAN, feb=FEB, archives=ARCHIVES):
    calls = {"headers": []}

    def fake_get(url, headers=None, timeout=None, **kwargs):
        calls["headers"].append(headers)
        if url.endswith("/archives"):
            return FakeResponse(archives)
        if url.endswith("2024/01"):
            return FakeResponse(jan)
        if url.endswith("2024/02"):
            return FakeResponse(feb)
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(fetch_data.requests, "get", fake_get)
    return calls


def test_takes_last_n_newest_first(monkeypatch):
    _install_fake_api(monkeypatch)
    text = fetch_data.fetch_chesscom_games("bob", 3)

    games = [g.strip() for g in text.split("\n\n") if g.strip()]
    # Newest month first, newest game first, variant skipped:
    assert games == ["PGN-F2", "PGN-F1", "PGN-J2"]


def test_skips_variants(monkeypatch):
    _install_fake_api(monkeypatch)
    assert "PGN-VARIANT" not in fetch_data.fetch_chesscom_games("bob", 10)


def test_stops_within_first_month_when_enough(monkeypatch):
    _install_fake_api(monkeypatch)
    # only the single newest game
    assert fetch_data.fetch_chesscom_games("bob", 1).strip() == "PGN-F2"


def test_sends_user_agent(monkeypatch):
    calls = _install_fake_api(monkeypatch)
    fetch_data.fetch_chesscom_games("bob", 1)
    assert all(h and "User-Agent" in h for h in calls["headers"])


def test_raises_when_no_standard_games(monkeypatch):
    only_variants = {"games": [{"rules": "chess960", "pgn": "X"}]}
    _install_fake_api(monkeypatch, jan=only_variants, feb=only_variants)
    with pytest.raises(RuntimeError, match="No standard chess games"):
        fetch_data.fetch_chesscom_games("bob", 5)


def test_cli_requires_user_for_chesscom(monkeypatch, tmp_path):
    monkeypatch.setattr(fetch_data, "DATA_DIR", tmp_path)
    with pytest.raises(SystemExit):  # argparse error → SystemExit(2)
        fetch_data.main(["--source", "chesscom"])
