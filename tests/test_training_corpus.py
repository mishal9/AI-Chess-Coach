"""Tests for the distillation corpus assembler.

The fetch is injectable and every filtering step is pure, so disjointness from the
held-out set, dedup, and the length filter are all validated with no network.
"""

from __future__ import annotations

import json

from training import corpus


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


def test_main_needs_a_source(tmp_path):
    assert corpus.main(["--out-dir", str(tmp_path)], fetch_fn=lambda u, m: "") == 1
