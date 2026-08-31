"""Generated coaching, and the job that produces it.

The model is injected throughout, so none of this needs Ollama. The point worth testing
is that coaching is stored *with the facts it was given* — that is what lets any stored
answer be re-scored for grounding later, and it is the fourth time this project has needed
an artifact to record enough to be checkable.
"""

from __future__ import annotations

import chess.pgn
import pytest

from memory.coaching import count_for_user, latest, save
from memory.jobs import create_job, latest_job, read_job, run_coach
from memory.profile import build_profile
from memory.store import backfill_pgn, connect, ingest_game
from tests.test_coach_memory import report as _base_report  # adds the whole-game counts
from tests.test_memory_store import pgn


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "memory.db"
    connect(path).close()
    return path


def store_game(db, user="alice", moves="1. e4 e5 1-0", report=None):
    conn = connect(db)
    game_id = ingest_game(conn, pgn(moves=moves), report or _base_report(), user, depth=8)
    conn.close()
    return game_id


FACTS = "Your most costly moves (worst first):\n- 1.Nxe5?? (blunder): the engine preferred d3."


class TestCoachingStore:
    def test_round_trips_with_its_facts(self, db):
        game_id = store_game(db)
        conn = connect(db)
        save(conn, game_id, "white", "test-model", "You played Nxe5.", FACTS)
        row = latest(conn, game_id)
        assert row.text == "You played Nxe5."
        assert row.facts == FACTS
        assert row.model == "test-model"

    def test_stored_facts_make_it_scoreable_afterwards(self, db):
        """The whole reason for keeping the facts: grounding, computed later, for free."""
        game_id = store_game(db)
        conn = connect(db)
        save(conn, game_id, "white", "m", "Nxe5 was the error, not Qh5.", FACTS)
        result = latest(conn, game_id).grounding()
        assert "Nxe5" in result.cited
        assert result.hallucinated == {"Qh5"}

    def test_regenerating_keeps_the_old_answer(self, db):
        """Old rows survive so a prompt or model change can be compared, not erased."""
        game_id = store_game(db)
        conn = connect(db)
        save(conn, game_id, "white", "old", "first", FACTS)
        save(conn, game_id, "white", "new", "second", FACTS)
        assert latest(conn, game_id).text == "second"
        assert conn.execute("SELECT COUNT(*) FROM coaching").fetchone()[0] == 2

    def test_no_coaching_is_none_not_an_error(self, db):
        assert latest(connect(db), store_game(db)) is None

    def test_counts_per_user(self, db):
        game_id = store_game(db, user="alice")
        conn = connect(db)
        assert count_for_user(conn, "alice") == 0
        save(conn, game_id, "white", "m", "text", FACTS)
        assert count_for_user(conn, "alice") == 1
        assert count_for_user(conn, "bob") == 0


class TestProfileExclusion:
    def test_the_game_being_coached_is_left_out_of_its_own_history(self, db):
        """Otherwise 'the fourth time' would be counting the move under discussion."""
        conn = connect(db)
        ids = [store_game(db, moves=f"1. e4 e5 {i} 1-0") for i in range(3)]
        assert build_profile(conn, "alice").games == 3
        assert build_profile(conn, "alice", exclude_game_id=ids[0]).games == 2

    def test_excluding_drops_that_games_motif_occurrences_too(self, db):
        conn = connect(db)
        ids = [store_game(db, moves=f"1. e4 e5 {i} 1-0") for i in range(2)]
        full = build_profile(conn, "alice").motifs[0].occurrences
        trimmed = build_profile(conn, "alice", exclude_game_id=ids[0]).motifs[0].occurrences
        assert trimmed == full - 1


class TestPgnBackfill:
    def test_a_row_stored_without_its_pgn_can_be_healed(self, db):
        game_id = store_game(db)
        conn = connect(db)
        conn.execute("UPDATE games SET pgn = NULL WHERE id = ?", (game_id,))
        conn.commit()

        assert backfill_pgn(conn, pgn(moves="1. e4 e5 1-0")) is True
        assert conn.execute(
            "SELECT pgn FROM games WHERE id = ?", (game_id,)
        ).fetchone()["pgn"] is not None

    def test_backfill_never_overwrites_what_is_already_there(self, db):
        store_game(db)
        conn = connect(db)
        assert backfill_pgn(conn, pgn(moves="1. e4 e5 1-0")) is False


class TestRunCoach:
    def _fake_analyze(self, game):
        return _base_report()

    def test_generates_and_stores_coaching(self, db):
        game_id = store_game(db)
        conn = connect(db)
        job_id = create_job(conn, "alice", kind="coach", game_id=game_id)

        seen = {}
        def fake_chat(messages, model=None, **kw):
            seen["messages"] = messages
            seen["model"] = model
            return "You hung a knight with Nxe5."

        run_coach(db, "alice", job_id, game_id, model="test-model",
                  chat_fn=fake_chat, analyze_fn=self._fake_analyze)

        assert read_job(conn, job_id).status == "done"
        row = latest(conn, game_id)
        assert row.text == "You hung a knight with Nxe5."
        assert row.model == "test-model"
        assert seen["model"] == "test-model"

    def test_the_stored_facts_are_the_ones_the_model_was_sent(self, db):
        """If these drifted apart, every later grounding score would be against fiction."""
        game_id = store_game(db)
        conn = connect(db)
        job_id = create_job(conn, "alice", kind="coach", game_id=game_id)

        sent = {}
        def fake_chat(messages, model=None, **kw):
            sent["user_turn"] = messages[-1]["content"]
            return "coaching"

        run_coach(db, "alice", job_id, game_id, chat_fn=fake_chat,
                  analyze_fn=self._fake_analyze)
        assert latest(conn, game_id).facts in sent["user_turn"]

    def test_a_game_without_its_pgn_fails_with_a_fixable_message(self, db):
        game_id = store_game(db)
        conn = connect(db)
        conn.execute("UPDATE games SET pgn = NULL WHERE id = ?", (game_id,))
        conn.commit()
        job_id = create_job(conn, "alice", kind="coach", game_id=game_id)

        run_coach(db, "alice", job_id, game_id, chat_fn=lambda *a, **k: "x",
                  analyze_fn=self._fake_analyze)
        job = read_job(conn, job_id)
        assert job.status == "failed"
        assert "Sync again" in job.message

    def test_another_players_game_is_refused(self, db):
        game_id = store_game(db, user="alice")
        conn = connect(db)
        job_id = create_job(conn, "bob", kind="coach", game_id=game_id)
        run_coach(db, "bob", job_id, game_id, chat_fn=lambda *a, **k: "x",
                  analyze_fn=self._fake_analyze)
        assert read_job(conn, job_id).status == "failed"

    def test_a_model_failure_reaches_the_job_row(self, db):
        game_id = store_game(db)
        conn = connect(db)
        job_id = create_job(conn, "alice", kind="coach", game_id=game_id)

        def exploding_chat(messages, model=None, **kw):
            raise RuntimeError("ollama is not running")

        run_coach(db, "alice", job_id, game_id, chat_fn=exploding_chat,
                  analyze_fn=self._fake_analyze)
        job = read_job(conn, job_id)
        assert job.status == "failed"
        assert "ollama is not running" in job.message


class TestJobKinds:
    def test_a_sync_job_is_not_mistaken_for_a_coach_job(self, db):
        """They drive different spinners on different pages."""
        conn = connect(db)
        create_job(conn, "alice", kind="sync")
        create_job(conn, "alice", kind="coach", game_id=7)

        assert latest_job(conn, "alice", kind="sync").kind == "sync"
        assert latest_job(conn, "alice", kind="coach").game_id == 7
        assert latest_job(conn, "alice", kind="coach", game_id=99) is None

    def test_an_older_database_gains_the_new_columns(self, db):
        """The live database already had a jobs table without kind/game_id."""
        conn = connect(db)
        conn.executescript(
            "DROP TABLE IF EXISTS jobs;"
            "CREATE TABLE jobs (id INTEGER PRIMARY KEY, user_name TEXT NOT NULL,"
            " status TEXT NOT NULL CHECK (status IN ('running','done','failed')),"
            " total INTEGER NOT NULL DEFAULT 0, done INTEGER NOT NULL DEFAULT 0,"
            " added INTEGER NOT NULL DEFAULT 0, message TEXT NOT NULL DEFAULT '',"
            " started_at TEXT NOT NULL, updated_at TEXT NOT NULL);"
        )
        conn.commit()

        job_id = create_job(conn, "alice", kind="coach", game_id=3)  # triggers migration
        job = read_job(conn, job_id)
        assert job.kind == "coach"
        assert job.game_id == 3
