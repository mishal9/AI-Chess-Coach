"""The read-only dashboard.

These check what the page *asserts to a human*, not how it is laid out. The one that
matters most is the trend: a difference inside normal variation must not be dressed up as
progress just because a web page has room for a green arrow.
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi", reason="needs the `api` extra")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import app  # noqa: E402
from memory.store import connect, ingest_game  # noqa: E402
from tests.test_memory_store import move, pgn  # noqa: E402
from tests.test_memory_store import report as _base_report  # noqa: E402
from tests.test_trend_noise import report_with  # noqa: E402


@pytest.fixture
def db(tmp_path, monkeypatch):
    """An empty memory database the app is pointed at."""
    path = tmp_path / "memory.db"
    connect(path).close()
    monkeypatch.setenv("DB", str(path))
    return path


@pytest.fixture
def client():
    return TestClient(app)


def store(db, counts, user="alice"):
    """Store one game per entry in ``counts``, each with that many flagged mistakes.

    Movetext is namespaced by user: identity is the movetext hash, so two players sharing
    a move sequence would (correctly) dedup into one stored game and quietly break the
    fixture rather than the code.
    """
    conn = connect(db)
    for i, mistakes in enumerate(counts):
        ingest_game(
            conn,
            pgn(moves=f"1. e4 e5 {user}{i} 1-0", date=f"2026.01.{i + 1:02d}"),
            report_with(mistakes),
            user,
        )
    conn.close()


def store_hangs(db, n, user="alice"):
    """Store ``n`` games that actually tag a motif (a hung knight in each)."""
    conn = connect(db)
    for i in range(n):
        ingest_game(
            conn,
            pgn(moves=f"1. e4 e5 hang{user}{i} 1-0", date=f"2026.02.{i + 1:02d}"),
            _base_report(),
            user,
        )
    conn.close()


class TestAvailability:
    def test_a_missing_database_explains_how_to_make_one(self, tmp_path, monkeypatch, client):
        monkeypatch.setenv("DB", str(tmp_path / "nope.db"))
        response = client.get("/")
        assert response.status_code == 503
        assert "python -m memory.store" in response.json()["detail"]

    def test_an_unknown_player_is_a_404(self, db, client):
        store(db, [1, 2])
        assert client.get("/player/stranger").status_code == 404

    def test_a_single_player_lands_straight_on_their_dashboard(self, db, client):
        store(db, [1, 2])
        response = client.get("/")
        assert response.status_code == 200
        assert "alice" in response.text
        assert "flagged mistakes" in response.text

    def test_several_players_get_a_chooser(self, db, client):
        store(db, [1, 2], user="alice")
        store(db, [3], user="bob")
        response = client.get("/")
        assert "Stored players" in response.text
        assert "/player/alice" in response.text
        assert "/player/bob" in response.text


class TestContent:
    def test_the_numbers_match_the_profile(self, db, client):
        store(db, [2, 3, 1])
        page = client.get("/player/alice").text
        assert "3 analyzed games" in page
        assert ">6<" in page  # 2 + 3 + 1 flagged mistakes

    def test_a_recurring_pattern_is_labelled_as_such(self, db, client):
        store_hangs(db, 3)
        page = client.get("/player/alice").text
        assert "leaving material hanging" in page
        # `>recurring<`, not `recurring` — the bare word also matches a CSS class name.
        assert ">recurring</span>" in page

    def test_a_one_off_is_not_called_recurring(self, db, client):
        store_hangs(db, 1)
        page = client.get("/player/alice").text
        assert ">seen once</span>" in page
        assert ">recurring</span>" not in page

    def test_a_player_with_no_tagged_motifs_is_told_plainly(self, db, client):
        conn = connect(db)
        quiet = _base_report(moves=[move(quality="inaccuracy", cp_loss=40)])
        ingest_game(conn, pgn(), quiet, "alice")
        conn.close()
        page = client.get("/player/alice").text
        assert "No tactical pattern has been tagged yet" in page

    def test_the_window_narrows_the_report(self, db, client):
        store(db, [1] * 10)
        assert "10 analyzed games" in client.get("/player/alice").text
        narrowed = client.get("/player/alice?last=4").text
        assert "4 analyzed games" in narrowed
        assert "most recent 4 of 10" in narrowed


class TestTrendHonesty:
    def test_noise_is_reported_as_too_close_to_call(self, db, client):
        store(db, [1, 3, 4, 1, 5, 1, 0] + [1, 1, 4, 3, 3, 1, 5])
        page = client.get("/player/alice").text
        assert "Too close to call" in page
        assert "shows neither improvement nor decline" in page

    def test_noise_is_never_dressed_up_as_progress(self, db, client):
        store(db, [1, 3, 4, 1, 5, 1, 0] + [1, 1, 4, 3, 3, 1, 5])
        page = client.get("/player/alice").text
        assert "Moving in the right direction" not in page
        assert "Slipping" not in page

    def test_a_real_improvement_is_named(self, db, client):
        store(db, [5, 6, 5, 6, 5, 6] + [0, 1, 0, 1, 0, 1])
        page = client.get("/player/alice").text
        assert "Moving in the right direction" in page

    def test_a_real_decline_is_named(self, db, client):
        store(db, [0, 1, 0, 1, 0, 1] + [5, 6, 5, 6, 5, 6])
        assert "Slipping" in client.get("/player/alice").text

    def test_too_few_games_shows_no_trend_section_at_all(self, db, client):
        store(db, [1, 2])
        assert "Are you improving?" not in client.get("/player/alice").text
