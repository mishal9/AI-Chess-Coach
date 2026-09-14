"""Paired equivalence testing for two eval runs — is a null result a real null?

``eval.compare`` answers "did it change?" by counting better/same/worse games. That is
enough while iterating, but it cannot distinguish *"these are the same"* from *"we cannot
tell them apart with 29 games"*, and those mean opposite things when reporting a negative
result.

This computes, per rubric axis, the paired difference, a confidence interval, and **two
one-sided tests** (TOST) against a pre-registered smallest-effect-of-interest. TOST
inverts the usual logic: a small p means the effect is *reliably smaller than delta*, i.e.
equivalent. A large p means the data are simply too thin to say — which is the honest
reading of most small nulls, and the one that gets skipped.

It also reports the minimum detectable effect and the sample size that delta would need,
so an underpowered axis says so out loud instead of being read as a tie.

Existing safeguards are reused rather than reimplemented: ``eval.compare`` already refuses
to difference reports whose metric versions or judge models differ, and that refusal
applies here for the same reason.

Usage:
    python -m eval.equivalence eval/reports/prompted_8b_2026-08-14.json \\
                               eval/reports/8b_v2_2026-08-10.json
    python -m eval.equivalence a.json b.json --delta 0.30 --alpha 0.05

    # cross-judge agreement: the same stored coaching, scored by two judges
    python -m eval.equivalence --agreement eval/reports/8b_v2_2026-08-10.json \\
                               eval/reports/8b_v2_2026-08-10__gemini31pro.json
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from eval.compare import load_report

# The smallest rubric difference we agreed in advance is worth caring about. Chosen as
# roughly the v1 -> v2 step, and outside the judged-axis noise. Pre-registering it is what
# makes a null interpretable rather than convenient.
DEFAULT_DELTA = 0.30

# One-sided alpha for each of the two TOST tests. The reported interval is the
# (1 - 2*alpha) interval, which is the one TOST corresponds to — 90% at alpha = 0.05.
DEFAULT_ALPHA = 0.05

RUBRIC_AXES = (
    "factual_correctness",
    "clarity",
    "actionability",
    "identifies_key_mistake",
)


@dataclass(frozen=True)
class AxisResult:
    """The paired comparison for one rubric axis."""

    axis: str
    n: int
    mean_difference: float
    sd_difference: float
    ci_low: float
    ci_high: float
    tost_p: float
    delta: float
    wilcoxon_p: float | None
    mde: float
    n_needed: int | None

    @property
    def equivalent(self) -> bool:
        """Reliably smaller than ``delta`` in both directions."""
        return self.tost_p < DEFAULT_ALPHA

    @property
    def verdict(self) -> str:
        if self.equivalent:
            return f"equivalent within ±{self.delta}"
        return f"inconclusive — cannot rule out ±{self.delta}"


def paired_scores(base: dict, cand: dict, axis: str) -> tuple[list[float], list[float]]:
    """Per-game scores for one axis, aligned game by game.

    ``eval.run`` walks the manifest in order, so the two reports are positionally paired —
    but that is an assumption worth checking rather than trusting, so every pair must
    agree on ``pgn``, ``game_index`` and ``coached_side``. A mismatch means the reports
    are not over the same games and differencing them would be meaningless.
    """
    base_games, cand_games = base["games"], cand["games"]
    if len(base_games) != len(cand_games):
        raise ValueError(
            f"different numbers of games: {len(base_games)} vs {len(cand_games)}"
        )

    left: list[float] = []
    right: list[float] = []
    for i, (b, c) in enumerate(zip(base_games, cand_games)):
        identity = ("pgn", "game_index", "coached_side")
        for key in identity:
            if key in b and key in c and b[key] != c[key]:
                raise ValueError(
                    f"game {i} does not line up: {key} is {b[key]!r} in the baseline and "
                    f"{c[key]!r} in the candidate — these reports are not paired"
                )
        if "rubric" not in b or "rubric" not in c:
            continue
        b_score = b["rubric"]["scores"].get(axis)
        c_score = c["rubric"]["scores"].get(axis)
        if b_score is None or c_score is None:
            continue
        left.append(float(b_score))
        right.append(float(c_score))
    return left, right


def assess_axis(
    base_scores: list[float],
    cand_scores: list[float],
    axis: str,
    delta: float = DEFAULT_DELTA,
    alpha: float = DEFAULT_ALPHA,
) -> AxisResult:
    """TOST plus supporting statistics for one axis."""
    from statistics import stdev

    from scipy import stats

    n = len(base_scores)
    if n < 2:
        raise ValueError(f"{axis}: need at least 2 paired games, got {n}")

    differences = [c - b for b, c in zip(base_scores, cand_scores)]
    mean = sum(differences) / n
    sd = stdev(differences)
    df = n - 1
    se = sd / (n**0.5) if sd else 0.0

    if se == 0:
        # No spread at all: every pair differs by exactly `mean`, so the difference is
        # known with certainty. That makes it equivalent when it is inside delta and
        # decisively *not* equivalent when it is outside — the absence of variance is not
        # the absence of an effect.
        tost_p = 0.0 if abs(mean) < delta else 1.0
        low = high = mean
        mde = 0.0
    else:
        # H0 for each side is "the effect is at least delta in this direction"; rejecting
        # both is what equivalence means.
        p_lower = stats.t.sf((mean + delta) / se, df)
        p_upper = stats.t.cdf((mean - delta) / se, df)
        tost_p = max(p_lower, p_upper)
        half = stats.t.ppf(1 - alpha, df) * se
        low, high = mean - half, mean + half
        mde = (stats.t.ppf(1 - alpha / 2, df) + stats.t.ppf(0.80, df)) * se

    try:
        wilcoxon_p = (
            float(stats.wilcoxon(differences).pvalue) if any(differences) else None
        )
    except ValueError:  # pragma: no cover - scipy refuses all-zero input
        wilcoxon_p = None

    n_needed = None
    if sd and delta:
        # Normal approximation, two-sided alpha, 80% power — a planning number, not a test.
        n_needed = int(round(((1.959964 + 0.841621) * sd / delta) ** 2))

    return AxisResult(
        axis=axis,
        n=n,
        mean_difference=round(mean, 4),
        sd_difference=round(sd, 4),
        ci_low=round(low, 4),
        ci_high=round(high, 4),
        tost_p=round(tost_p, 4),
        delta=delta,
        wilcoxon_p=round(wilcoxon_p, 4) if wilcoxon_p is not None else None,
        mde=round(mde, 4),
        n_needed=n_needed,
    )


def compare_reports(
    base: dict,
    cand: dict,
    delta: float = DEFAULT_DELTA,
    alpha: float = DEFAULT_ALPHA,
    axes: tuple[str, ...] = RUBRIC_AXES,
) -> list[AxisResult]:
    """Every rubric axis, plus the overall mean, as paired equivalence results."""
    results = []
    for axis in axes:
        base_scores, cand_scores = paired_scores(base, cand, axis)
        if base_scores:
            results.append(assess_axis(base_scores, cand_scores, axis, delta, alpha))

    overall_base, overall_cand = _overall_scores(base, cand, axes)
    if overall_base:
        results.append(
            assess_axis(overall_base, overall_cand, "rubric_overall", delta, alpha)
        )
    return results


def _overall_scores(
    base: dict, cand: dict, axes: tuple[str, ...]
) -> tuple[list[float], list[float]]:
    """Per-game mean across axes, for each report."""
    per_axis = [paired_scores(base, cand, axis) for axis in axes]
    per_axis = [pair for pair in per_axis if pair[0]]
    if not per_axis:
        return [], []
    n = len(per_axis[0][0])
    left = [sum(pair[0][i] for pair in per_axis) / len(per_axis) for i in range(n)]
    right = [sum(pair[1][i] for pair in per_axis) / len(per_axis) for i in range(n)]
    return left, right


def render(results: list[AxisResult], base_name: str, cand_name: str) -> str:
    """A table plus the sentence each row licenses."""
    lines = [
        f"Paired equivalence: {cand_name} vs {base_name}",
        f"n = {results[0].n} games, delta = {results[0].delta}, "
        f"{int((1 - 2 * DEFAULT_ALPHA) * 100)}% intervals",
        "",
        f"{'axis':24s} {'Δ':>8} {'interval':>20} {'TOST p':>8}  verdict",
    ]
    for r in results:
        interval = f"[{r.ci_low:+.3f}, {r.ci_high:+.3f}]"
        lines.append(
            f"{r.axis:24s} {r.mean_difference:>+8.3f} {interval:>20} "
            f"{r.tost_p:>8.3f}  {r.verdict}"
        )

    lines.append("")
    for r in results:
        if r.equivalent:
            lines.append(
                f"{r.axis}: no effect as large as ±{r.delta} — a real null, not an "
                f"absence of evidence."
            )
        else:
            need = f"~{r.n_needed} games" if r.n_needed else "more games"
            lines.append(
                f"{r.axis}: |Δ| < {max(abs(r.ci_low), abs(r.ci_high)):.2f} with "
                f"{int((1 - 2 * DEFAULT_ALPHA) * 100)}% confidence, but an effect of "
                f"{r.delta} cannot be ruled out at n={r.n} "
                f"(smallest detectable {r.mde:.2f}; would need {need})."
            )
    return "\n".join(lines)


def rubric_comparability_problems(base: dict, cand: dict) -> list[str]:
    """Reasons two reports' *rubric* scores cannot be differenced.

    Narrower than :func:`eval.compare.comparability_problems` on purpose. That function
    also refuses a grounding or claims version mismatch, which is right when differencing
    those metrics — but the rubric is produced by a judge that never touches the citation
    parser, so a metric-version difference does not make two rubric scores incomparable.
    Applying the wider check here would block a valid comparison, which is its own kind of
    wrong answer.

    The judge model still has to match: a rubric score means nothing apart from its ruler.
    """
    problems = []
    base_judge, cand_judge = base.get("judge_model"), cand.get("judge_model")
    if base_judge and cand_judge and base_judge != cand_judge:
        problems.append(
            f"judge: baseline was scored by {base_judge}, candidate by {cand_judge} — "
            "rubric scores are only meaningful against the same ruler."
        )
    return problems


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Is the difference between two eval runs a real null, or an "
        "underpowered one?"
    )
    parser.add_argument("baseline", help="path to the baseline report JSON")
    parser.add_argument("candidate", help="path to the candidate report JSON")
    parser.add_argument(
        "--delta",
        type=float,
        default=DEFAULT_DELTA,
        help="smallest effect worth caring about (rubric points)",
    )
    parser.add_argument("--alpha", type=float, default=DEFAULT_ALPHA)
    parser.add_argument(
        "--agreement",
        action="store_true",
        help="instead of testing equivalence, correlate two judges' scores over the "
        "same stored coaching (e.g. a report and its eval.rejudge copy)",
    )
    parser.add_argument(
        "--allow-judge-mismatch",
        action="store_true",
        help="compare anyway when the two runs were scored by different judges",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    base, cand = load_report(args.baseline), load_report(args.candidate)

    if args.agreement:
        problems = agreement_problems(base, cand)
        if problems:
            print("These reports cannot measure judge agreement:\n", file=sys.stderr)
            for problem in problems:
                print(f"  - {problem}", file=sys.stderr)
            return 1
        results = judge_agreement(base, cand)
        if not results:
            print("Too few commonly scored games to correlate.", file=sys.stderr)
            return 1
        print(render_agreement(results, base.get("judge_model") or Path(args.baseline).stem,
                               cand.get("judge_model") or Path(args.candidate).stem))
        return 0

    problems = rubric_comparability_problems(base, cand)
    if problems and not args.allow_judge_mismatch:
        print("These reports are not comparable:\n", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        print("\nPass --allow-judge-mismatch to override.", file=sys.stderr)
        return 1
    if problems:
        print("WARNING: comparing reports that are not strictly comparable.\n",
              file=sys.stderr)

    results = compare_reports(base, cand, args.delta, args.alpha)
    if not results:
        print("No rubric scores in these reports — nothing to test.", file=sys.stderr)
        return 1
    print(render(results, Path(args.baseline).stem, Path(args.candidate).stem))
    return 0



# --- cross-judge agreement -------------------------------------------------------------

@dataclass(frozen=True)
class AgreementResult:
    """How closely two judges scored the same texts on one axis."""

    axis: str
    n: int
    pearson: float
    kendall: float
    mean_a: float
    mean_b: float
    exact_match: float
    within_one: float

    @property
    def bias(self) -> float:
        """How much more generous judge B was, in rubric points."""
        return round(self.mean_b - self.mean_a, 3)


def judge_agreement(
    report_a: dict, report_b: dict, axes: tuple[str, ...] = RUBRIC_AXES
) -> list[AgreementResult]:
    """Correlate two judges' scores over the same stored coaching.

    Only meaningful when the two reports scored *identical texts* — which is what
    :mod:`eval.rejudge` produces and what re-running generation would not. Reported
    alongside Kendall's tau because these are ordinal 1-5 scores on a short scale, where
    Pearson alone flatters agreement.

    Published context for reading the numbers: Kim et al. (NAACL 2025) validate their
    LLM judge for chess commentary against human raters at Pearson 0.40-0.56 /
    Kendall 0.23-0.39. Judge-to-judge agreement in that range is ordinary, not alarming.
    """
    from scipy import stats

    results = []
    for axis in axes:
        a_scores, b_scores = paired_scores(report_a, report_b, axis)
        if len(a_scores) < 3:
            continue
        # A judge that gave every game the same score has no variance to correlate.
        if len(set(a_scores)) < 2 or len(set(b_scores)) < 2:
            pearson = kendall = float("nan")
        else:
            pearson = float(stats.pearsonr(a_scores, b_scores).statistic)
            kendall = float(stats.kendalltau(a_scores, b_scores).statistic)
        n = len(a_scores)
        results.append(
            AgreementResult(
                axis=axis,
                n=n,
                pearson=round(pearson, 3),
                kendall=round(kendall, 3),
                mean_a=round(sum(a_scores) / n, 3),
                mean_b=round(sum(b_scores) / n, 3),
                exact_match=round(
                    sum(x == y for x, y in zip(a_scores, b_scores)) / n, 3
                ),
                within_one=round(
                    sum(abs(x - y) <= 1 for x, y in zip(a_scores, b_scores)) / n, 3
                ),
            )
        )
    return results


def agreement_problems(report_a: dict, report_b: dict) -> list[str]:
    """Reasons two reports cannot measure judge-to-judge agreement.

    The inverse of :func:`rubric_comparability_problems`: here the judges *must* differ,
    and the coaching must not. If the texts differ, a score gap mixes the judge with the
    coach, and the correlation stops meaning agreement.
    """
    problems = []
    judge_a, judge_b = report_a.get("judge_model"), report_b.get("judge_model")
    if judge_a and judge_a == judge_b:
        problems.append(f"both reports were scored by {judge_a} — there is no second judge.")
    games_a, games_b = report_a["games"], report_b["games"]
    if len(games_a) != len(games_b):
        problems.append(f"different numbers of games: {len(games_a)} vs {len(games_b)}")
        return problems
    differing = [
        i for i, (a, b) in enumerate(zip(games_a, games_b))
        if a.get("coaching") != b.get("coaching")
    ]
    if differing:
        problems.append(
            f"coaching text differs in {len(differing)} game(s) (first: game "
            f"{differing[0]}) — these are not the same texts re-judged."
        )
    return problems


def render_agreement(results: list[AgreementResult], name_a: str, name_b: str) -> str:
    lines = [
        f"Cross-judge agreement on identical texts: {name_a} vs {name_b}",
        f"n = {results[0].n} games",
        "",
        f"{'axis':24s} {'r':>7} {'tau':>7} {name_a[:9]:>9} {name_b[:9]:>9} "
        f"{'bias':>7} {'exact':>7} {'±1':>7}",
    ]
    for r in results:
        lines.append(
            f"{r.axis:24s} {r.pearson:>7.2f} {r.kendall:>7.2f} {r.mean_a:>9.2f} "
            f"{r.mean_b:>9.2f} {r.bias:>+7.2f} {r.exact_match:>7.0%} {r.within_one:>7.0%}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
