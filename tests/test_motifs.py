"""Motif tagging: does the right label come off the engine's own analysis?

Every FEN and PV line here was generated and legality-checked with python-chess rather
than written by hand, because hand-written chess in a test is how you end up "fixing"
working code to satisfy a position that was illegal to begin with.
"""

from __future__ import annotations

import chess
import pytest

from memory.motifs import (
    MINOR_PIECE_VALUE,
    exchange_window,
    game_phase,
    material,
    replay,
    tag_move,
    tag_report,
)

# White plays Nxe5??; Black's Nxe5 wins a knight for the pawn.
HANG_FEN = "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 1"
HANG_REPLY_FEN = "r1bqkbnr/pppp1ppp/2n5/4N3/2B1P3/8/PPPP1PPP/RNBQK2R b KQkq - 0 1"

# Black knight on e4 lands f2, hitting the white king on d1 and the loose rook on h1.
FORK_REPLY_FEN = "4k3/8/8/8/4n3/8/8/3K3R b - - 0 1"

# Black king on g8 walled in by f7/g7/h7; White's Re8 is mate on the back rank.
BACK_RANK_REPLY_FEN = "6k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1"

# White to move with Rxd8 hanging a whole queen.
MISSED_FEN = "3q2k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1"


def move(**overrides) -> dict:
    """An analyzed-move dict with sane defaults, in the shape `GameReport` emits."""
    base = {
        "ply": 1,
        "move_number": 1,
        "side": "white",
        "san": "Nxe5",
        "best_san": "d3",
        "eval_before": 0,
        "eval_after": -300,
        "cp_loss": 300,
        "win_prob_loss": 0.25,
        "quality": "blunder",
        "fen_before": HANG_FEN,
        "pv": [],
    }
    return {**base, **overrides}


class TestMaterial:
    def test_counts_pieces_excluding_kings(self):
        board = chess.Board()
        # 8 pawns, 2 knights, 2 bishops, 2 rooks, 1 queen — kings contribute nothing.
        assert material(board, chess.WHITE) == 8 * 100 + 640 + 660 + 1000 + 900
        assert material(board, chess.WHITE) == material(board, chess.BLACK)

    def test_bare_kings_are_zero(self):
        assert material(chess.Board("4k3/8/8/8/8/8/8/4K3 w - - 0 1"), chess.WHITE) == 0


class TestGamePhase:
    def test_start_is_opening(self):
        assert game_phase(chess.STARTING_FEN, 1) == "opening"

    def test_bare_endgame(self):
        assert game_phase("4k3/4p3/8/8/8/8/4P3/4K3 w - - 0 1", 60) == "endgame"

    def test_full_material_late_is_middlegame(self):
        # Ply guards the opening: a full board on move 30 is not still an opening.
        assert game_phase(chess.STARTING_FEN, 60) == "middlegame"


class TestExchangeWindow:
    def test_cuts_before_promotion(self):
        assert exchange_window(["axb5", "g6", "b6", "Kf8", "b7", "b8=Q"]) == [
            "axb5",
            "g6",
            "b6",
            "Kf8",
            "b7",
        ]

    def test_leaves_promotion_free_lines_alone(self):
        line = ["Nxe5", "d4", "Nc6"]
        assert exchange_window(line) == line

    def test_promotion_first_yields_nothing_to_measure(self):
        assert exchange_window(["b8=Q", "Kf8"]) == []


class TestReplay:
    def test_returns_board_after_line(self):
        board = replay(HANG_REPLY_FEN, ["Nxe5"])
        assert board is not None
        assert board.piece_at(chess.E5) == chess.Piece(chess.KNIGHT, chess.BLACK)

    def test_illegal_line_is_none_not_an_exception(self):
        assert replay(HANG_REPLY_FEN, ["Qxh8"]) is None


class TestHangsMaterial:
    def test_flags_a_hung_knight(self):
        reply = move(ply=2, side="black", fen_before=HANG_REPLY_FEN, pv=["Nxe5"])
        tags = tag_move(move(), reply)
        hang = [t for t in tags if t.motif == "hangs_material"]
        assert len(hang) == 1
        assert "Nxe5" in hang[0].detail
        assert "320cp" in hang[0].detail

    def test_ignores_moves_the_engine_did_not_punish(self):
        # The motif classifies *how* a move was bad; cp_loss decides *whether* it was.
        reply = move(ply=2, side="black", fen_before=HANG_REPLY_FEN, pv=["Nxe5"])
        tags = tag_move(move(cp_loss=40), reply)
        assert not [t for t in tags if t.motif == "hangs_material"]

    def test_needs_a_capture_to_open_the_refutation(self):
        reply = move(ply=2, side="black", fen_before=HANG_REPLY_FEN, pv=["d6"])
        tags = tag_move(move(), reply)
        assert not [t for t in tags if t.motif == "hangs_material"]

    def test_last_move_of_a_game_has_no_reply_to_read(self):
        assert tag_move(move(), None) == []


class TestMissedCapture:
    def test_flags_a_free_queen_left_on_the_board(self):
        m = move(
            san="h3", best_san="Rxd8", fen_before=MISSED_FEN, pv=["Rxd8"], cp_loss=800
        )
        tags = tag_move(m, None)
        missed = [t for t in tags if t.motif == "missed_capture"]
        assert len(missed) == 1
        assert "900cp" in missed[0].detail

    def test_silent_when_the_student_played_the_capture(self):
        m = move(san="Rxd8", best_san="Rxd8", fen_before=MISSED_FEN, pv=["Rxd8"])
        assert not [t for t in tag_move(m, None) if t.motif == "missed_capture"]

    def test_silent_when_the_engine_preference_is_quiet(self):
        m = move(san="h3", best_san="Kg2", fen_before=MISSED_FEN, pv=["Kg2"])
        assert not [t for t in tag_move(m, None) if t.motif == "missed_capture"]


class TestAllowsFork:
    def test_flags_a_knight_hitting_king_and_rook(self):
        reply = move(ply=2, side="black", fen_before=FORK_REPLY_FEN, best_san="Nf2")
        tags = tag_move(move(side="white"), reply)
        fork = [t for t in tags if t.motif == "allows_fork"]
        assert len(fork) == 1
        assert "your king" in fork[0].detail
        assert "R on h1" in fork[0].detail

    def test_one_target_is_not_a_fork(self):
        # Same knight leap with the rook removed leaves only the king attacked.
        lone_king = "4k3/8/8/8/4n3/8/8/3K4 b - - 0 1"
        reply = move(ply=2, side="black", fen_before=lone_king, best_san="Nf2")
        assert not [t for t in tag_move(move(), reply) if t.motif == "allows_fork"]


class TestBackRank:
    def test_flags_a_rook_landing_behind_an_unmoved_pawn_shield(self):
        reply = move(ply=2, side="white", fen_before=BACK_RANK_REPLY_FEN, best_san="Re8")
        tags = tag_move(move(side="black"), reply)
        back = [t for t in tags if t.motif == "back_rank"]
        assert len(back) == 1
        assert "g8" in back[0].detail

    def test_luft_means_no_weakness(self):
        # Identical position with h7 advanced to h6: the king can breathe, so no tag.
        with_luft = "6k1/5pp1/7p/8/8/8/5PPP/4R1K1 w - - 0 1"
        reply = move(ply=2, side="white", fen_before=with_luft, best_san="Re8")
        assert not [t for t in tag_move(move(side="black"), reply) if t.motif == "back_rank"]

    def test_a_minor_piece_on_the_back_rank_is_not_a_back_rank_threat(self):
        knight = "6k1/5ppp/8/8/8/8/5PPP/4N1K1 w - - 0 1"
        reply = move(ply=2, side="white", fen_before=knight, best_san="Nd3")
        assert not [t for t in tag_move(move(side="black"), reply) if t.motif == "back_rank"]


class TestTagReport:
    def test_keys_by_ply_and_only_covers_the_coached_side(self):
        report = {
            "white": "w",
            "black": "b",
            "result": "0-1",
            "summary": {"acpl_white": 80.0, "acpl_black": 10.0},
            "moves": [
                move(ply=1, side="white", quality="blunder", fen_before=HANG_FEN,
                     san="Nxe5", cp_loss=300),
                move(ply=2, side="black", quality="good", fen_before=HANG_REPLY_FEN,
                     san="Nxe5", pv=["Nxe5"]),
            ],
        }
        tagged = tag_report(report, "white")
        assert list(tagged) == [1]  # black's move was fine, so it is not tagged
        assert [t.motif for t in tagged[1]] == ["hangs_material"]

    def test_clean_game_tags_nothing(self):
        report = {
            "summary": {"acpl_white": 8.0, "acpl_black": 9.0},
            "moves": [move(ply=1, quality="best"), move(ply=2, quality="good")],
        }
        assert tag_report(report, "white") == {}


@pytest.mark.parametrize("value", [MINOR_PIECE_VALUE])
def test_minor_piece_bar_sits_below_a_knight(value):
    """The material bar must let a knight through, or `hangs_material` never fires."""
    assert value < 320


# White plays the waiting move h3 and leaves e4 hanging to Nf6.
PAWN_FEN = "rnbqkb1r/pppp1ppp/5n2/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 1"
PAWN_REPLY_FEN = "rnbqkb1r/pppp1ppp/5n2/8/4P3/7P/PPPP1PP1/RNBQKBNR b KQkq - 0 1"


class TestDropsPawn:
    """Sub-minor-piece losses were the largest untagged group across 25 amateur games."""

    def test_flags_a_hung_pawn(self):
        m = move(san="h3", fen_before=PAWN_FEN, cp_loss=110, quality="inaccuracy")
        reply = move(ply=2, side="black", fen_before=PAWN_REPLY_FEN, pv=["Nxe4"])
        tags = [t for t in tag_move(m, reply) if t.motif == "drops_pawn"]
        assert len(tags) == 1
        assert "100cp" in tags[0].detail

    def test_a_pawn_is_not_reported_as_hanging_a_piece(self):
        m = move(san="h3", fen_before=PAWN_FEN, cp_loss=110)
        reply = move(ply=2, side="black", fen_before=PAWN_REPLY_FEN, pv=["Nxe4"])
        assert not [t for t in tag_move(m, reply) if t.motif == "hangs_material"]

    def test_a_piece_is_not_downgraded_to_a_pawn(self):
        reply = move(ply=2, side="black", fen_before=HANG_REPLY_FEN, pv=["Nxe5"])
        motifs = {t.motif for t in tag_move(move(), reply)}
        assert "hangs_material" in motifs
        assert "drops_pawn" not in motifs

    def test_the_pawn_bar_is_lower_than_the_piece_bar_but_still_real(self):
        reply = move(ply=2, side="black", fen_before=PAWN_REPLY_FEN, pv=["Nxe4"])
        # 110cp of engine-confirmed damage clears the pawn bar...
        assert [t for t in tag_move(move(san="h3", fen_before=PAWN_FEN, cp_loss=110), reply)]
        # ...but a move the engine barely marks down is still not a dropped pawn.
        assert not [t for t in tag_move(move(san="h3", fen_before=PAWN_FEN, cp_loss=30), reply)]
