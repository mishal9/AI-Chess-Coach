"""What the stored games add up to — a player's recurring weaknesses.

Every number here is a ``GROUP BY`` over :mod:`memory.store`. That is the whole argument
for a relational store: "which mistake costs you most", "are you improving", and "how many
times now" are counting questions, and counting is what SQL is for.

The renderer emits facts and *statuses* (``recurring``/``once_only``, ``improving``/
``unclear``), not prose. Everything downstream is a coaching model whose whole job is
turning facts into language; writing sentences here would duplicate that job and do it
worse. How to speak about each status lives in the system prompt instead.

What stays computed here is every number, because the model provably gets chess facts
wrong often enough that a count it derived itself could not be trusted — and a wrong count
stated confidently is worse than no count at all.

Usage:
    python -m memory.profile --user mishal9
    python -m memory.profile --user mishal9 --last 20
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from dataclasses import dataclass, field
from math import sqrt
from statistics import variance

from memory.store import DEFAULT_DB, connect

# Below this many occurrences a motif is an incident, not a habit, and is reported as such.
MIN_OCCURRENCES_FOR_PATTERN = 2

# Splitting a window into halves needs enough games that each half means something.
MIN_GAMES_FOR_TREND = 6

# An opening needs repeat visits before its average says anything about the player.
MIN_GAMES_FOR_OPENING = 2

_MOTIF_LABELS = {
    "hangs_material": "leaving material hanging",
    "drops_pawn": "dropping a pawn",
    "missed_capture": "missing a material-winning capture",
    "allows_fork": "walking into forks",
    "back_rank": "back-rank weakness",
}


@dataclass(frozen=True)
class MotifStat:
    motif: str
    occurrences: int
    games: int
    win_prob_lost: float

    @property
    def label(self) -> str:
        return _MOTIF_LABELS.get(self.motif, self.motif.replace("_", " "))

    @property
    def is_pattern(self) -> bool:
        return self.occurrences >= MIN_OCCURRENCES_FOR_PATTERN

    @property
    def status(self) -> str:
        """``"recurring"`` or ``"once_only"`` — emitted as a field, not as prose.

        The distinction matters (one bad game is not a weakness) but saying so is the
        coaching model's job. We state which case this is; the system prompt says how to
        talk about each.
        """
        return "recurring" if self.is_pattern else "once_only"

    @property
    def avg_win_prob_lost(self) -> float:
        """Typical cost of one occurrence.

        Reported instead of the total because summed win-probability runs past 100% over
        a handful of games, and "costing 125% win probability" reads as a bug. The total
        still does the ranking; the average does the explaining.
        """
        return self.win_prob_lost / self.occurrences if self.occurrences else 0.0


@dataclass(frozen=True)
class PhaseStat:
    phase: str
    mistakes: int
    win_prob_lost: float

    @property
    def avg_win_prob_lost(self) -> float:
        return self.win_prob_lost / self.mistakes if self.mistakes else 0.0


@dataclass(frozen=True)
class OpeningStat:
    eco: str
    opening: str
    games: int
    acpl: float

    @property
    def name(self) -> str:
        """The opening as it is safe to print into a coaching prompt.

        A handful of opening names carry move notation ("King's Indian Attack, with e6").
        The profile is rendered *into the facts block*, and the grounding checker treats
        everything in that block as a move the coach is licensed to cite — so a name like
        that would quietly authorize citing ``e6`` in a game where it was never played.
        Rare enough (1 in 108 across the corpus) that dropping to the bare ECO code costs
        nothing and closes the hole.
        """
        from eval.grounding import extract_moves

        return f"{self.eco} {self.opening}" if not extract_moves(self.opening) else self.eco


@dataclass(frozen=True)
class Trend:
    earlier_games: int
    later_games: int
    earlier_mistakes_per_game: float
    later_mistakes_per_game: float
    earlier_acpl: float
    later_acpl: float
    earlier_damage_per_game: float
    later_damage_per_game: float
    # Per-game mistake counts behind the two means, kept so the noise floor can be
    # computed from the data instead of a guessed constant.
    earlier_counts: tuple[int, ...] = ()
    later_counts: tuple[int, ...] = ()

    @property
    def mistakes_delta(self) -> float:
        """Negative means fewer mistakes per game lately — improvement."""
        return round(self.later_mistakes_per_game - self.earlier_mistakes_per_game, 2)

    @property
    def acpl_delta(self) -> float:
        return round(self.later_acpl - self.earlier_acpl, 1)

    @property
    def damage_delta(self) -> float:
        """Change in win probability thrown away per game. Negative is improvement.

        Severity-weighted, so a blunder and an inaccuracy stop counting the same. This is
        the signal :attr:`direction` is judged on: the raw count flips on a threshold (a
        move at 0.099 vs 0.101 win-probability loss changes it by a whole unit), while
        damage moves smoothly with how badly you actually played.
        """
        return round(self.later_damage_per_game - self.earlier_damage_per_game, 3)

    @property
    def noise_floor(self) -> float:
        """Standard error of the difference in mistakes per game.

        Two halves of a short game history differ by chance alone. This is how much
        they'd typically differ *without* any real change, so a gap smaller than it is
        not evidence of anything.
        """
        if len(self.earlier_counts) < 2 or len(self.later_counts) < 2:
            return float("inf")
        earlier = variance(self.earlier_counts) / len(self.earlier_counts)
        later = variance(self.later_counts) / len(self.later_counts)
        return sqrt(earlier + later)

    @property
    def direction(self) -> str:
        """``"improving"``, ``"declining"``, or ``"unclear"``.

        Deliberately conservative. Telling a player they are getting worse on the strength
        of three extra mistakes across seven games is both wrong and discouraging, and
        this project has already been fooled twice by exactly this size of sample — the
        "concentrated weakness" reading that turned out to be noise, and the 6-game
        held-out set that had to grow to 29.

        The bar is one standard error: a weak test on purpose, because the question is
        only "is this worth mentioning at all", not "is this significant".
        """
        if abs(self.mistakes_delta) <= self.noise_floor:
            return "unclear"
        return "improving" if self.mistakes_delta < 0 else "declining"


@dataclass(frozen=True)
class PlayerProfile:
    user: str
    games: int
    mistakes: int
    acpl: float
    motifs: list[MotifStat] = field(default_factory=list)
    phases: list[PhaseStat] = field(default_factory=list)
    openings: list[OpeningStat] = field(default_factory=list)
    trend: Trend | None = None

    @property
    def is_empty(self) -> bool:
        return self.games == 0


def _window_ids(
    conn: sqlite3.Connection,
    user: str,
    last_n: int | None,
    exclude_game_id: int | None = None,
) -> list[int]:
    """Game ids in the reporting window, oldest first.

    Ordered by date where the PGN carried one, falling back to ingest order. Lichess and
    chess.com exports always date their games, so the fallback is for hand-made PGNs.

    ``exclude_game_id`` drops one game, which matters when coaching it: a history that
    counted the game under discussion would let "the fourth time" include itself.
    """
    rows = conn.execute(
        """
        SELECT id FROM games WHERE user_name = ?
        ORDER BY COALESCE(played_at, ''), id
        """,
        (user,),
    ).fetchall()
    ids = [row["id"] for row in rows if row["id"] != exclude_game_id]
    return ids[-last_n:] if last_n else ids


def _placeholders(ids: list[int]) -> str:
    return ",".join("?" * len(ids))


def _motif_stats(conn: sqlite3.Connection, ids: list[int]) -> list[MotifStat]:
    rows = conn.execute(
        f"""
        SELECT motifs.motif AS motif,
               COUNT(*) AS occurrences,
               COUNT(DISTINCT mistakes.game_id) AS games,
               SUM(mistakes.win_prob_loss) AS win_prob_lost
        FROM motifs
        JOIN mistakes ON mistakes.id = motifs.mistake_id
        WHERE mistakes.game_id IN ({_placeholders(ids)})
        GROUP BY motifs.motif
        ORDER BY win_prob_lost DESC
        """,
        ids,
    ).fetchall()
    return [
        MotifStat(
            motif=row["motif"],
            occurrences=row["occurrences"],
            games=row["games"],
            win_prob_lost=round(row["win_prob_lost"] or 0.0, 3),
        )
        for row in rows
    ]


def _phase_stats(conn: sqlite3.Connection, ids: list[int]) -> list[PhaseStat]:
    rows = conn.execute(
        f"""
        SELECT phase, COUNT(*) AS mistakes, SUM(win_prob_loss) AS win_prob_lost
        FROM mistakes
        WHERE game_id IN ({_placeholders(ids)})
        GROUP BY phase
        ORDER BY win_prob_lost DESC
        """,
        ids,
    ).fetchall()
    return [
        PhaseStat(
            phase=row["phase"],
            mistakes=row["mistakes"],
            win_prob_lost=round(row["win_prob_lost"] or 0.0, 3),
        )
        for row in rows
    ]


def _opening_stats(conn: sqlite3.Connection, ids: list[int]) -> list[OpeningStat]:
    rows = conn.execute(
        f"""
        SELECT eco, MIN(opening) AS opening, COUNT(*) AS games, AVG(acpl) AS acpl
        FROM games
        WHERE id IN ({_placeholders(ids)}) AND eco IS NOT NULL AND eco != '?'
        GROUP BY eco
        HAVING COUNT(*) >= ?
        ORDER BY acpl DESC
        """,
        [*ids, MIN_GAMES_FOR_OPENING],
    ).fetchall()
    return [
        OpeningStat(
            eco=row["eco"],
            opening=row["opening"] or "?",
            games=row["games"],
            acpl=round(row["acpl"] or 0.0, 1),
        )
        for row in rows
    ]


def _per_game_counts(conn: sqlite3.Connection, ids: list[int]) -> list[int]:
    """Flagged-mistake count for each game, individually.

    The per-game spread is what makes a noise floor computable; a mean alone cannot say
    how much two halves would differ by chance.
    """
    rows = conn.execute(
        f"""
        SELECT blunders + mistakes + inaccuracies AS total
        FROM games WHERE id IN ({_placeholders(ids)})
        """,
        ids,
    ).fetchall()
    return [row["total"] for row in rows]


def _half_stats(
    conn: sqlite3.Connection, ids: list[int]
) -> tuple[float, float, float, list[int]]:
    """``(mistakes_per_game, acpl, damage_per_game, per_game_counts)`` for a set of games."""
    row = conn.execute(
        f"""
        SELECT COUNT(*) AS games,
               COALESCE(SUM(blunders + mistakes + inaccuracies), 0) AS total,
               AVG(acpl) AS acpl
        FROM games WHERE id IN ({_placeholders(ids)})
        """,
        ids,
    ).fetchone()
    damage = conn.execute(
        f"""
        SELECT COALESCE(SUM(win_prob_loss), 0) AS damage
        FROM mistakes WHERE game_id IN ({_placeholders(ids)})
        """,
        ids,
    ).fetchone()["damage"]
    games = row["games"] or 1
    return (
        round(row["total"] / games, 2),
        round(row["acpl"] or 0.0, 1),
        round(damage / games, 3),
        _per_game_counts(conn, ids),
    )


def _trend(conn: sqlite3.Connection, ids: list[int]) -> Trend | None:
    if len(ids) < MIN_GAMES_FOR_TREND:
        return None
    midpoint = len(ids) // 2
    earlier, later = ids[:midpoint], ids[midpoint:]
    earlier_rate, earlier_acpl, earlier_damage, earlier_counts = _half_stats(conn, earlier)
    later_rate, later_acpl, later_damage, later_counts = _half_stats(conn, later)
    return Trend(
        earlier_games=len(earlier),
        later_games=len(later),
        earlier_mistakes_per_game=earlier_rate,
        later_mistakes_per_game=later_rate,
        earlier_acpl=earlier_acpl,
        later_acpl=later_acpl,
        earlier_damage_per_game=earlier_damage,
        later_damage_per_game=later_damage,
        earlier_counts=tuple(earlier_counts),
        later_counts=tuple(later_counts),
    )


def build_profile(
    conn: sqlite3.Connection,
    user: str,
    last_n: int | None = None,
    exclude_game_id: int | None = None,
) -> PlayerProfile:
    """Aggregate a player's stored games into their recurring weaknesses.

    ``last_n`` limits the window to the most recent games, which is what makes the
    profile track a player who is improving rather than averaging over their whole life.
    ``exclude_game_id`` leaves one game out — see :func:`_window_ids`.
    """
    ids = _window_ids(conn, user, last_n, exclude_game_id)
    if not ids:
        return PlayerProfile(user=user, games=0, mistakes=0, acpl=0.0)

    totals = conn.execute(
        f"""
        SELECT COALESCE(SUM(blunders + mistakes + inaccuracies), 0) AS mistakes,
               AVG(acpl) AS acpl
        FROM games WHERE id IN ({_placeholders(ids)})
        """,
        ids,
    ).fetchone()

    return PlayerProfile(
        user=user,
        games=len(ids),
        mistakes=totals["mistakes"],
        acpl=round(totals["acpl"] or 0.0, 1),
        motifs=_motif_stats(conn, ids),
        phases=_phase_stats(conn, ids),
        openings=_opening_stats(conn, ids),
        trend=_trend(conn, ids),
    )


def _table(header: str, rows: list[tuple]) -> list[str]:
    """A header row plus its data rows, or nothing at all when there is no data.

    Absence is meaningful and cheaper than a placeholder: no ``pattern`` table means no
    tactical pattern has been tagged, and the system prompt says how to read that.
    """
    if not rows:
        return []
    return [header] + [" | ".join(str(cell) for cell in row) for row in rows]


def _pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def _trend_block(trend: Trend | None) -> list[str]:
    """The trend as three comparable measures, plus the verdict on whether it is real."""
    if trend is None:
        return []
    return [
        "measure | recent | earlier | normal_variation | verdict",
        f"mistakes_per_game | {trend.later_mistakes_per_game} | "
        f"{trend.earlier_mistakes_per_game} | {trend.noise_floor:.2f} | {trend.direction}",
        f"centipawn_loss | {trend.later_acpl} | {trend.earlier_acpl} | - | -",
        f"damage_per_game | {_pct(trend.later_damage_per_game)} | "
        f"{_pct(trend.earlier_damage_per_game)} | - | -",
        f"games_compared | {trend.later_games} | {trend.earlier_games} | - | -",
    ]


def format_profile(profile: PlayerProfile) -> str:
    """Render a profile as structured ``a | b | c`` rows under header lines.

    Deliberately not prose. Everything downstream of this is a coaching model whose whole
    job is turning facts into language, and hand-writing sentences here both duplicates
    that job and does it worse — the model can weave a pattern into the rest of its
    advice, while a canned sentence can only sit next to it.

    So this emits facts and *statuses* (``recurring`` / ``once_only``, ``improving`` /
    ``unclear``); how to speak about each status lives in the system prompt. The numbers
    stay computed here because the model provably gets chess facts wrong often enough
    that a count it derived itself could not be trusted, and a wrong count stated
    confidently is worse than no count.
    """
    if profile.is_empty:
        return f"No games stored yet for {profile.user}."

    blocks = [
        [
            f"games_analyzed | {profile.games}",
            f"total_mistakes | {profile.mistakes}",
            f"average_centipawn_loss | {profile.acpl}",
        ],
        _table(
            "pattern | occurrences | games | avg_cost | status",
            [
                (m.label, m.occurrences, m.games, _pct(m.avg_win_prob_lost), m.status)
                for m in profile.motifs
            ],
        ),
        _table(
            "phase | mistakes | avg_cost",
            [(p.phase, p.mistakes, _pct(p.avg_win_prob_lost)) for p in profile.phases],
        ),
        _table(
            "opening | games | centipawn_loss",
            [(o.name, o.games, o.acpl) for o in profile.openings],
        ),
        _trend_block(profile.trend),
    ]
    return "\n\n".join("\n".join(block) for block in blocks if block)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Show a player's recurring weaknesses from stored games."
    )
    parser.add_argument("--user", required=True, help="whose profile to build")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="path to the memory database")
    parser.add_argument(
        "--last", type=int, help="only consider this many most-recent games"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    conn = connect(args.db)
    profile = build_profile(conn, args.user, args.last)
    if profile.is_empty:
        print(
            f"No games stored for {args.user}. "
            f"Run: python -m memory.store --user {args.user} games.pgn",
            file=sys.stderr,
        )
        return 1
    print(format_profile(profile))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
