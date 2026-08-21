"""What the stored games add up to — a player's recurring weaknesses.

Every number here is a ``GROUP BY`` over :mod:`memory.store`. That is the whole argument
for a relational store: "which mistake costs you most", "are you improving", and "how many
times now" are counting questions, and counting is what SQL is for.

The renderer is deliberately blunt about sample size. A pattern seen once is not a
pattern, and a profile that says so keeps the coach from turning a single bad game into a
character flaw.

Usage:
    python -m memory.profile --user mishal9
    python -m memory.profile --user mishal9 --last 20
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from dataclasses import dataclass, field

from memory.store import DEFAULT_DB, connect

# Below this many occurrences a motif is an incident, not a habit, and is reported as such.
MIN_OCCURRENCES_FOR_PATTERN = 2

# Splitting a window into halves needs enough games that each half means something.
MIN_GAMES_FOR_TREND = 6

# An opening needs repeat visits before its average says anything about the player.
MIN_GAMES_FOR_OPENING = 2

_MOTIF_LABELS = {
    "hangs_material": "leaving material hanging",
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


@dataclass(frozen=True)
class Trend:
    earlier_games: int
    later_games: int
    earlier_mistakes_per_game: float
    later_mistakes_per_game: float
    earlier_acpl: float
    later_acpl: float

    @property
    def mistakes_delta(self) -> float:
        """Negative means fewer mistakes per game lately — improvement."""
        return round(self.later_mistakes_per_game - self.earlier_mistakes_per_game, 2)

    @property
    def acpl_delta(self) -> float:
        return round(self.later_acpl - self.earlier_acpl, 1)


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


def _window_ids(conn: sqlite3.Connection, user: str, last_n: int | None) -> list[int]:
    """Game ids in the reporting window, oldest first.

    Ordered by date where the PGN carried one, falling back to ingest order. Lichess and
    chess.com exports always date their games, so the fallback is for hand-made PGNs.
    """
    rows = conn.execute(
        """
        SELECT id FROM games WHERE user_name = ?
        ORDER BY COALESCE(played_at, ''), id
        """,
        (user,),
    ).fetchall()
    ids = [row["id"] for row in rows]
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


def _half_stats(conn: sqlite3.Connection, ids: list[int]) -> tuple[float, float]:
    """``(mistakes_per_game, acpl)`` for a set of games."""
    row = conn.execute(
        f"""
        SELECT COUNT(*) AS games,
               COALESCE(SUM(blunders + mistakes + inaccuracies), 0) AS total,
               AVG(acpl) AS acpl
        FROM games WHERE id IN ({_placeholders(ids)})
        """,
        ids,
    ).fetchone()
    games = row["games"] or 1
    return round(row["total"] / games, 2), round(row["acpl"] or 0.0, 1)


def _trend(conn: sqlite3.Connection, ids: list[int]) -> Trend | None:
    if len(ids) < MIN_GAMES_FOR_TREND:
        return None
    midpoint = len(ids) // 2
    earlier, later = ids[:midpoint], ids[midpoint:]
    earlier_rate, earlier_acpl = _half_stats(conn, earlier)
    later_rate, later_acpl = _half_stats(conn, later)
    return Trend(
        earlier_games=len(earlier),
        later_games=len(later),
        earlier_mistakes_per_game=earlier_rate,
        later_mistakes_per_game=later_rate,
        earlier_acpl=earlier_acpl,
        later_acpl=later_acpl,
    )


def build_profile(
    conn: sqlite3.Connection, user: str, last_n: int | None = None
) -> PlayerProfile:
    """Aggregate a player's stored games into their recurring weaknesses.

    ``last_n`` limits the window to the most recent games, which is what makes the
    profile track a player who is improving rather than averaging over their whole life.
    """
    ids = _window_ids(conn, user, last_n)
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


def format_profile(profile: PlayerProfile) -> str:
    """Render a profile as plain factual lines.

    Written to be quotable: every claim carries its own count, so a reader — human or
    model — cannot upgrade "twice" into "always" without contradicting the text in front
    of it.
    """
    if profile.is_empty:
        return f"No games stored yet for {profile.user}."

    lines = [
        f"Across {profile.games} analyzed game(s), {profile.user} made "
        f"{profile.mistakes} flagged mistakes (average centipawn loss {profile.acpl}).",
    ]

    patterns = [m for m in profile.motifs if m.is_pattern]
    incidents = [m for m in profile.motifs if not m.is_pattern]

    if patterns:
        lines.append("")
        lines.append("Recurring patterns (most costly first):")
        for stat in patterns:
            lines.append(
                f"- {stat.label}: {stat.occurrences} times across {stat.games} game(s), "
                f"costing about {stat.avg_win_prob_lost * 100:.0f}% win probability each time."
            )
    if incidents:
        lines.append("")
        lines.append(
            "Seen only once so far (not yet a pattern): "
            + ", ".join(f"{s.label}" for s in incidents)
            + "."
        )
    if not profile.motifs:
        lines.append("")
        lines.append(
            "No motif-tagged mistakes yet — the errors so far were positional rather "
            "than the tactical patterns this profile recognizes."
        )

    if profile.phases:
        lines.append("")
        worst = profile.phases[0]
        lines.append(
            f"Most damage happens in the {worst.phase}: {worst.mistakes} mistakes there, "
            f"costing about {worst.avg_win_prob_lost * 100:.0f}% win probability each."
        )
        others = ", ".join(f"{p.phase} {p.mistakes}" for p in profile.phases[1:])
        if others:
            lines.append(f"By phase, mistake counts are: {worst.phase} "
                         f"{worst.mistakes}, {others}.")

    if profile.openings:
        lines.append("")
        worst = profile.openings[0]
        lines.append(
            f"Worst-scoring opening so far: {worst.eco} {worst.opening} — "
            f"{worst.games} games, average centipawn loss {worst.acpl}."
        )

    if profile.trend is not None:
        trend = profile.trend
        direction = (
            "fewer" if trend.mistakes_delta < 0
            else "more" if trend.mistakes_delta > 0
            else "the same number of"
        )
        lines.append("")
        lines.append(
            f"Trend: over the most recent {trend.later_games} games you averaged "
            f"{trend.later_mistakes_per_game} mistakes per game "
            f"(centipawn loss {trend.later_acpl}), versus "
            f"{trend.earlier_mistakes_per_game} (centipawn loss {trend.earlier_acpl}) "
            f"in the {trend.earlier_games} before that — {direction} mistakes lately."
        )

    return "\n".join(lines)


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
