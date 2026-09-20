# Experiment records

Paper-grade records of every fine-tuning/eval experiment: hypothesis, data lineage,
exact training config, results tables, threats to validity, and reproduction commands.
One file per experiment, newest first. Written to be lifted into an arXiv preprint.

Iteration runs single-seed/single-judge on purpose; [`paper-protocol.md`](./paper-protocol.md)
is the one-time rigor checklist (multi-seed variance, Wilcoxon on the paired design,
second judge, ablations) to run on the final configuration before writing anything up.

- [2026-09-20 · Control: a coach with no model in it](./2026-09-20-template-control.md) —
  a deterministic template built from the same facts block. **Factual 5.00** against 3.72
  (Opus) / 2.86–3.28 (Gemini) for the 8B arms, and **overall 4.22 vs 4.14–4.17**, so a script
  ties or beats both 8B models on this rubric. The LLM's real contribution is actionability
  (template 2.83 vs 3.59–3.72). Also fixes `eval.rejudge` leaving the first judge's means in
  `aggregate`.

- [2026-08-14 · The prompted-8B control](./2026-08-14-prompted-8b-control.md) —
  the comparison the project was missing. Same base weights, same prompt, same held-out
  set, only the LoRA differs. **Judged factual is identical: 3.72 both.** Fine-tuning bought
  citation discipline (grounding 0.923 → 0.965, 79% → 86% fully grounded) and nothing the
  judge can see; overall is 0.03 *worse* and the control has fewer claim violations. Against
  the proposed gate (factual ≥ control + 0.30) v2 misses by the whole margin. Also documents
  an `eval.compare` defect that **inverted the grounding delta** by differencing two metric
  versions.

- [2026-08-13 · Re-deriving the release gates](./2026-08-13-gates-re-derived.md) —
  the 0.85 grounding gate is cleared by every model after #41, and the **prompted-3B
  reference is retired**: comparing an 8B fine-tune to a prompted 3B confounds the size
  jump with the fine-tune and cannot answer whether fine-tuning beats prompting the same
  base. The control is **prompted `qwen3:8b`**. Backfills the claim metrics and finds
  **claims discriminates less than grounding, not more** (v1→v2: +0.008 vs +0.075), so
  neither deterministic metric can be the progress gate. Proposes factual **≥ control
  + 0.30** as the progress gate, with **zero claim violations** and **≥27/29 grounded
  games** as free regression tripwires.

- [2026-08-11 · Audit: what the grounding metric cannot see](./2026-08-11-grounding-metric-audit.md) —
  the cheap gate is wrong in **both** directions: blind to the dominant factual failure (role
  inversion, move-type misreading, invented board state — all scoring grounding up to **1.00**),
  while **84–94% of what it flags is a bare-square parser false positive** that also discarded
  **64/64** paid teacher rows. *r*(grounding, factual) = **+0.39**; 62% of games sit at the
  metric's ceiling. Revises the "concentrated weakness" reading as under-powered noise.
  **Step 1 shipped (#41):** corrected grounding is baseline **0.861** / v1 **0.890** / v2
  **0.965** — so v1 never regressed grounding and the 0.85 gate was already met by the
  prompted baseline; 52 of the 64 dropped rows recovered at zero teacher cost.
  **Step 2 shipped (#43):** `eval/claims.py` catches role inversion and invented castling
  at **0/467 false positives** on teacher output, every hit landing on a judge-scored 1–2
  game — but **recall is 1 of 7**, so the residual factual gap is invented board state,
  which needs position replay.

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
