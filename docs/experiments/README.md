# Experiment records

Paper-grade records of every fine-tuning/eval experiment: hypothesis, data lineage,
exact training config, results tables, threats to validity, and reproduction commands.
One file per experiment, newest first. Written to be lifted into an arXiv preprint.

Iteration runs single-seed/single-judge on purpose; [`paper-protocol.md`](./paper-protocol.md)
is the one-time rigor checklist (multi-seed variance, Wilcoxon on the paired design,
second judge, ablations) to run on the final configuration before writing anything up.

- [2026-08-11 · Audit: what the grounding metric cannot see](./2026-08-11-grounding-metric-audit.md) —
  the cheap gate is wrong in **both** directions: blind to the dominant factual failure (role
  inversion, move-type misreading, invented board state — all scoring grounding up to **1.00**),
  while **84–94% of what it flags is a bare-square parser false positive** that also discarded
  **64/64** paid teacher rows. *r*(grounding, factual) = **+0.39**; 62% of games sit at the
  metric's ceiling. Revises the "concentrated weakness" reading as under-powered noise.

- [2026-08-10 · Ablation: shape vs volume](./2026-08-10-ablation-shape-vs-volume.md) —
  retraining on `kind`-filtered subsets shows v2's grounding gain came from **row shape, not
  volume**: more whole-game rows moved nothing (0.79→0.76), position rows moved a lot
  (→0.86), and the mixture beat both pure arms (0.91). Zero teacher calls.

- [2026-08-10 · Qwen3-8B QLoRA on the v2 mixed-granularity dataset](./2026-08-10-qwen3-8b-qlora-v2.md) —
  **grounding gate met** (0.79→0.91, grounded games 41%→62%); factual 3.45→3.72, still short of
  the 4.0 gate. Adding per-position rows fixed citation discipline without regressing whole-game
  structure (clarity and actionability both rose); clean_draw now perfectly grounded (1.00).

- [2026-08-08 · Qwen3-8B QLoRA (v1 dataset) vs prompted 3B baseline](./2026-08-08-qwen3-8b-qlora-v1.md) —
  **beats baseline** (overall 3.38→3.97, factual 2.90→3.45; clean_draw hallucination
  fixed 0.38→0.88 grounding); gates (grounding ≥0.85, factual ≥4.0) not yet met —
  new failure mode is citation discipline, targeted by the v2 per-position dataset.

Conventions: judged metrics come from `eval.run` (29-game held-out set,
`--judge anthropic`, coach temperature 0); comparisons from `eval.compare`; the
underlying JSON reports are committed in `eval/reports/`.
