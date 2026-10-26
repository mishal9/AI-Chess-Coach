# The prompted-8B control: does fine-tuning beat prompting the same base model?

**Date:** 2026-08-14 · **Status:** complete · **Cost:** 29 judge calls (~25 min wall clock, one local GPU-free run)

Every comparison in this project until now measured an 8B fine-tune against a prompted
**3B**, which confounds the size jump with the fine-tune and cannot answer the
question that decides whether the pipeline is worth keeping:

> Does fine-tuning `qwen3:8b` on distilled coaching beat simply prompting `qwen3:8b`?

**Answer: no, on everything the judge can see. Judged factual correctness is identical —
3.72 for both. Fine-tuning bought citation discipline (+0.042 grounding, two more fully
grounded games) and nothing else.**

## 1 · Design

Same base weights, same prompt pipeline, same held-out set, same judge. The only difference
is the LoRA.

| | control | subject |
|---|---|---|
| coach model | `qwen3:8b` (prompted, no fine-tune) | `qwen-coach-8b-v2` (QLoRA on the v2 dataset) |
| coach temperature | 0 | 0 |
| Stockfish depth | 15 | 15 |
| judge | `claude-opus-4-8` | `claude-opus-4-8` |
| held-out set | the fixed 29 games | the fixed 29 games |

Report: `eval/reports/prompted_8b_2026-08-14.json`.

## 2 · Result

Grounding for v2 is the **corrected** figure (`eval.rescore`, post-#41); claims for v2 are
the backfilled figure (`eval.recheck`). The control's numbers are native — `eval.run` has
computed both since #43/#45. §5 explains why mixing the raw stored numbers is a trap.

| metric | prompted `qwen3:8b` | fine-tuned v2 | Δ (fine-tune − control) |
|---|---|---|---|
| **judge factual** | **3.72** | **3.72** | **+0.00** |
| judge overall | **4.17** | 4.14 | −0.03 |
| clarity | 4.41 | **4.45** | +0.04 |
| actionability | **3.72** | 3.59 | −0.13 |
| identifies key mistake | **4.83** | 4.79 | −0.04 |
| grounding | 0.923 | **0.965** | **+0.042** |
| fully grounded games | 23/29 (79%) | **25/29 (86%)** | +2 games |
| claims | **0.989** | 0.974 | −0.015 |
| claim-clean games | **28/29** | 27/29 | −1 game |

Paired per-game factual, same 29 games: **8 better · 14 same · 7 worse.**

Per bucket, the control:

| bucket | n | grounding | claims | factual |
|---|---|---|---|---|
| clean_draw | 4 | 1.00 | 1.00 | 3.75 |
| slow_loss | 5 | 0.90 | 1.00 | 4.00 |
| two_mistakes | 5 | 0.94 | 1.00 | 3.80 |
| one_blunder | 5 | 0.93 | 1.00 | 3.60 |
| multi_blunder | 5 | 0.94 | 0.93 | 3.60 |
| inaccuracies | 5 | 0.84 | 1.00 | 3.60 |

Where the fine-tune wins and loses on factual: `clean_draw` **+0.50** (the original
hallucination target — genuinely fixed), `multi_blunder` +0.20; `one_blunder` **−0.40**,
`inaccuracies` −0.20; `slow_loss` and `two_mistakes` level.

The control's single claim violation is one `invented_placement` in `multi_blunder`. v2 has
two.

## 3 · What this means

**Against the gate proposed in [#47](./2026-08-13-gates-re-derived.md) (factual ≥ control
+ 0.30), v2 misses by the entire margin.** Its improvement over its own un-fine-tuned base
is exactly zero.

Three iterations of dataset work (v1 → v2 → the shape-vs-volume ablation) moved grounding,
which the [audit](./2026-08-11-grounding-metric-audit.md) later showed was partly measuring
whether the model said the word "b7". The judged quality did not move at all relative to
what the base model produces when simply given the same facts block.

The defensible claim the pipeline still supports is narrower than the one the project has
been assuming:

> Distillation reproduces the base model's judged coaching quality while improving citation
> discipline: 0.923 → 0.965 grounding, 79% → 86% fully grounded games.

That claim holds, and `clean_draw` +0.50 factual shows the confabulation-on-clean-games failure
that started Phase 3 was fixed. It does not support "the fine-tune is a better coach."

**The likely ceiling is the facts block, not the student.** If Opus-written coaching, distilled
into an 8B, lands exactly where that 8B already lands when prompted, the constraint is
plausibly the information available to either: moves, qualities, centipawn losses, win
probabilities, and nothing about plans, structures or piece activity. That is a testable
hypothesis (§6), and it should be tested before another dataset is built.

## 4 · Threats to validity

- **Single seed, single judge, n=29.** The ±0.13 wobble seen across judged axes here is the
  same order as most of the deltas. A 0.00 factual difference is a strong null, but "the
  control is 0.03 better overall" is not a result.
- **The control is prompted with the *student's* prompt.** `coach/prompts.py` was written
  for the pipeline, not tuned for a prompted 8B. A prompt-engineered control might do
  better still, which would strengthen this conclusion rather than weaken it.
- **v2's grounding and claims come from re-scoring and backfill**, not from a native run
  under the current metric. Both were verified reproducible (see the audit §9 and the gate
  doc §4), but they are reconstructions.
- **Qwen3 is a hybrid reasoner run non-thinking**, with `<think>` blocks stripped
  (#25). Any residual difference in how the fine-tune and the base handle that is not
  controlled for.

## 5 · `eval.compare` compared across metric versions, and inverted a number

Running the tool directly on these two reports reports grounding as **−0.02 for the
fine-tune**. The true figure is **+0.042 in its favour**.

The cause: the control's report was scored by the post-#41 parser, while v2's *stored*
`grounding_mean` (0.907) was written by the pre-#41 parser, whose corrected value is 0.965.
`eval.compare` reads both raw and differences them, with nothing recording which metric
version produced either.

This is the same defect the audit kept finding, in a new place: **the artifact does not
record enough to know whether two numbers are comparable.** Every number in §2 was
assembled by hand for this reason.

**Fixed.** `eval.grounding` and `eval.claims` now each declare a `METRIC_VERSION` beside the
code that defines their semantics; `eval.run` stamps both into every report, and
`eval.rescore` / `eval.recheck` re-stamp what they repair. `eval.compare` checks
comparability before differencing anything and **refuses** a cross-version diff, naming the
command that repairs it. Reports predating the stamp are read as the pre-#41 semantics,
which is what they are, rather than as unknown. Judged metrics are refused across different
judge models for the same reason: a rubric score is only comparable under the judge that
produced it.

Running the exact comparison above now fails closed:

```
Refusing to compare — these reports are not on the same footing:

  - grounding: baseline is v2, candidate is v1 — the scores mean different things.
    Bring the older one forward with:
      python -m eval.rescore <report> --out <rescored>
```

and following that advice yields **grounding +0.04, grounded +6.9pp**, the true figures,
in place of the −0.02 / −17.2pp the tool used to print.

## 6 · What to do next

Not build v3. In priority order:

1. **Fix `eval.compare`** to stamp and check a metric version. It will mislead again otherwise.
2. **Judge the teacher's own rows.** If Opus-written coaching scores near 3.7 on the same
   rubric, the ceiling is the facts block and no amount of distillation moves it. This is
   the highest-information cheap experiment available, and it decides whether the project's
   next move is *more data* or *richer facts*.
3. **Test whether prompting alone buys the citation discipline.** If a constrained prompt
   gets the base model to 0.96 grounding, the fine-tune's remaining advantage is
   obtainable without it.
4. **If richer facts are the answer**, that is an `engine/` change (piece activity, pawn
   structure, king safety, plans), not a training change.

## 7 · Reproduction

```bash
# the control run (29 judge calls, ~25 min)
python -m eval.run --coach-model qwen3:8b --judge anthropic --depth 15 \
    --coach-temperature 0 --max-judge-calls 35 \
    --out eval/reports/prompted_8b_2026-08-14.json --resume

# v2's comparable grounding and claims figures
python -m eval.rescore eval/reports/8b_v2_2026-08-10.json
python -m eval.recheck eval/reports/8b_v2_2026-08-10.json
```

Run `eval.run` detached (`nohup … & disown`): a harness-managed background run was killed
mid-flight once, losing its judge calls. `--resume` plus the incremental sidecar means a
restart does not re-pay for finished games.
