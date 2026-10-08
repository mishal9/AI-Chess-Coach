"""Coaching prompt construction.

The engine report (a plain dict from :meth:`engine.analyzer.GameReport.to_dict`) is
turned into a compact, deterministic *facts* block and paired with a system prompt that
constrains the model to those facts. Everything here is pure — no Stockfish, no model — so
it can be unit-tested directly, and so the coach can run from a saved JSON report just as
well as from a live analysis.
"""

from __future__ import annotations

import chess

from engine.report import (  # noqa: F401 - re-exported; eval/ and training/ read them here
    MISTAKE_QUALITIES,
    choose_coached_side,
    coachable_mistakes,
    move_label,
    opponent_of,
)
from engine.scoring import MATE_CP, MoveQuality

# Average centipawn loss at/below which a game with no flagged mistakes is "clean".
_CLEAN_ACPL = 20.0

SYSTEM_PROMPT = """\
You are a warm, encouraging but honest chess coach. A chess engine has already \
analyzed the student's game and given you the objective facts below. Your job is to \
turn those facts into clear, human coaching.

STRICT GROUNDING RULES (a small model tends to hallucinate chess — do not):
- You may ONLY name moves that appear verbatim in the facts. Never introduce any other \
move number or notation (e.g. do not write "16...Nbd7" or "25.Qxf3" unless that exact \
move is listed). If it isn't in the facts, you don't know it happened.
- Never invent evaluations, variations, tactics ("a fork", "a pin"), sacrifices, or \
threats that are not stated. When unsure, say less.
- If the facts list NO specific mistakes, do not cite any moves at all. Give general \
guidance based only on the summary numbers, and say plainly that there was no single \
big error.

COACHING (once grounded):
- Lead with the single most important listed mistake: name it, explain in plain \
language why it was costly, and say what the recommended move achieves instead.
- Then briefly cover the other listed mistakes and point out any recurring pattern \
(e.g. hanging pieces, weakening the king, missing tactics) — but only patterns the \
listed moves actually support.
- End with one or two concrete, actionable things to work on.
- Be concise: a few short paragraphs, no move-by-move dump. Speak directly to the \
student ("you"). Do not restate the raw numbers mechanically — interpret them.

IF A "PLAYER HISTORY" SECTION IS PRESENT:
It is structured data about the student's PAST games, written as rows of \
`value | value | value` under a header row naming the columns. Read it as a table, and \
write about it in your own words — never echo the rows back as a table.
- It contains NO moves. The moves in this game's facts are the only moves you may name.
- Use its numbers exactly as given. Never inflate a count or a percentage.
- A `pattern` row's `status` says how to treat it: `recurring` is a genuine habit, worth \
naming and connecting to this game ("this is the fourth time"). `once_only` has happened \
a single time — mention it as a one-off if useful, never as a weakness.
- The trend table's `verdict` says whether the change is real: `improving` or `declining` \
may be described as a direction of travel. `unclear` means the difference is within normal \
game-to-game variation — you may state the numbers, but you must NOT tell the student they \
are getting better or worse.
- If no `pattern` rows are present, no tactical pattern has been tagged yet; the past \
mistakes were positional. Say so plainly rather than implying a pattern exists.
- If this game's mistakes match no listed pattern, say that too — it is useful news, not a \
gap to paper over."""


POSITION_SYSTEM_PROMPT = """\
You are a warm, encouraging but honest chess coach. A chess engine has already \
analyzed ONE key moment from the student's game and given you the objective facts \
below. Your job is to coach the student on this single moment only.

STRICT GROUNDING RULES (a small model tends to hallucinate chess — do not):
- The ONLY moves you may name are the ones listed in the facts: the move the student \
played, the move the engine preferred, and the moves in the engine lines given. Never \
introduce any other move number or notation. If it isn't in the facts, you don't know it \
happened.
- The facts list where every piece stands before the move and what the move captured. \
Describe the board only as listed there; never place a piece anywhere else.
- The facts list which pieces are attacked (with attacker and defender counts) and what \
each capture in the engine lines takes, with the material at the end of each line. Call \
a piece attacked, hanging or defended, or say who wins material, only as listed there. \
The engine evaluation says who stands better; a line that ends on a capture may stop \
before the recapture and show the wrong side ahead on material, so trust the evaluation.
- Never invent evaluations, variations, tactics ("a fork", "a pin"), sacrifices, \
or threats that the board and the engine lines do not show. When unsure, say less.

COACHING (once grounded):
- One or two short paragraphs, speaking directly to the student ("you").
- Explain in plain language why the played move was costly and what the recommended \
move achieves instead — the reusable idea behind it, not a restatement of the numbers.
- Do not summarize the rest of the game; stay on this moment."""


def _mistake_line(m: dict) -> str:
    label = move_label(m["move_number"], m["side"])
    symbol = MoveQuality(m["quality"]).symbol
    best = ""
    if m.get("best_san") and m["best_san"] != m["san"]:
        best = f" the engine preferred {m['best_san']};"
    win_pct = round(m["win_prob_loss"] * 100)
    return (
        f"- {label}{m['san']}{symbol} ({m['quality']}):{best} "
        f"cost about {win_pct}% win probability (cp loss {m['cp_loss']})."
    )


def format_report_facts(
    report: dict, coached_side: str, max_mistakes: int = 6, profile: str | None = None
) -> str:
    """Render the engine report as a compact facts block for the coached side.

    ``profile`` is an optional plain-text summary of the student's past games (see
    :func:`memory.profile.format_profile`). It is appended *inside* the facts block on
    purpose: :mod:`eval.grounding` reconstructs this block to decide which moves the coach
    was licensed to cite, so history that lived outside it would be invisible to the
    metric. The profile renderer is required to name no moves, which keeps that licence
    exactly as wide as it was before.

    With ``profile=None`` the output is byte-identical to the pre-memory version, so
    existing reports and eval baselines stay comparable.
    """
    summary = report["summary"]
    opponent = opponent_of(coached_side)
    player_name = report.get(coached_side, "?")
    opponent_name = report.get(opponent, "?")

    your_acpl = summary[f"acpl_{coached_side}"]
    opp_acpl = summary[f"acpl_{opponent}"]

    lines = [
        f"Game: White ({report.get('white', '?')}) vs "
        f"Black ({report.get('black', '?')}), result {report.get('result', '*')}.",
        f"Opening: {report.get('eco', '?')} {report.get('opening', '?')}.",
        f"You are coaching the {coached_side.upper()} player "
        f"({player_name}); the opponent is {opponent_name}.",
        "",
        "Objective engine summary:",
        f"- Your average centipawn loss: {your_acpl} "
        f"(opponent: {opp_acpl}; lower is better).",
        f"- Across the whole game: {summary['blunders']} blunders, "
        f"{summary['mistakes']} mistakes, {summary['inaccuracies']} inaccuracies "
        "(both sides combined).",
    ]

    # Notable mistakes by the coached side only, worst (highest win-prob loss) first.
    mistakes = coachable_mistakes(report, coached_side)[:max_mistakes]

    lines.append("")
    if mistakes:
        lines.append("Your most costly moves (worst first):")
        lines.extend(_mistake_line(m) for m in mistakes)
    elif your_acpl <= _CLEAN_ACPL:
        lines.append(
            "You made no flagged inaccuracies, mistakes, or blunders, and your average "
            "loss was low — a genuinely clean game."
        )
    else:
        # No single flagged error, but the average loss is high: the player was ground
        # down by many small imprecisions rather than one big blunder (e.g. defending a
        # worse position). Say that, so the coach doesn't wrongly call it a clean game.
        lines.append(
            "You had no single flagged blunder or mistake, but your average loss is "
            "high: you lost ground gradually through many small imprecisions rather "
            "than one big error — likely defending a steadily worse position."
        )

    if profile:
        lines.append("")
        lines.append("PLAYER HISTORY (past games; structured rows, no moves):")
        lines.append(profile)

    return "\n".join(lines)


def build_messages(
    report: dict,
    coached_side: str | None = None,
    max_mistakes: int = 6,
    profile: str | None = None,
) -> list[dict]:
    """Build the ``[system, user]`` chat messages for coaching one side of a game.

    If ``coached_side`` is ``None``, the worse-playing side is chosen automatically.
    ``profile`` optionally carries the student's history; see
    :func:`format_report_facts`.
    """
    if coached_side is None:
        coached_side = choose_coached_side(report)
    elif coached_side not in ("white", "black"):
        raise ValueError(f"coached_side must be 'white' or 'black', got {coached_side!r}")

    facts = format_report_facts(report, coached_side, max_mistakes, profile)
    user_prompt = (
        "Here is the engine analysis of the game. Coach the student based on it.\n\n"
        f"{facts}"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


_PIECE_ORDER = (chess.KING, chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT, chess.PAWN)
_PIECE_VALUES = {chess.QUEEN: 9, chess.ROOK: 5, chess.BISHOP: 3, chess.KNIGHT: 3, chess.PAWN: 1}


def _side_pieces(board: chess.Board, color: chess.Color) -> str:
    """"king on g1, rook on a1, pawn on a2, ..." — one "<piece> on <square>" per piece.

    Every square follows "on", which :mod:`eval.grounding` reads as a location, so the
    board licenses no move citations; only the listed lines below do.
    """
    parts = []
    for piece_type in _PIECE_ORDER:
        for square in sorted(board.pieces(piece_type, color)):
            parts.append(f"{chess.piece_name(piece_type)} on {chess.square_name(square)}")
    return ", ".join(parts)


def _material(board: chess.Board, color: chess.Color) -> int:
    return sum(len(board.pieces(p, color)) * v for p, v in _PIECE_VALUES.items())


def _numbered_line(board: chess.Board, sans: list[str], you: chess.Color) -> str:
    """Render a SAN list as numbered notation from ``board``, each capture marked with what
    it takes, and the material once the line is played out::

        20...Rfc8 21.Bxe6 (takes your queen) Rxc5 (takes their queen); material at the end:
        you 18, opponent 19

    Stops at the first move that will not parse, as :func:`engine.analyzer.pv_to_san` does.
    """
    board = board.copy()
    parts = []
    last_was_capture = False
    for i, san in enumerate(sans):
        try:
            move = board.parse_san(san)
        except ValueError:
            break
        text = board.san(move)
        if board.turn == chess.WHITE:
            text = f"{board.fullmove_number}.{text}"
        elif i == 0:
            text = f"{board.fullmove_number}...{text}"
        if board.is_capture(move):
            whose = "their" if board.turn == you else "your"
            taken = (chess.PAWN if board.is_en_passant(move)
                     else board.piece_at(move.to_square).piece_type)
            text += f" (takes {whose} {chess.piece_name(taken)})"
        last_was_capture = board.is_capture(move)
        parts.append(text)
        board.push(move)
    if not parts:
        return ""
    # A line cut off right after a capture usually stops before the recapture, so its
    # material count can show the wrong side ahead. Say so rather than drop the count.
    cut = " (the line ends on a capture; a recapture may follow)" if last_was_capture else ""
    return (f"{' '.join(parts)}; material at the end{cut}: you {_material(board, you)}, "
            f"opponent {_material(board, not you)}")


def _eval_text(white_cp: int, you: chess.Color) -> str:
    """A White-POV centipawn score as pawns from the coached side's view ("+0.4")."""
    cp = white_cp if you == chess.WHITE else -white_cp
    if abs(cp) >= MATE_CP - 1000:  # mate scores are ±(MATE_CP - N)
        return "a forced mate for you" if cp > 0 else "a forced mate for the opponent"
    return f"{cp / 100:+.1f}"


def _under_attack(board: chess.Board, color: chess.Color) -> str:
    """"knight on b4 (attackers 1, defenders 0), ..." for ``color``'s attacked pieces.

    Kings are left out (a check is stated where it happens). Counts are direct attackers
    only — no pins, x-rays or exchange arithmetic — which is all the coach needs to stop
    calling a defended piece hanging, or an unattacked one attacked.
    """
    parts = []
    for piece_type in _PIECE_ORDER[1:]:
        for square in sorted(board.pieces(piece_type, color)):
            attackers = len(board.attackers(not color, square))
            if attackers:
                defenders = len(board.attackers(color, square))
                parts.append(f"{chess.piece_name(piece_type)} on {chess.square_name(square)} "
                             f"(attackers {attackers}, defenders {defenders})")
    return ", ".join(parts) or "none"


def _move_effect(board: chess.Board, san: str, capture_verb: str, check_phrase: str) -> str:
    """"captured the opponent's rook on f2 and gave check", or "" if ``san`` won't parse."""
    try:
        move = board.parse_san(san)
    except ValueError:
        return ""
    if board.is_en_passant(move):
        effects = [f"{capture_verb} a pawn en passant"]
    elif board.is_capture(move):
        taken = board.piece_at(move.to_square)
        effects = [
            f"{capture_verb} the opponent's {chess.piece_name(taken.piece_type)} on "
            f"{chess.square_name(move.to_square)}"
        ]
    else:
        effects = [f"{capture_verb} nothing"]
    if board.gives_check(move):
        effects.append(check_phrase)
    return " and ".join(effects)


def _board_lines(report: dict, coached_side: str, move: dict) -> list[str]:
    """The board, material, what the played move did, and the engine's lines.

    Built from the report alone (``fen_before`` and ``pv`` of this move and the next), so
    nothing here needs an engine. Without it the coach is asked *why* a move was bad with
    nothing but its name, and fills the gap with an invented position.
    """
    fen = move.get("fen_before")
    if not fen:
        return []
    board = chess.Board(fen)
    you = chess.WHITE if coached_side == "white" else chess.BLACK
    them = not you
    lines = [
        "",
        f"The position before your move ({coached_side.capitalize()} to move):",
        f"- Your pieces ({coached_side.capitalize()}): {_side_pieces(board, you)}.",
        f"- Opponent's pieces ({opponent_of(coached_side).capitalize()}): "
        f"{_side_pieces(board, them)}.",
        f"- Material (queen 9, rook 5, bishop 3, knight 3, pawn 1): you "
        f"{_material(board, you)}, opponent {_material(board, them)}.",
        f"- Your pieces under attack: {_under_attack(board, you)}.",
        f"- Opponent's pieces under attack: {_under_attack(board, them)}.",
    ]

    played = _move_effect(board, move["san"], "captured", "gave check")
    if played:
        lines.append(f"- Your move {move['san']} {played}.")
        after_board = board.copy()
        after_board.push_san(move["san"])
        lines.append(f"- After your move, your pieces under attack: "
                     f"{_under_attack(after_board, you)}.")
    if move.get("best_san") and move["best_san"] != move["san"]:
        preferred = _move_effect(board, move["best_san"], "would capture", "would give check")
        if preferred:
            lines.append(f"- The preferred move {move['best_san']} {preferred}.")

    if "eval_before" in move and "eval_after" in move:
        lines.append(
            f"- Engine evaluation (in pawns; + favours you): with the preferred move "
            f"{_eval_text(move['eval_before'], you)}, after your move "
            f"{_eval_text(move['eval_after'], you)}."
        )

    pv = move.get("pv") or []
    if pv and move.get("best_san") and move["best_san"] != move["san"]:
        preferred = _numbered_line(board, pv, you)
        if preferred:
            lines.append(f"- Engine's preferred line from here: {preferred}")

    after = next((m for m in report.get("moves", []) if m.get("ply") == move.get("ply", -1) + 1),
                 None)
    if after and after.get("pv") and after.get("fen_before"):
        refutation = _numbered_line(chess.Board(after["fen_before"]), after["pv"], you)
        if refutation:
            lines.append(f"- Engine's best line after your move: {refutation}")
    return lines


def format_position_facts(report: dict, coached_side: str, move: dict) -> str:
    """Render ONE critical position as a tight facts block.

    ``move`` is one entry of ``report["moves"]`` (typically from
    :func:`coachable_mistakes`). Names the move played, the engine's preference and the
    engine's two lines (from the position, and after the move played), plus the board
    before the move — so the coach can explain *why* from the position rather than
    invent one. No other move of the game appears.
    """
    opponent = opponent_of(coached_side)
    return "\n".join(
        [
            f"Game context: White ({report.get('white', '?')}) vs "
            f"Black ({report.get('black', '?')}), result {report.get('result', '*')}. "
            f"Opening: {report.get('eco', '?')} {report.get('opening', '?')}.",
            f"You are coaching the {coached_side.upper()} player "
            f"({report.get(coached_side, '?')}); the opponent is "
            f"{report.get(opponent, '?')}.",
            "",
            "The moment:",
            _mistake_line(move),
            *_board_lines(report, coached_side, move),
        ]
    )


def build_position_messages(report: dict, coached_side: str, move: dict) -> list[dict]:
    """Build the ``[system, user]`` chat messages for coaching one critical position."""
    if coached_side not in ("white", "black"):
        raise ValueError(f"coached_side must be 'white' or 'black', got {coached_side!r}")
    facts = format_position_facts(report, coached_side, move)
    user_prompt = (
        "Here is the engine analysis of one key moment from the game. "
        "Coach the student on it.\n\n"
        f"{facts}"
    )
    return [
        {"role": "system", "content": POSITION_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
