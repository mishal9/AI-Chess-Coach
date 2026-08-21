"""Coaching prompt construction.

The engine report (a plain dict from :meth:`engine.analyzer.GameReport.to_dict`) is
turned into a compact, deterministic *facts* block and paired with a system prompt that
constrains the model to those facts. Everything here is pure and dependency-free so it
can be unit-tested without an engine or a model, and so the coach can run from a saved
JSON report just as well as from a live analysis.
"""

from __future__ import annotations

# Move-quality string (as stored in the report dict) → chess annotation symbol.
# Kept local so this module needs nothing from the engine package.
_QUALITY_SYMBOL = {
    "blunder": "??",
    "mistake": "?",
    "inaccuracy": "?!",
    "good": "",
    "best": "",
}

# Qualities worth coaching on, worst first.
_MISTAKE_QUALITIES = ("blunder", "mistake", "inaccuracy")

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

IF A "YOUR HISTORY" SECTION IS PRESENT:
- It summarises the student's *past* games. The moves in this game's facts are the only \
moves you may name — the history section names none, and you must not invent any for it.
- You may connect this game's mistake to a listed history pattern, using the counts given \
("this is the fourth time"). Never inflate a count, never turn "twice" into "always", and \
never claim a pattern that is not listed.
- If a pattern is marked as seen only once, treat it as a one-off, not a weakness.
- If this game's mistakes do NOT match any listed pattern, say so plainly — that is useful \
news, not a gap to paper over."""


POSITION_SYSTEM_PROMPT = """\
You are a warm, encouraging but honest chess coach. A chess engine has already \
analyzed ONE key moment from the student's game and given you the objective facts \
below. Your job is to coach the student on this single moment only.

STRICT GROUNDING RULES (a small model tends to hallucinate chess — do not):
- The ONLY moves you may name are the ones listed in the facts: the move the student \
played and, if given, the move the engine preferred. Never introduce any other move \
number or notation. If it isn't in the facts, you don't know it happened.
- Never invent evaluations, variations, tactics ("a fork", "a pin"), sacrifices, \
board details, or threats that are not stated. When unsure, say less.

COACHING (once grounded):
- One or two short paragraphs, speaking directly to the student ("you").
- Explain in plain language why the played move was costly and what the recommended \
move achieves instead — the reusable idea behind it, not a restatement of the numbers.
- Do not summarize the rest of the game; stay on this moment."""


def _move_label(move_number: int, side: str) -> str:
    """'17.' for a White move, '17...' for a Black move."""
    return f"{move_number}." if side == "white" else f"{move_number}..."


def choose_coached_side(report: dict) -> str:
    """Pick which side to coach when the caller doesn't specify.

    Defaults to the side that played *worse* (higher average centipawn loss) — that's
    who has the most to learn. Ties break toward the side that lost the game, else White.
    """
    summary = report["summary"]
    acpl_white = summary["acpl_white"]
    acpl_black = summary["acpl_black"]
    if acpl_white != acpl_black:
        return "white" if acpl_white > acpl_black else "black"
    # Equal ACPL: coach whoever lost, if anyone.
    result = report.get("result", "*")
    if result == "0-1":
        return "white"
    if result == "1-0":
        return "black"
    return "white"


def coachable_mistakes(report: dict, coached_side: str) -> list[dict]:
    """The coached side's flagged mistakes, worst (highest win-prob loss) first.

    The single source of the "critical positions" ordering, shared by the whole-game
    facts block and the per-position distillation rows.
    """
    mistakes = [
        m
        for m in report.get("moves", [])
        if m["side"] == coached_side and m["quality"] in _MISTAKE_QUALITIES
    ]
    mistakes.sort(key=lambda m: m["win_prob_loss"], reverse=True)
    return mistakes


def _mistake_line(m: dict) -> str:
    label = _move_label(m["move_number"], m["side"])
    symbol = _QUALITY_SYMBOL.get(m["quality"], "")
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
    opponent = "black" if coached_side == "white" else "white"
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
        lines.append("YOUR HISTORY (past games, no moves — do not cite moves from here):")
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


def format_position_facts(report: dict, coached_side: str, move: dict) -> str:
    """Render ONE critical position as a tight facts block.

    ``move`` is one entry of ``report["moves"]`` (typically from
    :func:`coachable_mistakes`). Deliberately mentions only two moves — the one played
    and the engine's preference — so a perfectly grounded answer has nowhere to wander.
    """
    opponent = "black" if coached_side == "white" else "white"
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
