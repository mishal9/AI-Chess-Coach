"""The blinded human-rating instrument.

The tests that matter are the blinding ones: an item a rater can trace back to a system
is not a blind rating, and an agreement number computed from it would be worthless.
"""

from __future__ import annotations

import csv
import json
from collections import Counter

import pytest

pytest.importorskip("scipy", reason="needs the `eval` extra")

from eval.human_rating import (  # noqa: E402
    RatingItem,
    agreement,
    bucket_of,
    collect,
    consensus_ratings,
    judge_scores_for,
    load_many_ratings,
    load_ratings,
    mean_pairwise_r,
    paired_sample,
    pairwise_agreement,
    render_sheet,
    stratified_sample,
    write_round,
)
from eval.rubric import RUBRIC_AXES  # noqa: E402


def item(bucket="one_blunder", source="report_a", coaching="You played Nxe5.", idx=0):
    return RatingItem(
        item_id="", coaching=coaching, facts="the engine preferred d3",
        source_report=source, pgn=f"{bucket}.pgn", game_index=idx, bucket=bucket,
    )


def pool():
    """Two arms x three buckets x two games — enough to test stratification."""
    out = []
    for source in ("prompted_8b_2026-08-14", "8b_v2_2026-08-10"):
        for bucket in ("clean_draw", "one_blunder", "multi_blunder"):
            for i in range(2):
                # Coaching text must not name its source, or the blinding tests would
                # be checking the fixture rather than the renderer.
                out.append(item(bucket=bucket, source=source, idx=i,
                                coaching=f"Coaching text {bucket} {i} for arm {len(out)}"))
    return out


class TestBlinding:
    def test_item_ids_carry_no_provenance(self):
        sample = stratified_sample(pool(), size=6, seed=1)
        ids = [i.item_id for i in sample.items]
        assert ids == [f"item-0{n}" for n in range(1, 7)]

    def test_the_sheet_never_names_a_source_report(self):
        """A rater who can tell which system wrote a text is not rating the text."""
        items = [item(source="8b_v2_2026-08-10", coaching="Neutral coaching text.")]
        sheet = render_sheet(stratified_sample(items, size=1, seed=1))
        assert "8b_v2" not in sheet
        assert "prompted" not in sheet
        assert "2026-08-10" not in sheet

    def test_only_the_answer_key_maps_items_back(self, tmp_path):
        sample = stratified_sample(pool(), size=6, seed=1)
        paths = write_round(sample, tmp_path)
        key = paths["key"].read_text()
        assert "8b_v2_2026-08-10" in key, "the key must record provenance"
        assert "8b_v2_2026-08-10" not in paths["sheet"].read_text()
        assert "8b_v2_2026-08-10" not in paths["ratings"].read_text()

    def test_order_does_not_track_the_source(self):
        """If arms alternated, a rater could infer provenance from position alone."""
        sample = stratified_sample(pool(), size=12, seed=7)
        sources = [i.source_report for i in sample.items]
        alternating = all(a != b for a, b in zip(sources, sources[1:]))
        assert not alternating


class TestSampling:
    def test_spreads_across_buckets(self):
        sample = stratified_sample(pool(), size=6, seed=1)
        assert set(sample.buckets) == {"clean_draw", "one_blunder", "multi_blunder"}
        assert all(count == 2 for count in sample.buckets.values())

    def test_is_reproducible_for_a_second_rater(self):
        """Both raters must see identical items or the agreement is between samples."""
        a = stratified_sample(pool(), size=6, seed=42)
        b = stratified_sample(pool(), size=6, seed=42)
        assert [(i.item_id, i.coaching) for i in a.items] == \
               [(i.item_id, i.coaching) for i in b.items]

    def test_asking_for_more_than_exists_returns_what_there_is(self):
        assert len(stratified_sample(pool(), size=99, seed=1).items) == 12

    def test_balances_arms_within_each_bucket(self):
        """The real bug this fixes: one bucket ending up 4:1 by shuffle luck."""
        sample = stratified_sample(pool(), size=6, seed=1)  # 2 per bucket, both arms
        assert sample.arms == {"prompted_8b_2026-08-14": 3, "8b_v2_2026-08-10": 3}
        for bucket in sample.buckets:
            by_arm = Counter(i.source_report for i in sample.items if i.bucket == bucket)
            assert max(by_arm.values()) - min(by_arm.values()) <= 1

    def test_odd_per_bucket_quota_is_off_by_one_not_worse(self):
        items = [
            item(bucket="X", source=src, idx=i, coaching=f"{src}-{i}")
            for src in ("a", "b")
            for i in range(5)
        ]
        for size in (1, 3, 5, 7, 9):
            sample = stratified_sample(items, size=size, seed=3)
            counts = Counter(i.source_report for i in sample.items)
            assert abs(counts.get("a", 0) - counts.get("b", 0)) <= 1, (size, counts)

    def test_balances_each_bucket_independently(self):
        """A bucket with more of one arm available shouldn't affect another bucket."""
        items = [
            item(bucket=bucket, source=src, idx=i, coaching=f"{bucket}-{src}-{i}")
            for bucket in ("clean_draw", "multi_blunder")
            for src in ("a", "b")
            for i in range(4)
        ]
        sample = stratified_sample(items, size=10, seed=5)  # 5 per bucket: 3:2 or 2:3
        for bucket in ("clean_draw", "multi_blunder"):
            by_arm = Counter(i.source_report for i in sample.items if i.bucket == bucket)
            assert sum(by_arm.values()) == 5
            assert max(by_arm.values()) - min(by_arm.values()) <= 1


class TestRoundTrip:
    def test_the_blank_csv_has_a_row_per_item_and_a_column_per_axis(self, tmp_path):
        sample = stratified_sample(pool(), size=4, seed=1)
        paths = write_round(sample, tmp_path)
        rows = list(csv.DictReader(paths["ratings"].open()))
        assert len(rows) == 4
        assert set(RUBRIC_AXES).issubset(rows[0].keys())
        assert all(rows[0][a] == "" for a in RUBRIC_AXES)

    def test_returned_ratings_load_back(self, tmp_path):
        path = tmp_path / "ratings.csv"
        with path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["item_id", *RUBRIC_AXES, "comment"])
            writer.writerow(["item-01", 4, 5, 3, 5, "solid"])
            writer.writerow(["item-02", "", "", "", "", "skipped"])
        loaded = load_ratings(path)
        assert loaded["item-01"]["factual_correctness"] == 4
        assert "item-02" not in loaded, "an unscored row is not a rating"

    def test_out_of_range_scores_are_clamped(self, tmp_path):
        path = tmp_path / "ratings.csv"
        with path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["item_id", *RUBRIC_AXES, "comment"])
            writer.writerow(["item-01", 9, 0, 3, 3, ""])
        loaded = load_ratings(path)
        assert loaded["item-01"]["factual_correctness"] == 5
        assert loaded["item-01"]["clarity"] == 1


class TestAgreement:
    def test_matches_judge_scores_through_the_key(self, tmp_path):
        report = {"games": [
            {"pgn": "one_blunder.pgn", "game_index": 0,
             "rubric": {"scores": {a: 4 for a in RUBRIC_AXES}, "overall": 4.0}},
        ]}
        report_path = tmp_path / "r.json"
        report_path.write_text(json.dumps(report))
        key = tmp_path / "answer_key.csv"
        with key.open("w", newline="") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=["item_id","source_report","pgn","game_index","bucket"])
            writer.writeheader()
            writer.writerow({"item_id": "item-01", "source_report": "r",
                             "pgn": "one_blunder.pgn", "game_index": 0,
                             "bucket": "one_blunder"})
        scores = judge_scores_for(key, {"r": report_path})
        assert scores["item-01"]["factual_correctness"] == 4

    def test_a_generous_judge_shows_as_bias_with_ranking_intact(self):
        human = {f"i{n}": {a: n for a in RUBRIC_AXES} for n in range(1, 5)}
        judge = {f"i{n}": {a: n + 1 for a in RUBRIC_AXES} for n in range(1, 5)}
        result = agreement(human, judge)["factual_correctness"]
        assert result["pearson"] == pytest.approx(1.0)
        assert result["bias"] == pytest.approx(1.0)
        assert result["exact"] == 0.0
        assert result["within_one"] == 1.0

    def test_only_items_both_scored_are_compared(self):
        human = {f"i{n}": {a: 3 for a in RUBRIC_AXES} for n in range(5)}
        judge = {f"i{n}": {a: 3 for a in RUBRIC_AXES} for n in range(3)}
        assert agreement(human, judge)["clarity"]["n"] == 3


class TestMultiRaterConsensus:
    def _write_ratings(self, tmp_path, name, rows):
        path = tmp_path / f"ratings_{name}.csv"
        with path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["item_id", *RUBRIC_AXES, "comment"])
            for item_id, scores in rows.items():
                writer.writerow([item_id, *[scores.get(a, "") for a in RUBRIC_AXES], ""])
        return path

    def test_load_many_ratings_keys_by_rater_name(self, tmp_path):
        paths = {
            "sam": self._write_ratings(tmp_path, "sam", {"item-01": {a: 4 for a in RUBRIC_AXES}}),
            "alex": self._write_ratings(tmp_path, "alex", {"item-01": {a: 2 for a in RUBRIC_AXES}}),
        }
        by_rater = load_many_ratings(paths)
        assert set(by_rater) == {"sam", "alex"}
        assert by_rater["sam"]["item-01"]["clarity"] == 4
        assert by_rater["alex"]["item-01"]["clarity"] == 2

    def test_median_consensus_is_not_dragged_by_one_outlier(self):
        by_rater = {
            "a": {"item-01": {"clarity": 4}},
            "b": {"item-01": {"clarity": 5}},
            "c": {"item-01": {"clarity": 1}},  # one rater way out of line
        }
        consensus = consensus_ratings(by_rater, method="median")
        assert consensus["item-01"]["clarity"] == 4
        mean_consensus = consensus_ratings(by_rater, method="mean")
        assert mean_consensus["item-01"]["clarity"] == pytest.approx(10 / 3, abs=1e-3)

    def test_consensus_skips_items_nobody_scored_on_an_axis(self):
        by_rater = {
            "a": {"item-01": {"clarity": 4}},
            "b": {"item-01": {}},  # rater saw the item but left this axis blank
        }
        consensus = consensus_ratings(by_rater)
        assert consensus["item-01"]["clarity"] == 4

    def test_consensus_rejects_unknown_method(self):
        with pytest.raises(ValueError):
            consensus_ratings({"a": {}}, method="mode")

    def test_pairwise_agreement_covers_every_pair_once(self):
        by_rater = {
            "a": {f"i{n}": {a: 3 for a in RUBRIC_AXES} for n in range(5)},
            "b": {f"i{n}": {a: 3 for a in RUBRIC_AXES} for n in range(5)},
            "c": {f"i{n}": {a: 3 for a in RUBRIC_AXES} for n in range(5)},
        }
        pairwise = pairwise_agreement(by_rater)
        assert set(pairwise) == {("a", "b"), ("a", "c"), ("b", "c")}

    def test_mean_pairwise_r_averages_across_pairs(self):
        by_rater = {
            "a": {f"i{n}": {"clarity": n} for n in range(1, 5)},
            "b": {f"i{n}": {"clarity": n} for n in range(1, 5)},  # perfect agreement
            "c": {f"i{n}": {"clarity": 5 - n} for n in range(1, 5)},  # perfect reversal
        }
        pairwise = pairwise_agreement(by_rater)
        result = mean_pairwise_r(pairwise)
        # (a,b)=+1, (a,c)=-1, (b,c)=-1 -> mean = -1/3
        assert result["clarity"] == pytest.approx(-1 / 3, abs=1e-3)


def test_bucket_of_prefers_the_manifest_label_over_the_file_name():
    game = {"pgn": "slow_loss.pgn", "game_index": 4}
    assert bucket_of(game) == "slow_loss"
    assert bucket_of(game, {("slow_loss.pgn", 4): "inaccuracies"}) == "inaccuracies"
    assert bucket_of({**game, "bucket": "two_mistakes"}) == "two_mistakes"


class TestPairedSample:
    """Round 2 compares arms on the same games, so every game must carry every arm."""

    ARMS = ("base", "student", "teacher")

    def three_arm_pool(self, games_per_bucket=3):
        out = []
        for source in self.ARMS:
            for bucket in ("clean_draw", "one_blunder", "multi_blunder"):
                for i in range(games_per_bucket):
                    out.append(item(bucket=bucket, source=source, idx=i,
                                    coaching=f"text {source} {bucket} {i}"))
        return out

    def test_each_picked_game_has_every_arm_once(self):
        sample = paired_sample(self.three_arm_pool(), games=4, seed=3)
        assert len(sample.items) == 12
        per_game = Counter((i.pgn, i.game_index) for i in sample.items)
        assert len(per_game) == 4 and set(per_game.values()) == {3}
        for game in per_game:
            arms = {i.source_report for i in sample.items if (i.pgn, i.game_index) == game}
            assert arms == set(self.ARMS)

    def test_games_spread_across_buckets(self):
        sample = paired_sample(self.three_arm_pool(), games=6, seed=3)
        games = {(i.pgn, i.game_index, i.bucket) for i in sample.items}
        assert Counter(b for _, _, b in games) == {"clean_draw": 2, "one_blunder": 2,
                                                    "multi_blunder": 2}

    def test_a_game_missing_an_arm_is_never_picked(self):
        items = [i for i in self.three_arm_pool()
                 if not (i.bucket == "clean_draw" and i.source_report == "teacher")]
        sample = paired_sample(items, games=9, seed=3)
        assert "clean_draw" not in {i.bucket for i in sample.items}

    def test_no_two_neighbours_share_a_game(self):
        sample = paired_sample(self.three_arm_pool(), games=6, seed=5)
        keys = [(i.pgn, i.game_index) for i in sample.items]
        assert all(a != b for a, b in zip(keys, keys[1:]))

    def test_ids_are_sequential_and_seed_is_reproducible(self):
        a = paired_sample(self.three_arm_pool(), games=4, seed=9)
        b = paired_sample(self.three_arm_pool(), games=4, seed=9)
        assert [i.item_id for i in a.items] == [f"item-{n:02d}" for n in range(1, 13)]
        assert [i.coaching for i in a.items] == [i.coaching for i in b.items]

    def test_items_json_is_blinded(self, tmp_path):
        sample = paired_sample(self.three_arm_pool(), games=2, seed=1)
        paths = write_round(sample, tmp_path)
        rows = json.loads(paths["items"].read_text())
        assert [r["item_id"] for r in rows] == [i.item_id for i in sample.items]
        assert all(set(r) == {"item_id", "game", "facts", "coaching"} for r in rows)
        # The game id names the game, never the arm: one id per game, shared by its arms.
        assert len({r["game"] for r in rows}) == 2


def test_board_data_replays_the_game_and_flags_the_moves_the_facts_name(tmp_path):
    from eval.human_rating import Sample, board_data

    (tmp_path / "g.pgn").write_text(
        '[Event "a"]\n\n1. e4 e5 2. Nf3 Nc6 *\n\n[Event "b"]\n\n1. d4 d5 2. c4 e6 11. *\n',
        encoding="utf-8")
    (tmp_path / "manifest.json").write_text(json.dumps(
        [{"pgn": "g.pgn", "game_index": 1, "coached_side": "black"}]), encoding="utf-8")
    it = RatingItem(item_id="item-01", coaching="x", source_report="r", pgn="g.pgn",
                    game_index=1, bucket="b",
                    facts="- 2.c4?! (inaccuracy): the engine preferred Nf3.\n- 12.c4 is not this game")
    data = board_data(Sample(items=[it]), tmp_path / "manifest.json")
    game = data["g01"]
    assert game["orientation"] == "black"
    assert [p["label"] for p in game["plies"]] == ["1.d4", "1...d5", "2.c4", "2...e6"]
    assert [p["flag"] for p in game["plies"]] == [False, False, True, False]
    assert game["plies"][0]["from"] == "d2" and game["plies"][0]["to"] == "d4"
    assert game["plies"][-1]["fen"] == "rnbqkbnr/ppp2ppp/4p3/3p4/2PP4/8/PP2PPPP/RNBQKBNR"
