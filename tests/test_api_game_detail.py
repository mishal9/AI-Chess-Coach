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


class TestCoachEndpoint:
    def _save_coaching(self, db, game_id, text, facts):
        from memory.coaching import save
        conn = connect(db)
        save(conn, game_id, "white", "test-model", text, facts, used_profile=True)
        conn.close()

    def test_offers_to_coach_a_game_that_has_none(self, db, client):
        game_id = store_game(db)
        assert "Coach this game" in client.get(f"/player/alice/game/{game_id}").text

    def test_shows_stored_coaching(self, db, client):
        game_id = store_game(db)
        self._save_coaching(db, game_id, "You hung a knight.", "facts with Nxe5")
        page = client.get(f"/player/alice/game/{game_id}").text
        assert "You hung a knight." in page
        assert "test-model" in page
        assert "with your history" in page

    def test_reports_when_every_cited_move_was_given_to_it(self, db, client):
        game_id = store_game(db)
        self._save_coaching(db, game_id, "Nxe5 was the error.", "the facts list Nxe5")
        page = client.get(f"/player/alice/game/{game_id}").text
        assert "all of them from the analysis it was given" in page

    def test_flags_moves_the_model_was_never_given(self, db, client):
        """The grounding check is only possible because the facts were stored with it."""
        game_id = store_game(db)
        self._save_coaching(db, game_id, "Nxe5 was bad, and so was Qh5.", "facts: Nxe5")
        page = client.get(f"/player/alice/game/{game_id}").text
        assert "not in the facts it was given" in page
        assert "Qh5" in page

    def test_starting_a_coach_run_redirects_back_to_the_game(self, db, client, monkeypatch):
        game_id = store_game(db)
        started = []
        monkeypatch.setattr(
            "api.app.start_coach", lambda path, user, gid, **kw: started.append(gid) or 1
        )
        response = client.post(
            f"/player/alice/game/{game_id}/coach", follow_redirects=False
        )
        assert response.status_code == 303
        assert response.headers["location"] == f"/player/alice/game/{game_id}"
        assert started == [game_id]

    def test_cannot_coach_another_players_game(self, db, client, monkeypatch):
        game_id = store_game(db, user="alice")
        started = []
        monkeypatch.setattr(
            "api.app.start_coach", lambda path, user, gid, **kw: started.append(gid) or 1
        )
        assert client.post(f"/player/bob/game/{game_id}/coach").status_code == 404
        assert started == []

    def test_a_second_run_is_refused_while_one_is_going(self, db, client, monkeypatch):
        from memory.jobs import create_job

        game_id = store_game(db)
        conn = connect(db)
        create_job(conn, "alice", kind="coach", game_id=game_id)
        conn.close()

        started = []
        monkeypatch.setattr(
            "api.app.start_coach", lambda path, user, gid, **kw: started.append(gid) or 1
        )
        client.post(f"/player/alice/game/{game_id}/coach")
        assert started == [], "the model takes tens of seconds; don't spend them twice"

    def test_the_page_polls_only_while_coaching_is_running(self, db, client):
        from memory.jobs import create_job, update_job

        game_id = store_game(db)
        conn = connect(db)
        job_id = create_job(conn, "alice", kind="coach", game_id=game_id)
        conn.close()
        assert 'http-equiv="refresh"' in client.get(f"/player/alice/game/{game_id}").text

        conn = connect(db)
        update_job(conn, job_id, status="done", message="Coaching ready.")
        conn.close()
        assert 'http-equiv="refresh"' not in client.get(f"/player/alice/game/{game_id}").text

    def test_a_sync_job_does_not_drive_the_coaching_spinner(self, db, client):
        """Different kinds, different pages — one must not spin the other."""
        from memory.jobs import create_job

        game_id = store_game(db)
        conn = connect(db)
        create_job(conn, "alice", kind="sync")
        conn.close()
        page = client.get(f"/player/alice/game/{game_id}").text
        assert "Thinking…" not in page
