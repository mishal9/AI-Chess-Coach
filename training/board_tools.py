"""Board tools the teacher can call while writing a position row.

The facts block answers questions decided in advance (who attacks what, what the lines
capture). The errors that survived every facts change were claims about relations the
block did not settle: "Qd5 defends your bishop on g2" through a pawn, "after Rxd6 you are
left with a knight against a rook". Tool-augmented generation lets the teacher check the
exact relation it is about to assert: on arXiv 2608.04240 it cut DeepSeek V4 Pro's
incorrect chess sub-claims from 36.7% to 14.4%.

Every tool is deterministic python-chess over the three positions the facts describe:
before the move, after the move played, after the preferred move. Nothing here needs an
engine. The student never sees these tools; they only make the teacher's prose truer.
"""

from __future__ import annotations

import json

import chess

from coach import prompts

POSITIONS = ("before_your_move", "after_your_move", "after_preferred_move")

_POSITION_PARAM = {
    "type": "string",
    "enum": list(POSITIONS),
    "description": "which position to look at",
}
_SQUARE_PARAM = {"type": "string", "description": "a square such as e4"}

TOOLS = [
    {"type": "function", "function": {
        "name": "piece_at",
        "description": "What stands on a square.",
        "parameters": {"type": "object", "properties": {
            "square": _SQUARE_PARAM, "position": _POSITION_PARAM},
            "required": ["square", "position"]},
    }},
    {"type": "function", "function": {
        "name": "attackers_and_defenders",
        "description": "The piece on a square, every opposing piece that attacks it and every "
                       "friendly piece that defends it (direct, no x-rays).",
        "parameters": {"type": "object", "properties": {
            "square": _SQUARE_PARAM, "position": _POSITION_PARAM},
            "required": ["square", "position"]},
    }},
    {"type": "function", "function": {
        "name": "reaches",
        "description": "Whether the piece on one square attacks or defends another square, "
                       "and if not, what blocks it or why.",
        "parameters": {"type": "object", "properties": {
            "from_square": _SQUARE_PARAM, "to_square": _SQUARE_PARAM,
            "position": _POSITION_PARAM},
            "required": ["from_square", "to_square", "position"]},
    }},
    {"type": "function", "function": {
        "name": "play_line",
        "description": "Play moves (SAN, in order) from a position: each move with what it "
                       "captures, and the material at the end. Reports the first illegal move.",
        "parameters": {"type": "object", "properties": {
            "moves": {"type": "array", "items": {"type": "string"}},
            "position": _POSITION_PARAM},
            "required": ["moves", "position"]},
    }},
]


def _describe(board: chess.Board, square: chess.Square) -> str:
    piece = board.piece_at(square)
    if piece is None:
        return f"{chess.square_name(square)} is empty"
    color = "White" if piece.color == chess.WHITE else "Black"
    return f"{color} {chess.piece_name(piece.piece_type)} on {chess.square_name(square)}"


def _named(board: chess.Board, squares) -> str:
    return ", ".join(_describe(board, s) for s in sorted(squares)) or "none"


class BoardTools:
    """The tool executor for one position row."""

    def __init__(self, report: dict, coached_side: str, move: dict):
        before = chess.Board(move["fen_before"])
        self.you = chess.WHITE if coached_side == "white" else chess.BLACK
        self.boards = {"before_your_move": before}
        for name, san in (("after_your_move", move.get("san")),
                          ("after_preferred_move", move.get("best_san"))):
            if san:
                after = before.copy(stack=False)
                try:
                    after.push_san(san)
                except ValueError:
                    continue
                self.boards[name] = after
        self.calls = 0

    def _board(self, position: str) -> chess.Board:
        if position not in self.boards:
            raise ValueError(f"unknown position {position!r}; use one of {list(self.boards)}")
        return self.boards[position]

    def piece_at(self, square: str, position: str) -> str:
        return _describe(self._board(position), chess.parse_square(square))

    def attackers_and_defenders(self, square: str, position: str) -> str:
        board, sq = self._board(position), chess.parse_square(square)
        piece = board.piece_at(sq)
        if piece is None:
            return (f"{square} is empty; White pieces attacking it: "
                    f"{_named(board, board.attackers(chess.WHITE, sq))}; Black pieces "
                    f"attacking it: {_named(board, board.attackers(chess.BLACK, sq))}")
        return (f"{_describe(board, sq)}; attacked by: "
                f"{_named(board, board.attackers(not piece.color, sq))}; defended by: "
                f"{_named(board, board.attackers(piece.color, sq))}")

    def reaches(self, from_square: str, to_square: str, position: str) -> str:
        board = self._board(position)
        a, b = chess.parse_square(from_square), chess.parse_square(to_square)
        piece = board.piece_at(a)
        if piece is None:
            return f"{from_square} is empty"
        who = _describe(board, a)
        if b in board.attacks(a):
            target = board.piece_at(b)
            verb = ("defends" if target and target.color == piece.color
                    else "attacks" if target else "covers")
            return f"yes: the {who} {verb} {to_square}"
        between = chess.SquareSet(chess.between(a, b))
        if piece.piece_type in (chess.QUEEN, chess.ROOK, chess.BISHOP) and between:
            # Same line: say whether this piece moves along it and what stands in the way.
            same_file_or_rank = chess.square_file(a) == chess.square_file(b) or \
                chess.square_rank(a) == chess.square_rank(b)
            slides = (piece.piece_type == chess.QUEEN
                      or (piece.piece_type == chess.ROOK) == same_file_or_rank)
            blockers = [s for s in between if board.piece_at(s)]
            if slides and blockers:
                return f"no: the {who} is blocked by the {_describe(board, blockers[0])}"
        return f"no: the {who} does not reach {to_square}"

    def play_line(self, moves: list[str], position: str) -> str:
        board = self._board(position).copy(stack=False)
        for i, san in enumerate(moves):
            try:
                board.parse_san(san)
            except ValueError:
                played = prompts._numbered_line(self._board(position), moves[:i], self.you)
                return (f"{san} is not legal there" +
                        (f" (after {played.split(';')[0]})" if played else ""))
            board.push_san(san)
        return prompts._numbered_line(self._board(position), moves, self.you) or "no moves"

    def run(self, name: str, arguments: str) -> str:
        """Run one tool call; errors come back as text so the model can correct itself."""
        self.calls += 1
        try:
            args = json.loads(arguments or "{}")
            fn = {"piece_at": self.piece_at,
                  "attackers_and_defenders": self.attackers_and_defenders,
                  "reaches": self.reaches, "play_line": self.play_line}[name]
            return fn(**args)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return f"error: {exc}"
