"""Opening names: useful for the reader, and free of move notation.

The opening is printed into the coach's facts block, which is exactly the set of moves
`eval.grounding` licenses the coach to cite. A variation suffix left in the name would
authorise citing moves that were never played in the game being coached.
"""

from __future__ import annotations

import pytest

from engine.analyzer import opening_name
from eval.grounding import extract_moves


class TestOpeningName:
    def test_lichess_supplies_the_name_directly(self):
        assert opening_name({"Opening": "Sicilian Defense: Najdorf"}) == \
            "Sicilian Defense: Najdorf"

    def test_chesscom_name_comes_from_the_ecourl_slug(self):
        assert opening_name(
            {"ECOUrl": "https://www.chess.com/openings/Sicilian-Defense"}
        ) == "Sicilian Defense"

    @pytest.mark.parametrize(
        "slug,expected",
        [
            ("Petrovs-Defense-3.d3-Nc6-4.Be2", "Petrovs Defense"),
            ("Philidor-Defense-3.Nc3", "Philidor Defense"),
            ("Kings-Pawn-Opening-Kings-Knight-Variation-2...Nc6-3.d3",
             "Kings Pawn Opening Kings Knight Variation"),
            ("Modern-Defense-Geller-System-4...Nd7", "Modern Defense Geller System"),
        ],
    )
    def test_the_variation_suffix_is_stripped(self, slug, expected):
        name = opening_name({"ECOUrl": f"https://www.chess.com/openings/{slug}"})
        assert name == expected
        assert extract_moves(name) == set(), "opening name would license a move citation"

    def test_event_is_not_an_opening(self):
        """The old fallback produced 'Live Chess' for every chess.com game."""
        assert opening_name({"Event": "Live Chess"}) == "?"
        assert opening_name({"Event": "Rated Blitz game"}) == "?"

    def test_missing_headers_give_a_question_mark(self):
        assert opening_name({}) == "?"
        assert opening_name({"Opening": "?"}) == "?"

    def test_every_real_slug_from_a_live_account_is_move_free(self):
        """Regression net over the opening slugs an actual chess.com account produced."""
        slugs = [
            "Sicilian-Defense", "Four-Knights-Game-4.Be2", "Petrovs-Defense-3.d3-Nc6",
            "Philidor-Defense-3.Nc3", "Modern-Defense-Geller-System-4...Nd7",
            "Sicilian-Defense-Old-Sicilian-Variation-3.b3",
            "Pirc-Defense-Modern-Defense-Geller-System-2...Nf6",
            "Kings-Pawn-Opening-Kings-Knight-Variation-2...Nc6-3.d3",
            "Petrovs-Defense-3.d3-Nc6-4.Be2", "Scandinavian-Defense", "Kings-Gambit",
        ]
        for slug in slugs:
            name = opening_name({"ECOUrl": f"https://www.chess.com/openings/{slug}"})
            assert extract_moves(name) == set(), f"{slug} -> {name!r} leaks a move"
            assert name != "?", f"{slug} produced no usable name"
