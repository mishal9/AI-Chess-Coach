"""Drilling from "you keep hanging material" into an actual example.

The dashboard states patterns; these pages have to show the evidence behind them. What
matters most here is that a game id can't be walked across players, and that the engine's
own refutation line is what gets surfaced — it is the closest thing to an explanation
available without an LLM.
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi", reason="needs the `api` extra")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import app  # noqa: E402
from memory.store import (  # noqa: E402
    connect,
    game_mistakes,
    game_row,
    ingest_game,
    list_games,
)
from tests.test_memory_store import move, pgn  # noqa: E402
from tests.test_memory_store import report as _base_report  # noqa: E402


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path / "memory.db"
    connect(path).close()
    monkeypatch.setenv("DB", str(path))
    return path


@pytest.fixture
def client():
    return TestClient(app)


def store_game(db, user="alice", moves="1. e4 e5 1-0", date="2026.03.01", report=None):
    conn = connect(db)
    game_id = ingest_game(conn, pgn(moves=moves, date=date), report or _base_report(), user)
    conn.close()
    return game_id


class TestStoreQueries:
    def test_list_games_is_newest_first(self, db):
        store_game(db, moves="1. e4 e5 a 1-0", date="2026.01.01")
        store_game(db, moves="1. d4 d5 b 1-0", date="2026.05.05")
        conn = connect(db)
        rows = list_games(conn, "alice")
        assert [r["played_at"][:10] for r in rows] == ["2026-05-05", "2026-01-01"]

    def test_list_games_counts_only_the_players_own_mistakes(self, db):
        store_game(db)
        conn = connect(db)
        row = list_games(conn, "alice")[0]
        # The fixture's black move is "good"; only white's blunder should count.
        assert row["total_mistakes"] == 1

    def test_game_row_is_scoped_to_the_player(self, db):
        game_id = store_game(db, user="alice")
        conn = connect(db)
        assert game_row(conn, game_id, "alice") is not None
        assert game_row(conn, game_id, "bob") is None

    def test_mistakes_come_back_in_played_order_with_their_motifs(self, db):
        game_id = store_game(db)
        conn = connect(db)
        mistakes = game_mistakes(conn, game_id)
        assert [m["ply"] for m in mistakes] == sorted(m["ply"] for m in mistakes)
        assert mistakes[0]["motifs"][0]["motif"] == "hangs_material"
        assert "engine line" in mistakes[0]["motifs"][0]["detail"]

    def test_a_clean_game_has_no_mistake_rows(self, db):
        clean = _base_report(moves=[move(quality="best"), move(ply=2, quality="good")])
        game_id = store_game(db, report=clean)
        assert game_mistakes(connect(db), game_id) == []


class TestGamesList:
    def test_lists_the_players_games(self, db, client):
        store_game(db, moves="1. e4 e5 a 1-0")
        store_game(db, moves="1. d4 d5 b 1-0")
        page = client.get("/player/alice/games").text
        assert page.count("/player/alice/game/") == 2

    def test_a_player_with_nothing_is_a_404(self, db, client):
        store_game(db, user="alice")
        assert client.get("/player/bob/games").status_code == 404

    def test_the_dashboard_links_to_it(self, db, client):
        store_game(db)
        assert "/player/alice/games" in client.get("/player/alice").text


class TestGameDetail:
    def test_shows_the_move_and_what_the_engine_preferred(self, db, client):
        game_id = store_game(db)
        page = client.get(f"/player/alice/game/{game_id}").text
        assert "Nxe5" in page      # the move played
        assert "d3" in page        # what the engine preferred

    def test_surfaces_the_engine_refutation_line(self, db, client):
        """The motif detail is the explanation, and it must reach the page."""
        game_id = store_game(db)
        page = client.get(f"/player/alice/game/{game_id}").text
        assert "punishes" in page
        assert "cp of material" in page

    def test_marks_the_costliest_move(self, db, client):
        game_id = store_game(db)
        assert "costliest" in client.get(f"/player/alice/game/{game_id}").text

    def test_a_game_id_cannot_be_walked_across_players(self, db, client):
        game_id = store_game(db, user="alice")
        store_game(db, user="bob", moves="1. c4 c5 1-0")
        assert client.get(f"/player/bob/game/{game_id}").status_code == 404

    def test_a_missing_game_is_a_404(self, db, client):
        store_game(db)
        assert client.get("/player/alice/game/9999").status_code == 404

    def test_a_clean_game_says_so_rather_than_showing_an_empty_table(self, db, client):
        clean = _base_report(moves=[move(quality="best"), move(ply=2, quality="good")])
        game_id = store_game(db, report=clean)
        page = client.get(f"/player/alice/game/{game_id}").text
        assert "played it cleanly" in page
