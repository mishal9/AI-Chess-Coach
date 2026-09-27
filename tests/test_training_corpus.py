"""Tests for the distillation corpus assembler.

The fetch is injectable and every filtering step is pure, so disjointness from the
held-out set, dedup, and the length filter are all validated with no network.
"""

from __future__ import annotations

import json

import pytest

from training import corpus


@pytest.fixture(autouse=True)
def _no_real_pacing_delay(monkeypatch):
    """Fake fetchers hit no real API, so the inter-user pacing delay would only slow the
    suite down for nothing. ``test_paced_sleeps_between_users_not_before_the_first``
    restores a real value to check the pacing itself."""
    monkeypatch.setattr(corpus, "FETCH_PACING_SECONDS", 0)


# A held-out-shaped game (carries a Lichess GameId) and a plain one.
HELDOUT_GAME = """[Event "rated bullet game"]
[Site "https://lichess.org/VOqkxbKK"]
[White "PseudoBenko"]
[Black "DrNykterstein"]
[Result "0-1"]
[GameId "VOqkxbKK"]

1. e4 e6 2. d4 d5 3. Nc3 Bb4 4. Ne2 dxe4 5. a3 Be7 6. Nxe4 Nf6 0-1
"""

# The same game re-exported without its GameId tag and with an eval comment.
HELDOUT_GAME_RETAGGED = """[Event "Casual game"]
[White "PseudoBenko"]
[Black "DrNykterstein"]
[Result "0-1"]

1. e4 e6 2. d4 d5 { [%eval 0.12] } 3. Nc3 Bb4 4. Ne2 dxe4 5. a3 Be7 6. Nxe4 Nf6 0-1
"""

FRESH_GAME = """[Event "rated blitz game"]
[Site "https://lichess.org/AbCdEfGh"]
[White "Alice"]
[Black "Bob"]
[Result "1-0"]
[GameId "AbCdEfGh"]

1. d4 Nf6 2. c4 e6 3. Nc3 Bb4 4. e3 O-O 5. Bd3 d5 6. Nf3 c5 7. O-O Nc6 1-0
"""

SHORT_GAME = """[Event "abandoned"]
[Site "https://lichess.org/ZzZzZzZz"]
[GameId "ZzZzZzZz"]

1. e4 e5 1-0
"""

FRESH_GAME_2 = """[Event "rated blitz game"]
[Site "https://lichess.org/QqRrSsTt"]
[White "Carol"]
[Black "Dave"]
[Result "0-1"]
[GameId "QqRrSsTt"]

1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 a6 6. Be2 e5 0-1
"""


# --- split_pgn / game_key ----------------------------------------------------------

def test_split_pgn_separates_games():
    blob = HELDOUT_GAME + "\n\n" + FRESH_GAME
    games = corpus.split_pgn(blob)
    assert len(games) == 2
    assert all(g.startswith("[Event ") for g in games)


def test_game_key_prefers_gameid():
    assert corpus.game_key(FRESH_GAME) == "id:AbCdEfGh"


def test_game_key_falls_back_to_site_then_movetext():
    no_id = FRESH_GAME.replace('[GameId "AbCdEfGh"]\n', "")
    assert corpus.game_key(no_id) == "id:AbCdEfGh"  # recovered from the Site URL
    no_site = "\n".join(
        l for l in no_id.splitlines() if not l.startswith("[Site")
    )
    assert corpus.game_key(no_site).startswith("moves:")


# --- disjointness from the held-out set --------------------------------------------

def test_assemble_drops_heldout_by_id():
    heldout = {corpus.game_key(HELDOUT_GAME)}
    kept = corpus.assemble([HELDOUT_GAME, FRESH_GAME], heldout)
    assert [corpus.game_key(g) for g in kept] == ["id:AbCdEfGh"]


def test_assemble_catches_retagged_heldout_by_movetext():
    """A held-out game re-exported without its id must still be excluded by its moves."""
    import hashlib

    # Fingerprint the original held-out game by both its id and its movetext hash.
    digest = hashlib.sha256(
        corpus._normalized_movetext(HELDOUT_GAME).encode("utf-8")
    ).hexdigest()[:16]
    prints = {corpus.game_key(HELDOUT_GAME), f"moves:{digest}"}

    kept = corpus.assemble([HELDOUT_GAME_RETAGGED, FRESH_GAME], prints)
    assert [corpus.game_key(g) for g in kept] == ["id:AbCdEfGh"]


def test_assemble_dedups_within_corpus_and_drops_short_games():
    kept = corpus.assemble([FRESH_GAME, FRESH_GAME, SHORT_GAME], set(), min_plies=10)
    assert len(kept) == 1
    assert corpus.game_key(kept[0]) == "id:AbCdEfGh"


def test_real_heldout_fingerprints_load():
    prints = corpus.heldout_fingerprints()
    assert prints  # the six curated held-out games exist
    assert all(p.startswith(("id:", "moves:")) for p in prints)


# --- write_corpus + manifest -------------------------------------------------------

def test_write_corpus_emits_distill_ready_manifest(tmp_path):
    manifest_path = corpus.write_corpus([FRESH_GAME, HELDOUT_GAME], tmp_path)
    assert (tmp_path / "corpus.pgn").exists()

    manifest = json.loads(manifest_path.read_text())
    assert [e["game_index"] for e in manifest] == [0, 1]
    assert all(e["pgn"] == "corpus.pgn" for e in manifest)
    assert all(e["coached_side"] is None for e in manifest)


# --- canonical_order (reproducible sweep tiers) -------------------------------------

def test_canonical_order_is_independent_of_input_order():
    forward = corpus.canonical_order([FRESH_GAME, HELDOUT_GAME, SHORT_GAME])
    backward = corpus.canonical_order([SHORT_GAME, HELDOUT_GAME, FRESH_GAME])
    assert forward == backward


def test_canonical_order_is_stable_across_calls():
    # No shuffle state, no clock — same input, same seed, same order every time.
    a = corpus.canonical_order([FRESH_GAME, HELDOUT_GAME, SHORT_GAME], seed=0)
    b = corpus.canonical_order([FRESH_GAME, HELDOUT_GAME, SHORT_GAME], seed=0)
    assert a == b


def test_canonical_order_prefix_is_nested_regardless_of_pool_growth():
    # The prefix that makes up a smaller sweep tier must survive the corpus growing —
    # exactly the "player keeps playing between fetches" scenario this exists for.
    small_pool = [FRESH_GAME, HELDOUT_GAME]
    grown_pool = [FRESH_GAME, HELDOUT_GAME, SHORT_GAME]
    small_order = corpus.canonical_order(small_pool)
    grown_order = corpus.canonical_order(grown_pool)
    assert small_order == [g for g in grown_order if g in small_pool]


def test_canonical_order_differs_by_seed():
    seed0 = corpus.canonical_order([FRESH_GAME, HELDOUT_GAME, SHORT_GAME], seed=0)
    seed1 = corpus.canonical_order([FRESH_GAME, HELDOUT_GAME, SHORT_GAME], seed=1)
    assert seed0 != seed1  # not a hard requirement, but true for this fixture set


# --- CLI wiring (fetch injected) ---------------------------------------------------

def test_main_fetches_dedups_and_writes(tmp_path):
    # HELDOUT_GAME is one_blunder.pgn (GameId VOqkxbKK) — a *real* held-out game, so the
    # assembler must drop it against the on-disk held-out set, keeping only FRESH_GAME.
    def fake_fetch(user, max_games):
        return HELDOUT_GAME + "\n\n" + FRESH_GAME

    rc = corpus.main(
        ["--user", "someone", "--out-dir", str(tmp_path)],
        fetch_fn=fake_fetch,
    )
    assert rc == 0
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert len(manifest) == 1  # the real held-out game is excluded; FRESH_GAME survives
    games = corpus.split_pgn((tmp_path / "corpus.pgn").read_text())
    assert corpus.game_key(games[0]) == "id:AbCdEfGh"


def test_main_falls_back_to_default_roster(tmp_path):
    fetched = []

    def fake_fetch(user, max_games):
        fetched.append(user)
        return FRESH_GAME if user == "maia1" else ""

    rc = corpus.main(["--out-dir", str(tmp_path)], fetch_fn=fake_fetch)
    assert rc == 0
    assert fetched == corpus.DEFAULT_USERS  # every roster account was fetched
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert len(manifest) == 1


def test_main_returns_1_when_no_games(tmp_path):
    assert corpus.main(["--user", "nobody", "--out-dir", str(tmp_path)],
                       fetch_fn=lambda u, m: "") == 1


# --- pacing between sequential per-user fetches (be polite to Lichess) -------------

def test_paced_yields_users_unchanged():
    assert list(corpus._paced(["a", "b", "c"])) == ["a", "b", "c"]
    assert list(corpus._paced([])) == []
    assert list(corpus._paced(["only"])) == ["only"]


def test_paced_sleeps_between_users_not_before_the_first(monkeypatch):
    slept = []
    monkeypatch.setattr(corpus.time, "sleep", lambda s: slept.append(s))
    monkeypatch.setattr(corpus, "FETCH_PACING_SECONDS", 3.0)

    list(corpus._paced(["a", "b", "c"]))

    assert slept == [3.0, 3.0]  # one gap before each user after the first, none before it


def test_main_paces_between_users(monkeypatch, tmp_path):
    monkeypatch.setattr(corpus, "FETCH_PACING_SECONDS", 5.0)
    slept = []
    monkeypatch.setattr(corpus.time, "sleep", lambda s: slept.append(s))

    corpus.main(
        ["--user", "a", "--user", "b", "--user", "c", "--out-dir", str(tmp_path)],
        fetch_fn=lambda u, m: FRESH_GAME,
    )
    assert slept == [5.0, 5.0]


def test_main_canonical_seed_reorders_the_written_corpus(tmp_path):
    def fake_fetch(user, max_games):
        return FRESH_GAME + "\n\n" + FRESH_GAME_2  # fetch order: AbCdEfGh, then QqRrSsTt

    default_rc = corpus.main(["--user", "x", "--out-dir", str(tmp_path / "a")],
                             fetch_fn=fake_fetch)
    seeded_rc = corpus.main(
        ["--user", "x", "--out-dir", str(tmp_path / "b"), "--canonical-seed", "0"],
        fetch_fn=fake_fetch,
    )
    assert default_rc == seeded_rc == 0

    fetch_order = corpus.split_pgn((tmp_path / "a" / "corpus.pgn").read_text())
    canonical = corpus.split_pgn((tmp_path / "b" / "corpus.pgn").read_text())
    assert [corpus.game_key(g) for g in fetch_order] == ["id:AbCdEfGh", "id:QqRrSsTt"]

    # Same two games, but in the identity-hash order, not the order they were fetched in —
    # this is the property that stays reproducible across a corpus fetched at another time.
    expected = [corpus.game_key(g) for g in corpus.canonical_order([FRESH_GAME, FRESH_GAME_2])]
    assert [corpus.game_key(g) for g in canonical] == expected
    assert set(expected) == {"id:AbCdEfGh", "id:QqRrSsTt"}


# --- sampling by rating band from the database export ----------------------------------

_MOVES = "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 {i}"


def _db_game(gid, white=1500, black=1500, tc="300+0", event="Rated Blitz game",
             extra="", moves=None):
    return (f'[Event "{event}"]\n[Site "https://lichess.org/{gid}"]\n'
            f'[WhiteElo "{white}"]\n[BlackElo "{black}"]\n[TimeControl "{tc}"]\n'
            f'[Termination "Normal"]\n{extra}\n'
            f"{moves or _MOVES.format(i='1-0')}\n")


@pytest.mark.parametrize("game, cell", [
    (_db_game("a", 1000, 1100), ("<1200", "blitz")),
    (_db_game("b", 1500, 1600), ("1200-1599", "blitz")),
    (_db_game("c", 1599, 1600), ("1200-1599", "blitz")),   # mean 1599.5 is below 1600
    (_db_game("d", 2450, 2500), ("2400+", "blitz")),
    (_db_game("e", tc="600+0"), ("1200-1599", "rapid")),
    (_db_game("f", tc="900+15"), ("1200-1599", "classical")),   # 1,500 s estimated
    (_db_game("g", tc="60+0"), None),               # bullet
    (_db_game("h", tc="120+1"), None),              # 160 s estimated: still bullet
    (_db_game("i", tc="-"), None),                  # correspondence
    (_db_game("j", 1200, 1500), None),              # players too far apart
    (_db_game("k", event="Casual Blitz game"), None),
    (_db_game("l", extra='[FEN "8/8/8/8/8/8/8/K6k w - - 0 1"]'), None),
    (_db_game("m", black="?"), None),
    (_db_game("n").replace("Normal", "Abandoned"), None),
])
def test_db_cell(game, cell):
    assert corpus.db_cell(game) == cell


def test_bot_games_are_skipped():
    assert corpus.db_cell(_db_game("bot", extra='[WhiteTitle "BOT"]')) is None
    assert corpus.db_cell(_db_game("gm", extra='[WhiteTitle "GM"]')) == ("1200-1599", "blitz")


def test_split_decoded_slice_drops_partial_games_at_both_ends():
    games = [_db_game(f"p{i}") for i in range(3)]
    text = "\n\n".join(games)
    sliced = text[len(games[0]) // 2 : -10]   # starts inside game 0, ends inside game 2
    assert [corpus.game_key(g) for g in corpus.split_decoded_slice(sliced)] == ["id:p1"]
    assert corpus.split_decoded_slice("no games here") == []


def test_decode_slice_starts_at_a_later_zstd_frame():
    zstd = pytest.importorskip("zstandard")
    frames = [zstd.ZstdCompressor().compress(f"frame {i}\n".encode() * 50) for i in range(3)]
    data = b"".join(frames)
    cut = data[len(frames[0]) // 2 : -5]   # mid-frame 0 to mid-frame 2
    text = corpus._decode_slice(cut)
    assert text.startswith("frame 1") and "frame 0" not in text


def _unique(gid, tc="300+0", white=1500):
    return _db_game(gid, white, white, tc=tc, moves=_MOVES.format(i=f"7. {gid} 1-0"))


def test_collect_cells_limits_each_slice_and_the_total():
    slices = [[_unique(f"h{k}{i}") for i in range(5)] for k in range(3)]
    cells = corpus.collect_cells(slices, per_slice=2, cap=5, heldout=set())
    got = [corpus.game_key(g) for g in cells["1200-1599", "blitz"]]
    assert got == ["id:h00", "id:h01", "id:h10", "id:h11", "id:h20"]


def test_collect_cells_skips_heldout_duplicate_and_short_games():
    stream = [
        _unique("HELD"),
        _db_game("x1"),
        _db_game("x2"),                          # same moves as x1
        _db_game("x3", moves="1. e4 e5 1-0"),    # too short
        _unique("x4"),
    ]
    cells = corpus.collect_cells([stream], per_slice=9, cap=9, heldout={"id:HELD"})
    assert [corpus.game_key(g) for g in cells["1200-1599", "blitz"]] == ["id:x1", "id:x4"]


@pytest.mark.parametrize("available, total, expected", [
    ({"a": 1000, "b": 1000, "c": 1000}, 300, {"a": 100, "b": 100, "c": 100}),
    ({"a": 1000, "b": 1000, "c": 10}, 300, {"a": 145, "b": 145, "c": 10}),
    ({"a": 1000, "b": 30, "c": 0}, 300, {"a": 270, "b": 30, "c": 0}),
    ({"a": 50, "b": 40, "c": 0}, 300, {"a": 50, "b": 40, "c": 0}),   # short overall
])
def test_allocate_is_as_equal_as_availability_allows(available, total, expected):
    assert corpus.allocate(available, total) == expected


def test_allocate_hands_out_rounding_leftovers():
    alloc = corpus.allocate({"a": 1000, "b": 1000, "c": 1000}, 301)
    assert sorted(alloc.values()) == [100, 100, 101]


def test_select_balanced_shares_a_band_across_speeds_and_spreads_picks():
    blitz = [_unique(f"b{i}") for i in range(10)]
    rapid = [_unique(f"r{i}", tc="600+0") for i in range(10)]
    cells = corpus.collect_cells([blitz + rapid], per_slice=10, cap=10, heldout=set())
    chosen = corpus.select_balanced(cells, per_band=4)
    # two each; picks are spaced through the candidates, not the first two
    assert [corpus.game_key(g) for g in chosen["1200-1599", "blitz"]] == ["id:b0", "id:b5"]
    assert len(chosen["1200-1599", "rapid"]) == 2
    assert chosen["1200-1599", "classical"] == [] and chosen["2400+", "blitz"] == []


def test_main_from_db_writes_corpus_and_source(tmp_path):
    games = [_unique(f"s{i}") for i in range(3)] + [_unique("s9", tc="600+0")]
    args = corpus.build_parser().parse_args(
        ["--from-db", "2026-08", "--per-band", "2", "--slices", "1", "--min-plies", "10",
         "--out-dir", str(tmp_path), "--canonical-seed", "0"])
    assert corpus._main_from_db(args, fetch_fn=lambda url, n: iter([games])) == 0
    assert len(json.loads((tmp_path / "manifest.json").read_text())) == 2
    source = json.loads((tmp_path / "source.json").read_text())
    assert source["url"].endswith("rated_2026-08.pgn.zst")
    assert source["games"]["1200-1599"] == {"blitz": 1, "rapid": 1, "classical": 0}
    assert source["candidates"]["1200-1599"]["blitz"] == 2
