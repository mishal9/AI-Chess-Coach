"""Background sync jobs.

Both the fetch and the analysis are injectable, so the whole loop runs here with no
network and no Stockfish. What is being checked is the bookkeeping a web page depends on:
that progress is visible while work happens, that failure is reported rather than
swallowed, and that a job which stopped reporting is not shown as still working.
"""

from __future__ import annotations

import chess.pgn
import pytest

from memory.jobs import (
    STALE_AFTER,
    USERNAME_RE,
    active_job,
    create_job,
    latest_job,
    read_job,
    run_sync,
    update_job,
)
from memory.store import connect, stats
from tests.test_memory_store import pgn
from tests.test_memory_store import report as _base_report


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "memory.db"
    connect(path).close()
    return path


def fake_fetch(games: list[str]):
    """A fetcher that returns a fixed multi-game PGN blob."""
    def fetch(user, max_games):
        return "\n\n".join(games[:max_games])
    return fetch


def fake_analyze(game: chess.pgn.Game) -> dict:
    return _base_report()


class TestUsernameValidation:
    @pytest.mark.parametrize("name", ["mshah509", "abc", "a-b_c", "A" * 25])
    def test_accepts_real_handles(self, name):
        assert USERNAME_RE.match(name)

    @pytest.mark.parametrize(
        "name", ["ab", "A" * 26, "has space", "../etc/passwd", "semi;colon", ""]
    )
    def test_rejects_anything_that_could_not_be_one(self, name):
        """The name goes into an API URL, so a bad one must fail here, not out there."""
        assert not USERNAME_RE.match(name)


class TestRunSync:
    def test_stores_the_fetched_games_and_finishes(self, db):
        games = [pgn(moves=f"1. e4 e5 {i} 1-0") for i in range(3)]
        conn = connect(db)
        job_id = create_job(conn, "alice")
        run_sync(db, "alice", job_id, fetch_fn=fake_fetch(games), analyze_fn=fake_analyze)

        job = read_job(conn, job_id)
        assert job.status == "done"
        assert job.total == 3 and job.done == 3 and job.added == 3
        assert job.percent == 100
        assert stats(conn, "alice")["games"] == 3

    def test_a_second_sync_analyzes_only_what_is_new(self, db):
        first = [pgn(moves=f"1. e4 e5 {i} 1-0") for i in range(2)]
        second = first + [pgn(moves="1. d4 d5 new 1-0")]
        conn = connect(db)

        job_a = create_job(conn, "alice")
        run_sync(db, "alice", job_a, fetch_fn=fake_fetch(first), analyze_fn=fake_analyze)

        analyzed = []
        def counting_analyze(game):
            analyzed.append(game)
            return _base_report()

        job_b = create_job(conn, "alice")
        run_sync(db, "alice", job_b, fetch_fn=fake_fetch(second),
                 analyze_fn=counting_analyze)

        # The expensive step ran once, for the one game that was actually new.
        assert len(analyzed) == 1
        assert read_job(conn, job_b).added == 1
        assert stats(conn, "alice")["games"] == 3

    def test_nothing_new_is_said_plainly(self, db):
        games = [pgn(moves="1. e4 e5 1-0")]
        conn = connect(db)
        job_a = create_job(conn, "alice")
        run_sync(db, "alice", job_a, fetch_fn=fake_fetch(games), analyze_fn=fake_analyze)
        job_b = create_job(conn, "alice")
        run_sync(db, "alice", job_b, fetch_fn=fake_fetch(games), analyze_fn=fake_analyze)

        job = read_job(conn, job_b)
        assert job.status == "done"
        assert "up to date" in job.message

    def test_progress_is_visible_partway_through(self, db):
        """A page polling mid-sync must see movement, not a frozen zero."""
        seen = []
        conn = connect(db)
        games = [pgn(moves=f"1. e4 e5 {i} 1-0") for i in range(4)]

        def watching_analyze(game):
            seen.append(read_job(conn, job_id).done)
            return _base_report()

        job_id = create_job(conn, "alice")
        run_sync(db, "alice", job_id, fetch_fn=fake_fetch(games),
                 analyze_fn=watching_analyze)
        assert seen == [0, 1, 2, 3]

    def test_a_failure_reaches_the_job_row(self, db):
        def exploding_fetch(user, max_games):
            raise RuntimeError("chess.com said no")

        conn = connect(db)
        job_id = create_job(conn, "alice")
        run_sync(db, "alice", job_id, fetch_fn=exploding_fetch)

        job = read_job(conn, job_id)
        assert job.status == "failed"
        assert "chess.com said no" in job.message

    def test_a_game_with_no_moves_is_skipped_not_fatal(self, db):
        empty = '[Event "x"]\n[White "a"]\n[Black "b"]\n[Result "*"]\n\n*\n'
        conn = connect(db)
        job_id = create_job(conn, "alice")
        run_sync(db, "alice", job_id, fetch_fn=fake_fetch([empty]),
                 analyze_fn=fake_analyze)
        assert read_job(conn, job_id).status == "done"


class TestJobState:
    def test_latest_and_active(self, db):
        conn = connect(db)
        assert latest_job(conn, "alice") is None
        job_id = create_job(conn, "alice")
        assert active_job(conn, "alice").id == job_id
        update_job(conn, job_id, status="done")
        assert active_job(conn, "alice") is None
        assert latest_job(conn, "alice").status == "done"

    def test_a_job_that_stopped_reporting_is_not_shown_as_working(self, db):
        """Otherwise a killed server leaves a spinner running forever."""
        from datetime import datetime, timezone

        conn = connect(db)
        job_id = create_job(conn, "alice")
        stale = (datetime.now(timezone.utc) - STALE_AFTER * 2).isoformat(timespec="seconds")
        conn.execute("UPDATE jobs SET updated_at = ? WHERE id = ?", (stale, job_id))
        conn.commit()

        job = read_job(conn, job_id)
        assert job.status == "failed"
        assert not job.is_active
        assert "Syncing again is safe" in job.message

    def test_percent_is_zero_rather_than_a_crash_before_the_total_is_known(self, db):
        conn = connect(db)
        job = read_job(conn, create_job(conn, "alice"))
        assert job.total == 0
        assert job.percent == 0
