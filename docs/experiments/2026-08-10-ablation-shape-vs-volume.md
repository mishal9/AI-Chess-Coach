# Ablation: did v2's grounding gain come from data *volume* or data *shape*?

**Date:** 2026-08-10 · **Status:** complete · **Cost:** ~$1.20 GPU, **zero teacher calls**, zero judge calls

The [v2 fine-tune](./2026-08-10-qwen3-8b-qlora-v2.md) changed two things at once — 3.9× more
training rows *and* a new row shape (per-critical-position rows alongside whole-game rows) —
so its +0.12 grounding gain could not be attributed. Retraining on `kind`-filtered subsets of
the same dataset separates them for the price of GPU time.

**Answer: shape. Adding more whole-game rows does nothing for grounding; adding position rows
does. But the mixture beats either pure arm, so whole-game rows are not merely ballast.**

---

## 1 · Design

Four models, all Qwen3-8B QLoRA with identical hyperparameters (r=16, α=32, 3 epochs, eff.
batch 16, lr 1e-4, seed 0). Arms differ only in which rows of `data/distill/raw_v2.jsonl`
survive the `--kind` filter; the strict 1.0 grounding gate and the leakage-safe per-game split
are unchanged, so every arm is drawn from the same pool with the same quality bar.

| Arm | Train rows | Row shape |
|---|---|---|
| v1 (prior experiment) | 82 | whole-game only |
| **game-only** | **101** | whole-game only |
| **position-only** | **218** | single-position only |
| v2 mixed (prior experiment) | 319 | both |

The game-only arm is the key control: it is v1's *shape* with **more and better rows** (it
includes the 25 gate-failures recovered by `--retries`). If volume drove v2's gain, this arm
should move toward 0.91.

**Metric: grounding only** (`eval.run --no-judge`). Grounding is deterministic, costs nothing,
and is the metric v2 moved (+0.12) — the right instrument for this question. It also keeps the
ablation free, preserving Claude credits for iteration 3.

## 2 · Results (29 held-out games, coach temp 0)

| Model | Train rows | Shape | Grounding | Grounded games | Worst-move |
|---|---|---|---|---|---|
| v1 | 82 | game | 0.79 | 41% | 72% |
| **game-only** | 101 | game | **0.76** | 34% | 72% |
| **position-only** | 218 | position | **0.86** | 45% | 72% |
| v2 mixed | 319 | both | **0.91** | 62% | 72% |

Per-bucket grounding deltas, game-only → position-only (the shape contrast):

| Bucket | Δ grounding |
|---|---|
| slow_loss | +0.18 |
| one_blunder | +0.14 |
| clean_draw | +0.12 |
| inaccuracies | +0.10 |
| multi_blunder | +0.08 |
| two_mistakes | −0.03 |

Position rows help in five of six buckets — a broad effect, not one bucket carrying the mean.

### Findings

1. **Volume of whole-game rows buys nothing.** v1 (82 rows) → game-only (101 rows, plus 25
   recovered high-quality rows) moved grounding 0.79 → 0.76. Flat-to-slightly-down; certainly
   not toward 0.91. This is the cleanest comparison in the study — same shape, same recipe,
   only the row count differs — and it falsifies the volume hypothesis directly.
2. **Row shape is the active ingredient.** Position-only reaches 0.86 versus game-only's 0.76,
   improving in five of six buckets.
3. **The mixture beats either pure arm (0.91 > 0.86 > 0.76).** Whole-game rows are *not* merely
   protecting clarity and actionability, as the v2 record hypothesized — they contribute to
   grounding too, but only in combination with position rows. The gap is widest on the strict
   per-game measure: 62% of games perfectly grounded for mixed versus 45% for position-only.
4. **Worst-move identification is invariant at 72.4% across all four models.** No dataset
   change moved it, which suggests it is set by the facts block (the engine's worst move is
   always stated) rather than anything learnable from these rows — a metric to stop optimizing.

## 3 · Threats to validity

- **The design is not fully factorial.** Arm size is determined by the filter, so `game-only`
  (101) and `position-only` (218) differ in *both* shape and volume. The volume hypothesis is
  falsified cleanly by v1 → game-only (same shape, +19 rows, no gain), but the mixed-vs-
  position-only comparison (319 vs 218) still confounds the two. **Cheap fix, no teacher calls:**
  subsample position-only to 101 rows and retrain (~$0.40) for a matched-size shape contrast.
- **Single seed per arm.** Differences of ~0.03 (v1 vs game-only) are within plausible seed
  noise on n=29; the ~0.10–0.15 differences are not, but the paper protocol's 3-seed run is
  what would establish that.
- **Grounding only.** These arms were never judged, so the ablation says nothing about whether
  position-heavy training costs clarity or actionability. v2's judged run showed the mixture
  does not, but a pure position-only model is unmeasured on those axes.
- **Shared metric definition.** The training gate and the reported metric are the same grounding
  function, as noted in the v2 record.

## 4 · Consequences for iteration 3

- **Spend teacher calls on position rows, not whole games** — specifically for the buckets
  holding factual down (`one_blunder` 3.20, `inaccuracies` 3.40). Whole-game rows are already
  at the point of diminishing returns for grounding.
- **Keep the mixture.** Do not drop whole-game rows; they contribute beyond format retention.
- **Stop reporting worst-move % as a model-quality signal** — it has not moved across four
  models and one prompted baseline.

## 5 · Reproduction

```bash
python -m training.dataset --in data/distill/raw_v2.jsonl \
    --out-dir training/datasets/v2-game-only --kind game --as-chat
python -m training.dataset --in data/distill/raw_v2.jsonl \
    --out-dir training/datasets/v2-position-only --kind position --as-chat
# train each arm: training/qlora_8b_runpod.ipynb with RUN_TAG / DATA_SUBDIR set per arm
python -m eval.run --coach-model qwen-coach-8b-abl-game --no-judge \
    --out eval/reports/abl_game_only_2026-08-10.json
python -m eval.run --coach-model qwen-coach-8b-abl-pos  --no-judge \
    --out eval/reports/abl_pos_only_2026-08-10.json
```

Both arms trained on one RunPod RTX 4090 in a single session (~$1.20 total). Running two arms
in one kernel surfaced a latent notebook leak — the fp16 merge was never freed after saving,
starving the second arm's 4-bit load (fixed in PR #37).
