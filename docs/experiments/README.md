# Experiment records

Paper-grade records of every fine-tuning/eval experiment: hypothesis, data lineage,
exact training config, results tables, threats to validity, and reproduction commands.
One file per experiment, newest first. Written to be lifted into an arXiv preprint.

Iteration runs single-seed/single-judge on purpose; [`paper-protocol.md`](./paper-protocol.md)
is the one-time rigor checklist (multi-seed variance, Wilcoxon on the paired design,
second judge, ablations) to run on the final configuration before writing anything up.

**Current resume point:** "Where to resume" at the end of
[`2026-10-10-game-only-vs-mixed-student.md`](./2026-10-10-game-only-vs-mixed-student.md).
Training data is finished and the eight registered sets are built; no student is trained yet.

- [2026-10-10 · Game-only vs mixed student (pre-registered)](./2026-10-10-game-only-vs-mixed-student.md):
  decides whether position rows enter training. Game-only (G) and mixed 1:2 (M) at 400,
  1,000 and **1,700** rows, M also at 2,500 and all (3,645), 3 seeds each (24 runs). Position
  rows stay if the 90% interval of the paired Opus factual difference M − G at 1,700 lies
  above **−0.30** and Gemini's estimate isn't below it. Amends the size sweep in
  `paper-protocol.md`.

- [2026-10-10 · v5 position-row corpus](./2026-10-10-v5-corpus-batch1.md):
  1,900 games, 5,395 rows written with the plain v5 prompt; QC passes 4,649 (86%) and
  **2,690 clear-cut position rows** are available. Confirmation sample before training:
  position rows factual 4.53 with **4 / 100** confirmed errors, game rows 4.73 with 1 / 100.
  Limitation: game rows are templated (84% open with "Let's …").

- [2026-10-10 · Position teacher with and without board tools, paired](./2026-10-10-tools-vs-no-tools-paired.md):
  100 positions, both arms. Factual 4.59 tools vs 4.54 plain; confirmed errors **8 vs 7**
  (McNemar p = 1) at 3.7× input tokens. The tools weren't called on the claims that went
  wrong. The corpus is written without tools. 2608.04240's no-tool baseline got only a FEN,
  so their gain mixes having the information with using tools; this run separates them.

- [2026-10-09 · Tool-augmented teacher: pilot](./2026-10-09-tool-augmented-teacher-pilot.md):
  four python-chess query tools for the teacher. Optional tools go unused at temperature 0;
  forced, pronoun subjects drop 34% → 13%. Veto-only mode still wrote a causal claim its own
  facts contradict. Also the defence-check negation fix and held-out claim metric **v3**.

- [2026-10-08 · Name both pieces in every defence claim](./2026-10-08-explicit-defence-claims.md):
  a prompt rule; pronoun or bare-move subjects 34% → **32%** (bar ≤ 10%). Not followed.
  Records the decision to keep position rows as a stated deviation and let the student
  comparison decide.

- [2026-10-08 · Named defenders](./2026-10-08-named-defenders.md),
  [clear-cut filter](./2026-10-08-clear-cut-position-rows.md),
  [evaluation in words](./2026-10-08-position-facts-eval-words.md),
  [board in the facts](./2026-10-07-position-facts-board.md):
  four pre-registered position-row versions. Factual rose 4.19 → 4.38 → 4.44 → 4.55 → 4.51
  and rows ≤ 3 fell 18% → ~6%, but confirmed errors stayed at **5–8%** (pooled no-tools
  29 / 500 = 5.8%, 4.1–8.2%). Each change removed the error it targeted (misplaced pieces,
  the eval's sign, misread engine lines); what remains is causal stories about which piece
  defends what. Adds the `eval_sign` and `invented_defence` QC checks and `training.clear_cut`.

- [2026-10-07 · DeepSeek training rows and the placement audit](./2026-10-07-deepseek-training-rows-and-placement-audit.md):
  7,669 rows from the 2,000-game corpus, 94% pass QC. Placement flags are **14 / 50 real
  (28%)**; the filter is kept anyway. Opus spot-check: game rows factual 4.78, position rows
  4.19 with 8 / 150 false on the board, which started the position-row work above. Split
  90/10 by game; the 91 held-out games are the only test set.

- [2026-09-26 · Label stability from depth 18 to 20](./2026-09-26-depth-20-label-stability.md):
  7 of 85 rule-sorted labels change (8%, against 12% from 16 to 18) and oscillate rather than
  settle. Depth stays 18; headline results are repeated on the **73 label-stable games**.

- [2026-09-26 · DeepSeek-V4 Pro as coach on 91 games, depth 18](./2026-09-26-deepseek-teacher-91-games-d18.md):
  the teacher gate. **Factual 4.74** (4.77 on the stable 73), overall 4.77, Opus judge.
  Claim checker v2 cuts DeepSeek's flags 7 → 2, both real. Gate passed.

- [2026-09-13 · Literature refresh](./2026-09-13-literature-refresh.md):
  ACT-Eval (arXiv 2608.04240) is the closest neighbour and removes both "no prior work"
  claims; the paper is reframed around three cheap references and how each misled. The
  11 Oct addendum covers work on the errors the position-row versions didn't fix.

- [2026-09-13 · Gate 3: a second judge](./2026-09-13-gate3-cross-judge.md):
  Gemini 3.1 Pro re-judges the same text. Factual agreement with Opus r = 0.51–0.65, and
  Gemini is harsher. Fine-tune − base factual is **+0.00 under Opus, +0.41 under Gemini**
  (neither significant): the §6 tie is one judge's reading. The judges name the same errors
  and disagree on severity.

- [2026-09-20 · Control: a coach with no model in it](./2026-09-20-template-control.md):
  a deterministic template built from the same facts block. **Factual 5.00** against 3.72
  (Opus) / 2.86–3.28 (Gemini) for the 8B arms, and **overall 4.22 vs 4.14–4.17**, so a script
  ties or beats both 8B models on this rubric. The LLM's contribution is actionability
  (template 2.83 vs 3.59–3.72). Also fixes `eval.rejudge` leaving the first judge's means in
  `aggregate`.

- [2026-08-14 · The prompted-8B control](./2026-08-14-prompted-8b-control.md):
  the comparison the project was missing. Same base weights, same prompt, same held-out
  set, only the LoRA differs. **Judged factual is identical: 3.72 both.** Fine-tuning bought
  citation discipline (grounding 0.923 → 0.965, 79% → 86% fully grounded) and nothing the
  judge can see; overall is 0.03 *worse* and the control has fewer claim violations. Against
  the proposed gate (factual ≥ control + 0.30) v2 misses by the whole margin. Also documents
  an `eval.compare` defect that **inverted the grounding delta** by differencing two metric
  versions.

- [2026-08-13 · Re-deriving the release gates](./2026-08-13-gates-re-derived.md):
  the 0.85 grounding gate is cleared by every model after #41, and the **prompted-3B
  reference is retired**: comparing an 8B fine-tune to a prompted 3B confounds the size
  jump with the fine-tune and cannot answer whether fine-tuning beats prompting the same
  base. The control is **prompted `qwen3:8b`**. Backfills the claim metrics and finds
  **claims discriminates less than grounding, not more** (v1→v2: +0.008 vs +0.075), so
  neither deterministic metric can be the progress gate. Proposes factual **≥ control
  + 0.30** as the progress gate, with **zero claim violations** and **≥27/29 grounded
  games** as free regression tripwires.

- [2026-08-11 · Audit: what the grounding metric cannot see](./2026-08-11-grounding-metric-audit.md):
  the cheap gate is wrong in **both** directions: blind to the dominant factual failure (role
  inversion, move-type misreading, invented board state, all scoring grounding up to **1.00**),
  while **84–94% of what it flags is a bare-square parser false positive** that also discarded
  **64/64** paid teacher rows. *r*(grounding, factual) = **+0.39**; 62% of games sit at the
  metric's ceiling. Revises the "concentrated weakness" reading as under-powered noise.
  **Step 1 shipped (#41):** corrected grounding is baseline **0.861** / v1 **0.890** / v2
  **0.965**, so v1 never regressed grounding and the 0.85 gate was already met by the
  prompted baseline; 52 of the 64 dropped rows recovered at zero teacher cost.
  **Step 2 shipped (#43):** `eval/claims.py` catches role inversion and invented castling
  at **0/467 false positives** on teacher output, every hit landing on a judge-scored 1–2
  game, but **recall is 1 of 7**, so the residual factual gap is invented board state,
  which needs position replay.

- [2026-08-10 · Ablation: shape vs volume](./2026-08-10-ablation-shape-vs-volume.md):
  retraining on `kind`-filtered subsets shows v2's grounding gain came from **row shape, not
  volume**: more whole-game rows moved nothing (0.79→0.76), position rows moved a lot
  (→0.86), and the mixture beat both pure arms (0.91). Zero teacher calls.

- [2026-08-10 · Qwen3-8B QLoRA on the v2 mixed-granularity dataset](./2026-08-10-qwen3-8b-qlora-v2.md):
  **grounding gate met** (0.79→0.91, grounded games 41%→62%); factual 3.45→3.72, still short of
  the 4.0 gate. Adding per-position rows fixed citation discipline without regressing whole-game
  structure (clarity and actionability both rose); clean_draw now perfectly grounded (1.00).

- [2026-08-08 · Qwen3-8B QLoRA (v1 dataset) vs prompted 3B baseline](./2026-08-08-qwen3-8b-qlora-v1.md):
  **beats baseline** (overall 3.38→3.97, factual 2.90→3.45; clean_draw hallucination
  fixed 0.38→0.88 grounding); gates (grounding ≥0.85, factual ≥4.0) not yet met;
  the new failure mode is citation discipline, targeted by the v2 per-position dataset.

Conventions: judged metrics come from `eval.run` (coach temperature 0, `--judge anthropic`;
re-judging with `eval.rejudge`, `--batch` for the Message Batches API); comparisons from
`eval.compare` and `eval.equivalence`; the underlying JSON reports are committed in
`eval/reports/`. Up to 20 Sep the held-out set was 29 games at Stockfish depth 15. From
26 Sep it is 91 games at depth 18 (the original 29 included), and the two are not compared.
