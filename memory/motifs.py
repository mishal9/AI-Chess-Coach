"""Why a mistake was a mistake — motif tagging on top of the engine's own analysis.

:mod:`engine.analyzer` says *that* a move cost win probability. This says *what kind of
error it was*, so the same failure can be counted across many games ("you hang pieces
right after castling").

**The tactics are Stockfish's job, not ours.** Every move carries the engine's principal
variation, so "you hung a piece" is read off the refutation line the engine already
found at full depth — we replay it and count material. No exchange evaluation, no
threat detection, no tactical reasoning reimplemented in Python beside an engine that
does it better. What is left here is bookkeeping: replay, count, name.

The taxonomy is deliberately small and biased toward false negatives. An untagged
mistake costs a little signal; a wrongly tagged one puts a false claim in front of the
student, and the coach repeats it with a confident number attached. Every tag carries a
``detail`` string quoting the engine line that produced it, so a bad rule is visible.
"""

from __future__ import annotations

from dataclasses import dataclass

import chess

from engine.report import coachable_mistakes

# Centipawn values, for counting material on a board — not for simulating exchanges.
PIECE_VALUES: dict[int, int] = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
}

# The bar for "material": a minor piece. Below it, and down to a pawn, the loss is real
# but smaller, and gets its own motif rather than being discarded.
MINOR_PIECE_VALUE = 300
PAWN_VALUE = 100

# Corroboration bar. A motif only classifies *how* a move was bad; the engine's own
# centipawn loss decides *whether* it was. Requiring both means a truncated PV cannot
# invent a material loss on its own.
_MATERIAL_MISTAKE_CP = 200

# The same corroboration idea scaled to a pawn: demanding 200cp of confirmed damage for a
# ~100cp loss would hide every dropped pawn there is.
_PAWN_MISTAKE_CP = 80

# Non-king material on the board (both sides, centipawns) marking the phase boundaries.
_ENDGAME_MATERIAL = 2400
_OPENING_MATERIAL = 6000
_OPENING_MAX_PLY = 24


@dataclass(frozen=True)
class MotifTag:
    """One tagged reason a move was bad, with the engine evidence that triggered it."""

    motif: str
    detail: str

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.motif}: {self.detail}"


def material(board: chess.Board, color: chess.Color) -> int:
    """Total centipawn value of ``color``'s pieces (kings excluded)."""
    return sum(
        PIECE_VALUES.get(piece.piece_type, 0)
        for piece in board.piece_map().values()
        if piece.color == color
    )


def replay(fen: str, line: list[str]) -> chess.Board | None:
    """Board after playing ``line`` (SAN) from ``fen``, or ``None`` if it doesn't fit.

    A stored PV is only guaranteed legal for the position it was computed from, so an
    unplayable line means the caller's assumptions are wrong and the motif is skipped.
    """
    board = chess.Board(fen)
    for san in line:
        try:
            board.push_san(san)
        except (ValueError, AssertionError):
            return None
    return board


def _side_color(side: str) -> chess.Color:
    return chess.WHITE if side == "white" else chess.BLACK


def exchange_window(line: list[str]) -> list[str]:
    """The part of a PV that measures an exchange, cut before any promotion.

    A line that runs on to ``b8=Q`` is no longer describing a piece being taken; it is
    describing a pawn race being converted, and counting the new queen as "material
    lost" reports a hang at four times its real size.
    """
    for i, san in enumerate(line):
        if "=" in san:
            return line[:i]
    return line


def game_phase(fen: str, ply: int) -> str:
    """Classify a position as opening, middlegame, or endgame.

    Material is the primary signal; ply only guards the opening, so a wild game that
    sheds pieces by move 10 is still called a middlegame.
    """
    board = chess.Board(fen)
    total = material(board, chess.WHITE) + material(board, chess.BLACK)
    if total <= _ENDGAME_MATERIAL:
        return "endgame"
    if ply <= _OPENING_MAX_PLY and total >= _OPENING_MATERIAL:
        return "opening"
    return "middlegame"


def _tag_material_loss(move: dict, reply: dict | None) -> MotifTag | None:
    """Material the engine's refutation wins — a whole piece, or just a pawn.

    ``reply`` is the *next* ply's analysis, whose ``fen_before`` is the position the
    played move created and whose ``pv`` is the engine's punishment for it.

    One function rather than two because the measurement is identical and only the
    threshold differs; the size of the loss picks the motif. Pawns get a lower
    corroboration bar than pieces, in proportion to what they cost — a dropped pawn is
    around 100cp, so demanding 200cp of engine-confirmed damage would hide every one of
    them. Across 25 amateur games, sub-minor-piece losses were the single largest group
    of mistakes going untagged.
    """
    if reply is None:
        return None
    line = exchange_window(reply.get("pv") or [])
    if not line:
        return None

    start = chess.Board(reply["fen_before"])
    try:
        first = start.parse_san(line[0])
    except (ValueError, AssertionError):  # pragma: no cover - defensive
        return None
    if not start.is_capture(first):
        return None

    end = replay(reply["fen_before"], line)
    if end is None:
        return None

    mover = _side_color(move["side"])
    lost = material(start, mover) - material(end, mover)
    conceded = material(start, not mover) - material(end, not mover)
    net = lost - conceded

    if net >= MINOR_PIECE_VALUE:
        motif, corroboration = "hangs_material", _MATERIAL_MISTAKE_CP
    elif net >= PAWN_VALUE:
        motif, corroboration = "drops_pawn", _PAWN_MISTAKE_CP
    else:
        return None
    if move["cp_loss"] < corroboration:
        return None

    return MotifTag(
        motif,
        f"{line[0]} punishes {move['san']}; the engine line "
        f"{' '.join(line)} nets {net}cp of material",
    )


def _tag_missed_capture(move: dict) -> MotifTag | None:
    """Did the engine's own line open with a material-winning capture the student passed?"""
    best_san = move.get("best_san")
    if not best_san or best_san == move["san"]:
        return None
    line = exchange_window(move.get("pv") or [])
    if not line or line[0] != best_san:
        return None

    start = chess.Board(move["fen_before"])
    try:
        best = start.parse_san(best_san)
    except (ValueError, AssertionError):  # pragma: no cover - defensive
        return None
    if not start.is_capture(best):
        return None

    end = replay(move["fen_before"], line)
    if end is None:
        return None

    mover = _side_color(move["side"])
    gained = material(start, not mover) - material(end, not mover)
    given = material(start, mover) - material(end, mover)
    if gained - given < MINOR_PIECE_VALUE:
        return None
    return MotifTag(
        "missed_capture",
        f"{best_san} was there and wins {gained - given}cp "
        f"({' '.join(line)}); you played {move['san']}",
    )


def _tag_allows_fork(move: dict, reply: dict | None) -> MotifTag | None:
    """Does the opponent's best reply attack two valuable pieces at once?

    A target counts when taking it is plainly good: it is undefended, or it is worth
    more than the piece attacking it. That is the ordinary definition of a fork and
    needs only attack sets — no exchange simulation.
    """
    if reply is None:
        return None
    reply_san = reply.get("best_san")
    if not reply_san:
        return None

    after = chess.Board(reply["fen_before"])
    try:
        landed = after.push_san(reply_san).to_square
    except (ValueError, AssertionError):  # pragma: no cover - defensive
        return None
    forker = after.piece_at(landed)
    if forker is None:  # pragma: no cover - the piece just moved there
        return None
    forker_value = PIECE_VALUES.get(forker.piece_type, 0)

    victims: list[str] = []
    for square in after.attacks(landed):
        piece = after.piece_at(square)
        if piece is None or piece.color == forker.color:
            continue
        if piece.piece_type == chess.KING:
            victims.append("your king")
            continue
        value = PIECE_VALUES.get(piece.piece_type, 0)
        if value < MINOR_PIECE_VALUE:
            continue
        defended = bool(after.attackers(piece.color, square))
        if not defended or value > forker_value:
            victims.append(f"{piece.symbol().upper()} on {chess.square_name(square)}")

    if len(victims) < 2:
        return None
    return MotifTag("allows_fork", f"{reply_san} forks {' and '.join(victims)}")


def _tag_back_rank(move: dict, reply: dict | None) -> MotifTag | None:
    """Is the best reply a heavy piece hitting a back rank the king can't leave?

    Tagged only when the king is genuinely entombed — no empty flight square in front of
    it — so a routine rook lift onto an open back rank is not called a weakness.
    """
    if reply is None:
        return None
    reply_san = reply.get("best_san")
    if not reply_san:
        return None

    board = chess.Board(reply["fen_before"])
    try:
        landing = board.parse_san(reply_san)
    except (ValueError, AssertionError):  # pragma: no cover - defensive
        return None

    piece = board.piece_at(landing.from_square)
    if piece is None or piece.piece_type not in (chess.ROOK, chess.QUEEN):
        return None

    mover = _side_color(move["side"])
    back_rank = 0 if mover == chess.WHITE else 7
    if chess.square_rank(landing.to_square) != back_rank:
        return None

    king_square = board.king(mover)
    if king_square is None or chess.square_rank(king_square) != back_rank:
        return None

    escape_rank = 1 if mover == chess.WHITE else 6
    king_file = chess.square_file(king_square)
    for file in range(max(0, king_file - 1), min(8, king_file + 2)):
        if board.piece_at(chess.square(file, escape_rank)) is None:
            return None

    return MotifTag(
        "back_rank",
        f"{reply_san} hits the back rank while your king on "
        f"{chess.square_name(king_square)} has no luft",
    )


def tag_move(move: dict, reply: dict | None = None) -> list[MotifTag]:
    """Every motif that fits one analyzed move.

    ``move`` is an entry of ``report["moves"]``; ``reply`` is the *following* entry,
    which carries the engine's answer to the played move. It is ``None`` for the last
    move of a game, and the reply-based motifs simply don't fire.
    """
    tags = [
        _tag_material_loss(move, reply),
        _tag_missed_capture(move),
        _tag_allows_fork(move, reply),
        _tag_back_rank(move, reply),
    ]
    return [tag for tag in tags if tag is not None]


def tag_report(report: dict, coached_side: str) -> dict[int, list[MotifTag]]:
    """Tag every flagged mistake by ``coached_side``, keyed by ply.

    Mistake selection reuses :func:`engine.report.coachable_mistakes`, the one definition
    of "worth coaching on" the rest of the project already follows.
    """
    by_ply = {m["ply"]: m for m in report.get("moves", [])}
    return {
        mistake["ply"]: tag_move(mistake, by_ply.get(mistake["ply"] + 1))
        for mistake in coachable_mistakes(report, coached_side)
    }
