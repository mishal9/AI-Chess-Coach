# Two-week publication sprint — TMLR, submit Mon 14 Sep 2026

Date: 2026-08-31. Companion to `docs/experiments/2026-08-30-paper-outline.md`.
Tracked in Todoist under **Chess Analyzer → AI Eng**, sections `TMLR Sprint · *`.

## The call

**Target: TMLR, submitted Mon 14 Sep, with an arXiv preprint the same morning.**

Rejected alternatives:

- **ARR October cycle (closes 12 Oct 2026 → NAACL 2027).** Six weeks out — too slow for
  a two-week deadline, and a main-conference reviewer kills n=29.
- **TACL.** Better prestige, but same n=29 problem plus the single-judge issue, and the
  rolling review is ~2 months to first response.
- **Chess / games venue.** Wrong audience; the outline already ruled this out and is right.

TMLR's acceptance bar — claims supported by evidence, of interest to some subset — is the
only top-tier criterion this paper already satisfies. It is rolling, so the deadline is the
one we chose rather than one we are racing. No page limit means §7 threats-to-validity gets
room, which is the strongest defensive asset. **TMLR forbids concurrent submission**, so ARR
October is a sequential fallback, not a parallel bet.

## Milestones

| # | Date | Gate |
|---|---|---|
| M1 | Wed 2 Sep | Gate 3 closed — cross-judge agreement reported |
| M2 | Sun 6 Sep | Evidence freeze — every number final, no more compute |
| M3 | Thu 10 Sep | Full draft, all sections, all figures |
| M4 | Sun 13 Sep | Hostile-review pass done, repo tagged `paper-v1` |
| M5 | Mon 14 Sep | arXiv + TMLR submitted |

## Starting position (better than the outline says)

- Gates 1, 2, 4 already cleared. Gate 4 closed 2026-08-31: the class-C hypothesis **does
  not hold** — fine-tuning more than doubled placement claims (1.03 → 2.31/game) while
  false claims stayed flat at one each.
- `eval/rejudge.py` written (uncommitted), `eval/equivalence.py` landed,
  `eval/expand_heldout.py` exists.
- **Both `ANTHROPIC_API_KEY` and `GEMINI_API_KEY` are set in `.env`.** Gate 3 is not
  blocked — it is merely unrun.
- No paper draft exists yet. Only the outline.

## Week 1 — evidence (the part that can still fail)

**Day 1 · Mon 31 Aug.** Two items, ~45 min, worth doing tonight so the rejudge runs
unattended overnight.

- *1a — contamination check, first.* `python -m eval.expand_heldout --per-bucket 20
  --dry-run`. Does topping up force a re-cut of the training corpus? **If yes, do not
  expand.** A re-cut contaminates v2's eval and every number in the paper dies; n=29 with
  an honest bound merely weakens it.
- *1b — cut `paper/grounding-audit`* off the phase-6 branch, commit the untracked outline,
  gap analysis, and `rejudge.py` plus the modified `backends.py` / `equivalence.py` — the
  paper cannot cite what is not in git. Then launch both rejudge runs.

**Day 2 · Tue 1 Sep → M1.** Per-axis Opus↔Gemini agreement on identical stored text, then
`eval.equivalence` re-run under the Gemini judge. The question: does §6.3 survive a judge
swap? Write up as `docs/experiments/2026-09-01-gate3-cross-judge.md`. If Gemini diverges
sharply that is not a disaster — judge-dependence of the rubric *is* a meta-evaluation
finding and strengthens the frame. Wed 2 Sep is slack for that pivot.

**Day 3 · Wed 2 Sep.** Launch the expansion in the background (Stockfish-bound,
unattended). Build the human-rating instrument: 20 games stratified by bucket, model
identity stripped, order randomized, same 4-axis rubric. **Recruit raters today** — the
item most likely to slip, and two raters × 20 games is the difference between a desk
reject and a review.

**Day 4 · Thu 3 Sep.** `paper/` with the TMLR style file. Write §4 (the audit) in full —
primary contribution, every number already on disk. F2 and F3 as committed scripts under
`eval/figures/`, not scratchpad, per §8's own "record enough to be checked" lesson.

**Day 5 · Fri 4 Sep.** Coach + judge both arms over the expanded set, spend guard on.
Draft §5 while it runs.

**Day 6 · Sat 5 Sep.** Human ratings in; human↔Opus↔Gemini agreement. Re-run equivalence
at the new n against the pre-registered δ=0.30. Decision point: if factual correctness now
clears δ in either direction, the abstract changes.

**Day 7 · Sun 6 Sep → M2.** Regenerate T1–T4 and F4, tag `evidence-freeze`, stop.

## Week 2 — prose only

| Day | Date | Goal |
|---|---|---|
| 8  | Mon 7 Sep  | §1 Introduction + §2 Related work (hardest writing day) |
| 9  | Tue 8 Sep  | §3 Setup + §6 distillation + §6.5 ablation, at the new n |
| 10 | Wed 9 Sep  | §7 Threats + §8 Discussion + §9 Limitations + draw F1 |
| 11 | Thu 10 Sep | Appendices + rewrite abstract **last** + read-through → M3 |
| 12 | Fri 11 Sep | Reproducibility: fresh clone, bare `pytest` green, `paper/REPRODUCE.md` |
| 13 | Sat 12 Sep | External read + write the three reviews you fear, answer each in the text |
| 14 | Sun 13 Sep | Fix, freeze, tag `paper-v1` → M4 |
| 15 | Mon 14 Sep | arXiv (cs.CL, cross-list cs.LG) + TMLR OpenReview → M5 |

The current abstract is written against pre-Gate-3 numbers and will be wrong. Rewrite it
from the final tables on Day 11, not before.

## Standing rules

1. **After 6 Sep, no new experiments.** The documented failure mode on this project is
   finding one more thing worth auditing.
2. **Every number traceable** to a committed report file *and* a committed script. §8's
   third lesson is exactly this — the paper must not violate its own finding.
3. **Phase 6 stops for two weeks.** Cannot ship an app and a paper in the same fortnight.

## Risks

| Risk | Mitigation |
|---|---|
| Expansion re-cuts the corpus and contaminates v2's eval | Day 1a dry-run gates it; if it collides, ship at n=29 with the bound |
| Gemini disagrees with Opus, invalidating §6 | Reframe as judge-dependence finding; Wed 2 Sep is the slack day |
| Human raters never materialise | Recruit Day 3, not Day 10; n=2 raters is enough |
