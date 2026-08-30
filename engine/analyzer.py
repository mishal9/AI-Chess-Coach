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

import re
from dataclasses import dataclass, field

import chess
import chess.engine
import chess.pgn

from engine.scoring import (
    MATE_CP,
    MoveQuality,
    capped_centipawn_loss,
    centipawn_loss,
    classify,
    mate_to_cp,
    win_prob_loss,
)
from engine.stockfish import find_stockfish

DEFAULT_DEPTH = 15

# chess.com names openings only in an ECOUrl, whose slug often carries the defining
# variation as a move suffix: ".../Petrovs-Defense-3.d3-Nc6". Everything from the first
# move number onward is that suffix.
_VARIATION_SUFFIX_RE = re.compile(r"\s+\d+\.")

# How much of the engine's principal variation to keep per move. Long enough to show why
# a move lost material (capture, recapture, and the follow-up), short enough that a report
# for a 60-move game stays a reasonable size.
MAX_PV_PLIES = 8


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
    cp_loss: int             # centipawns given up, mover's perspective (for display)
    win_prob_loss: float     # drop in mover's win probability; drives `quality`
    quality: MoveQuality
    fen_before: str          # position the move was played from
    pv: list[str] = field(default_factory=list)  # engine's best line from `fen_before`, SAN

    def to_dict(self) -> dict:
        """JSON-serialisable view (enum → its string value)."""
        return {
            "ply": self.ply,
            "move_number": self.move_number,
            "side": self.side,
            "san": self.san,
            "best_san": self.best_san,
            "eval_before": self.eval_before,
            "eval_after": self.eval_after,
            "cp_loss": self.cp_loss,
            "win_prob_loss": round(self.win_prob_loss, 4),
            "quality": self.quality.value,
            "fen_before": self.fen_before,
            "pv": self.pv,
        }


@dataclass
class GameReport:
    """Full objective report for one game."""

    white: str
    black: str
    result: str
    eco: str
    opening: str
    moves: list[MoveAnalysis] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Full JSON-serialisable report: headers, summary, and per-move analysis."""
        return {
            "white": self.white,
            "black": self.black,
            "result": self.result,
            "eco": self.eco,
            "opening": self.opening,
            "summary": self.summary,
            "moves": [m.to_dict() for m in self.moves],
        }

    @property
    def summary(self) -> dict:
        counts = {q: 0 for q in MoveQuality}
        loss_by_side = {"white": [], "black": []}
        worst: MoveAnalysis | None = None
        for m in self.moves:
            counts[m.quality] += 1
            # ACPL uses capped-eval cp-loss so decided positions don't skew the average.
            loss_by_side[m.side].append(
                capped_centipawn_loss(m.eval_before, m.eval_after, m.side == "white")
            )
            # "Worst" ranks by win-probability loss — the honest measure of damage done.
            if worst is None or m.win_prob_loss > worst.win_prob_loss:
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
                    "win_prob_loss": round(worst.win_prob_loss, 3),
                }
            ),
        }


def evaluate_position(
    engine: chess.engine.SimpleEngine,
    board: chess.Board,
    limit: chess.engine.Limit,
) -> tuple[int, list[chess.Move]]:
    """Return ``(white_pov_centipawns, principal_variation)`` for a position.

    The full PV — not just its first move — because it *is* the engine's tactical
    justification: the line that refutes a blunder shows what was actually lost, so
    downstream consumers don't have to re-derive the tactics by hand.

    Game-over positions are scored directly (Stockfish can't analyse them): a
    checkmate is ±MATE_CP depending on who is mated; other terminal states are 0.
    """
    if board.is_game_over():
        if board.is_checkmate():
            # The side to move has been mated.
            cp = -MATE_CP if board.turn == chess.WHITE else MATE_CP
            return cp, []
        return 0, []  # stalemate / insufficient material / draw

    info = engine.analyse(board, limit)
    pov = info["score"].white()  # normalize to White's perspective
    mate = pov.mate()
    cp = mate_to_cp(mate) if mate is not None else pov.score()
    return cp, list(info.get("pv") or [])[:MAX_PV_PLIES]


def opening_name(headers) -> str:
    """The opening's name from PGN headers, or ``"?"``.

    Lichess supplies ``Opening`` directly. chess.com supplies neither ``Opening`` nor a
    usable name — only an ``ECOUrl`` whose final path segment is a slug. That slug often
    ends in the defining variation ("Petrovs-Defense-3.d3-Nc6"), and **that suffix must
    go**: the opening is printed into the coach's facts block, which is exactly the set of
    moves ``eval.grounding`` licenses the coach to cite. Left in, it would authorize
    citing ``d3`` and ``Nc6`` in games where neither was played — and 11 of 27 slugs
    across a real chess.com account carry such a suffix.

    There is deliberately no fall back to ``Event``: that header holds "Live Chess" or
    "Rated Blitz game", which is not an opening and only looked like one.
    """
    name = (headers.get("Opening") or "").strip()
    if not name or name == "?":
        url = (headers.get("ECOUrl") or "").strip()
        if not url:
            return "?"
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        name = slug.replace("-", " ").strip()
    return _VARIATION_SUFFIX_RE.split(name, maxsplit=1)[0].strip() or "?"


def pv_to_san(board: chess.Board, pv: list[chess.Move]) -> list[str]:
    """Render a principal variation as SAN, stopping at the first illegal move.

    Defensive because a PV is only guaranteed legal for the position it came from, and
    a truncated or stale line should degrade to what it can render, not raise.
    """
    line: list[str] = []
    replay = board.copy(stack=False)
    for move in pv:
        if not replay.is_legal(move):
            break
        line.append(replay.san(move))
        replay.push(move)
    return line


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
            opening=opening_name(headers),
        )

        board = game.board()
        cur_eval, cur_pv = evaluate_position(engine, board, limit)

        ply = 0
        for move in game.mainline_moves():
            mover_is_white = board.turn == chess.WHITE
            eval_before = cur_eval
            best_move = cur_pv[0] if cur_pv else None
            san = board.san(move)
            best_san = board.san(best_move) if best_move else None
            pv_san = pv_to_san(board, cur_pv)
            fen_before = board.fen()

            played_best = best_move is not None and move == best_move

            board.push(move)
            ply += 1
            cur_eval, cur_pv = evaluate_position(engine, board, limit)

            if played_best:
                # You can't be blamed for playing the engine's own top choice. This also
                # sidesteps search-horizon artifacts where a forced/only move looks like a
                # huge swing simply because a mate becomes visible one ply deeper.
                loss = 0
                wp_loss = 0.0
            else:
                loss = centipawn_loss(eval_before, cur_eval, mover_is_white)
                wp_loss = win_prob_loss(eval_before, cur_eval, mover_is_white)
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
                    win_prob_loss=wp_loss,
                    quality=classify(wp_loss),
                    fen_before=fen_before,
                    pv=pv_san,
                )
            )
        return report
    finally:
        if owns_engine:
            engine.quit()
