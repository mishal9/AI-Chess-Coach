"""End-to-end validation of the report CLI on a famous game (the Opera Game).

The Phase-1 checkpoint: run the analyzer on Morphy's Opera Game and confirm the report
is sane — Black (the allies) plays worse than Morphy, mistakes are flagged, and the
win-probability clamp holds so no move shows an absurd loss. Requires Stockfish (CI
installs it; locally `brew install stockfish`).
"""

import json
import shutil
from pathlib import Path

import pytest

from engine.analyzer import analyze_game
from engine.loader import iter_games
from engine.report import format_summary, load_game
from engine.scoring import MATE_CP, MoveQuality

requires_stockfish = pytest.mark.skipif(
    shutil.which("stockfish") is None, reason="Stockfish not installed"
)

OPERA_PGN = Path(__file__).parent / "data" / "opera_game.pgn"
TEST_DEPTH = 14


@pytest.fixture(scope="module")
def opera_report():
    game = load_game(OPERA_PGN, 0)
    assert game is not None
    return analyze_game(game, depth=TEST_DEPTH)


def test_fixture_parses():
    games = list(iter_games(OPERA_PGN))
    assert len(games) == 1
    assert games[0].headers["White"] == "Paul Morphy"


@requires_stockfish
def test_black_plays_worse_than_morphy(opera_report):
    # The losing allies were gradually outplayed — their average centipawn loss should be
    # clearly higher than Morphy's. (Note: Morphy won by *sacrificing*, so this game has no
    # single Black blunder; discrete blunder detection is covered in test_analyzer.py.)
    s = opera_report.summary
    assert s["acpl_black"] > s["acpl_white"]


@requires_stockfish
def test_engine_best_move_is_never_flagged(opera_report):
    # Regression for the search-horizon artifact: a move equal to the engine's own top
    # choice must carry zero loss and never be tagged a mistake.
    for m in opera_report.moves:
        if m.best_san is not None and m.san == m.best_san:
            assert m.win_prob_loss == 0.0
            assert m.cp_loss == 0
            assert m.quality is MoveQuality.BEST


@requires_stockfish
def test_clamp_holds_no_absurd_loss(opera_report):
    # The final position is a forced mate; without the win-probability clamp + best-move
    # guard, a forced recapture would show a ~MATE_CP-sized cp_loss. Guard nothing explodes.
    assert all(m.win_prob_loss <= 1.0 for m in opera_report.moves)
    assert all(m.cp_loss < MATE_CP for m in opera_report.moves)


@requires_stockfish
def test_report_json_round_trips(opera_report):
    payload = json.dumps(opera_report.to_dict())
    back = json.loads(payload)
    assert back["white"] == "Paul Morphy"
    assert len(back["moves"]) == len(opera_report.moves)
    # Every serialized quality is a plain string, not an enum.
    assert all(isinstance(m["quality"], str) for m in back["moves"])


@requires_stockfish
def test_format_summary_mentions_key_facts(opera_report):
    text = format_summary(opera_report, depth=TEST_DEPTH, top=5)
    assert "Morphy" in text
    assert "ACPL" in text
    assert "Blunders:" in text
