"""Stockfish-backed per-move analysis of a whole game.

Replays a game move by move, asks Stockfish to evaluate each resulting position,
and uses :mod:`engine.scoring` to turn the eval swings into centipawn loss and
move-quality labels. The result is a structured :class:`GameReport` — the objective
"what went wrong" that the LLM coach will later explain.

Efficiency note: the position *after* move *i* is the same as the position *before*
move *i+1*, so we evaluate each position exactly once and reuse it for both the
move that created it and the move that follows.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import chess
import chess.engine
import chess.pgn

from engine.scoring import MATE_CP, MoveQuality, centipawn_loss, classify, mate_to_cp
from engine.stockfish import find_stockfish

DEFAULT_DEPTH = 15


@dataclass
class MoveAnalysis:
    """Analysis of a single played move."""

    ply: int                 # half-move index, 1-based
    move_number: int         # full-move number (1, 1, 2, 2, ...)
    side: str                # "white" or "black"
    san: str                 # the move actually played
    best_san: str | None     # Stockfish's preferred move in that position
    eval_before: int         # White-POV cp, best play, before the move
    eval_after: int          # White-POV cp after the move was played
    cp_loss: int             # centipawns given up, mover's perspective
    quality: MoveQuality
    fen_before: str          # position the move was played from


@dataclass
class GameReport:
    """Full objective report for one game."""

    white: str
    black: str
    result: str
    eco: str
    opening: str
    moves: list[MoveAnalysis] = field(default_factory=list)

    @property
    def summary(self) -> dict:
        counts = {q: 0 for q in MoveQuality}
        loss_by_side = {"white": [], "black": []}
        worst: MoveAnalysis | None = None
        for m in self.moves:
            counts[m.quality] += 1
            loss_by_side[m.side].append(m.cp_loss)
            if worst is None or m.cp_loss > worst.cp_loss:
                worst = m

        def avg(xs: list[int]) -> float:
            return round(sum(xs) / len(xs), 1) if xs else 0.0

        return {
            "blunders": counts[MoveQuality.BLUNDER],
            "mistakes": counts[MoveQuality.MISTAKE],
            "inaccuracies": counts[MoveQuality.INACCURACY],
            "acpl_white": avg(loss_by_side["white"]),  # avg centipawn loss
            "acpl_black": avg(loss_by_side["black"]),
            "worst_move": (
                None
                if worst is None
                else {
                    "move_number": worst.move_number,
                    "side": worst.side,
                    "played": worst.san,
                    "best": worst.best_san,
                    "cp_loss": worst.cp_loss,
                }
            ),
        }


def evaluate_position(
    engine: chess.engine.SimpleEngine,
    board: chess.Board,
    limit: chess.engine.Limit,
) -> tuple[int, chess.Move | None]:
    """Return ``(white_pov_centipawns, best_move)`` for a position.

    Game-over positions are scored directly (Stockfish can't analyse them): a
    checkmate is ±MATE_CP depending on who is mated; other terminal states are 0.
    """
    if board.is_game_over():
        if board.is_checkmate():
            # The side to move has been mated.
            cp = -MATE_CP if board.turn == chess.WHITE else MATE_CP
            return cp, None
        return 0, None  # stalemate / insufficient material / draw

    info = engine.analyse(board, limit)
    pov = info["score"].white()  # normalize to White's perspective
    mate = pov.mate()
    cp = mate_to_cp(mate) if mate is not None else pov.score()
    pv = info.get("pv")
    best = pv[0] if pv else None
    return cp, best


def analyze_game(
    game: chess.pgn.Game,
    depth: int = DEFAULT_DEPTH,
    engine: chess.engine.SimpleEngine | None = None,
) -> GameReport:
    """Analyze every move of ``game`` and return a structured report.

    If ``engine`` is not supplied, a Stockfish process is opened and closed here.
    """
    owns_engine = engine is None
    if owns_engine:
        engine = chess.engine.SimpleEngine.popen_uci(find_stockfish())

    try:
        limit = chess.engine.Limit(depth=depth)
        headers = game.headers
        report = GameReport(
            white=headers.get("White", "?"),
            black=headers.get("Black", "?"),
            result=headers.get("Result", "*"),
            eco=headers.get("ECO", "?"),
            opening=headers.get("Opening", headers.get("Event", "?")),
        )

        board = game.board()
        cur_eval, cur_best = evaluate_position(engine, board, limit)

        ply = 0
        for move in game.mainline_moves():
            mover_is_white = board.turn == chess.WHITE
            eval_before = cur_eval
            best_move = cur_best
            san = board.san(move)
            best_san = board.san(best_move) if best_move else None
            fen_before = board.fen()

            board.push(move)
            ply += 1
            cur_eval, cur_best = evaluate_position(engine, board, limit)

            loss = centipawn_loss(eval_before, cur_eval, mover_is_white)
            report.moves.append(
                MoveAnalysis(
                    ply=ply,
                    move_number=(ply + 1) // 2,
                    side="white" if mover_is_white else "black",
                    san=san,
                    best_san=best_san,
                    eval_before=eval_before,
                    eval_after=cur_eval,
                    cp_loss=loss,
                    quality=classify(loss),
                    fen_before=fen_before,
                )
            )
        return report
    finally:
        if owns_engine:
            engine.quit()
