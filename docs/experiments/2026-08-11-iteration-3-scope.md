# Iteration 3: scope

**Date:** 2026-08-11
**Status:** scoped, not started
**Standing gates:** grounding ≥ 0.85 (v2: **0.91 ✅**), judge factual ≥ 4.0 (v2: **3.72 ✗**)

## The planned direction was based on a misdiagnosis

After v2, the recorded next step was: *"spend teacher calls on POSITION rows for one_blunder
(factual 3.20) and inaccuracies (3.40) — not more whole games."* Reading the actual judge
rationales for those buckets says that would buy very little.

> **Superseded in part by the fuller audit:
> [2026-08-11 · what the grounding metric cannot see](./2026-08-11-grounding-metric-audit.md).**
> Reading every rationale (not just the two lagging buckets) shows the failure spans **five of
> six buckets**, in three classes, and that the per-bucket concentration was under-powered
> noise. The step sequencing below is unchanged; the targeting rationale is corrected there.

### Finding 1: the factual gap is role confusion, not missing coverage

The four low-factual games in the two lagging buckets fail the same way: the coaching cites
moves that **are** in the facts block, but swaps **who played what**.

| bucket | factual | grounding | what the judge caught |
|---|---|---|---|
| one_blunder | 2 | **1.00** | *"13.Qd2 instead you castled"* — Qd2 **is** the played move |
| one_blunder | 2 | 0.86 | *"When you played Nf3 or g3 instead"* — g3 was the **engine's** preference |
| inaccuracies | 2 | 0.71 | *"chose a passive rook move (Rc8)"* — player played Bc6; **Rc8 was the engine's** |
| inaccuracies | 3 | 0.67 | *"worked well enough to get the result"* — White **lost** 0-1 |

Two of these score grounding **1.00 / 0.86**. The grounding metric is a set-membership check
over cited moves, so it is structurally blind to a played↔preferred role swap. That is
why grounding cleared its gate while factual stalled.

**Consequence:** more position rows of the same shape do not address this. The model has
plenty of them (178 position rows already exist across 65 corpus games in these two profiles).
It has a role-binding problem, not a coverage problem.

### Finding 2: the grounding metric has a false-positive class, and it is expensive

`_SAN_RE` in `eval/grounding.py` makes the piece letter optional, so a bare square in prose
("the rook from b7 to b8", "the e5 square") parses as a pawn move and, if absent from the
facts, scores as a **hallucination**.

| report | hallucinated tokens | bare squares |
|---|---|---|
| 8b_v2_2026-08-10 | 17 | **16 (94%)** |
| 8b_v1_2026-08-08 | 49 | 46 (94%) |
| baseline_29g_2026-07-10 | 32 | 27 (84%) |

And on the training side: **64 of 64 rows dropped by the v2 distillation gate failed on bare
squares alone** (56 position, 8 game). Those are already-paid Opus rows discarded for naming
squares, not for inventing moves. It also plausibly explains why inaccuracy positions had the
lowest teacher gate rate (80% vs 91% blunder): positional coaching names squares more.

A bare square *can* be a genuine invented pawn move, so the fix is
context-sensitive extraction, not dropping bare squares.

## Scope

Sequenced cheapest-and-most-informative first. The teacher spend moves to **last**, gated on
evidence.

### Step 1: fix the metric, re-score everything (free, no API)

- Context-aware bare-square handling in `extract_moves` (require a move-ish context: move
  number prefix, `!`/`?` annotation, or presence in the facts' move list; exclude
  `on/at/to/from/the <sq>` and `<sq> square/pawn/file/outpost`).
- Re-score the three stored reports offline. The coaching text is saved, so this needs no
  model and no judge.
- Re-run the gate over `raw_v2.jsonl` → **recover ~64 already-paid rows** → v3 dataset
  ≈ 467 rows vs v2's 403, for **zero teacher calls**.

Deliverable: corrected grounding for baseline/v1/v2, plus a bigger dataset for free.
Caveat to state in the write-up: part of the v1→v2 grounding gain (0.79→0.91) was the model
learning to stop naming squares, which the corrected metric will re-attribute.

### Step 2: measure the real failure (free, no API)

Add a deterministic **role-confusion check** to `eval/`: for each cited move, compare the role
the coaching assigns it (player played it / engine preferred it) against the facts. A coarse
version catches all four swaps in the table above.

Two payoffs:
- Turns the invisible failure into a number tracked per-bucket alongside grounding.
- Drop it into the distillation gate so role-swapped **teacher** rows get retried; the teacher
  is nondeterministic and `--retries` already works (86% recovery rate observed).

### Step 3: retrain on v3 (~$0.40 GPU, no teacher calls)

Reuse `training/qlora_8b_runpod.ipynb`, tag `qwen-coach-8b-v3`. Evaluate grounding-only first
(`eval.run --no-judge`), which is free and deterministic, then the judged rubric (~29 Claude calls).

**Decision point:** if factual is still < 4.0 *and* the new role-confusion metric is still bad,
the data lacks role-contrast examples → proceed to step 4. If role confusion is fixed
but factual lags for other reasons, re-scope from the new rationales rather than buying rows.

### Step 4: targeted distill run (only if step 3 says so; ~$1.50–4 teacher)

```bash
python -m training.corpus            # re-assemble; keeps held-out disjoint
python -m training.distill \
    --sources data/games/manifest.json \
    --out data/distill/raw_v3_targeted.jsonl \
    --no-game-rows \                 # position rows only; don't re-pay for game rows
    --positions-per-game 8 \
    --retries 2 \
    --max-teacher-calls 1200
```

Note `--positions-per-game` is **not** the binding constraint today: only 42 of 127 games hit
the cap of 4 (28 games have 1 position, 37 have 2). Raising it to 8 yields perhaps +50–80 rows.
Real volume requires **more corpus games of the target profiles**. `training/corpus.py` fetches
CC0 games free; bucket them with `eval.expand_heldout.classify()`, which is already a pure
function of the analyzed report.

## Budget

| step | teacher/judge | GPU | note |
|---|---|---|---|
| 1 metric fix + re-score | $0 | $0 | recovers ~64 paid rows |
| 2 role-confusion metric | $0 | $0 | |
| 3 v3 retrain + eval | ~29 judge calls | ~$0.40 | grounding-only pass is free |
| 4 targeted distill | ~$1.50–4 | ~$0.40 | conditional |

Anthropic credits remain the binding constraint (RunPod ~$9.40 left; a retrain is ~$0.40).

## Open item carried forward

Cell-6 `eval_loss` was never captured from either pod run, so 3-epoch overfit is still unruled
out. Capture it on the step-3 run.
