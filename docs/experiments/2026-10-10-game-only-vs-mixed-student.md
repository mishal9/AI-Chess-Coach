# Game-only vs mixed student, and the amended size sweep

**Status:** pre-registered 10 Oct 2026, before any student was trained and before the corpus
was finished. The user fixed the three open choices of the draft that day (see "Choices").
Nothing below changes once the first student trains. It amends the size sweep in
`paper-protocol.md`.

## Question

Position rows carry about 6% confirmed errors (pooled 25 / 400, 95% Wilson 4.3–9.1%), over
the 5% bar set for training rows. On 8 Oct the user kept them as a stated deviation, to be
settled by the student: **does training on game and clear-cut position rows (mixed) make the
student less factual on the held-out games than training on game rows alone?** If it does,
the position rows come out of the paper's training set.

The August ablation (`2026-08-10-ablation-shape-vs-volume.md`; 29 games, grounding only,
older rows) found position rows drove the grounding gain, and the mixture beat either pure
arm (0.91 vs 0.86 position-only vs 0.76 game-only). It did not measure factual accuracy,
which is what the error rate threatens.

## Why the registered sweep changes

`paper-protocol.md` (25 Sep) registered nested sizes of 400, 1,000, 2,500 and 5,000 train
rows at a fixed 1 game : 2 position mix. The sweep has not started, and two facts found
since make it unbuildable as written:

- Only **clear-cut** position rows are kept (`2026-10-08-clear-cut-position-rows.md`). With
  every corpus game written by the v5 prompt, the full corpus yields about 2,630 of them
  (`2026-10-10-v5-corpus-batch1.md`). At 1:2 that caps the mixed train split at about
  3,550 rows. **5,000 cannot be reached.**
- A game-only arm has at most 1,928 game rows, about **1,735** in a 90% train split.

## Design

**Arms.** Both arms use the same recipe as v2: Qwen3-8B, the QLoRA config in
`training/qlora_8b_runpod.ipynb`, and the 90/10/0 split by game (`training.dataset --ratios
0.9 0.1 0`). Row-level filters are QC passed, grounding 1.0 and, for position rows, the
clear-cut filter.

- **G (game-only):** QC-passed DeepSeek game rows (`deepseek_qc.jsonl`, kind `game`).
- **M (mixed):** the same game rows plus clear-cut v5 position rows, at 1 game : 2
  position. Position rows come only from the v5 prompt without tools: the explicit100,
  batch 1 and later games in `raw_deepseek_pos_v5.jsonl`, the paired100 plain arm, and the
  354 earlier sample games (`spotcheck146`, `pilot10`, `clearcut100`, `named100`) rewritten
  with v5. Their older-prompt rows are not used. Those 354 games helped develop the facts
  block and the QC checks. Their new rows are fresh text that QC scores like any other row,
  and they are corpus games, never held-out ones.

**Sizes (train rows), nested.** Each size is a superset of the smaller ones, drawn by a
seeded shuffle of whole games, so only size varies within an arm:

| Size | G | M | Role |
|---|---|---|---|
| 400 | ✓ | ✓ | v2's size, like for like |
| 1,000 | ✓ | ✓ | |
| **1,700** | ✓ | ✓ | **the decision point: the largest size G can fill** |
| 2,500 | | ✓ | |
| all at 1:2 (≈ 3,550) | | ✓ | replaces the registered 5,000 |

**Seeds.** 0, 1 and 2 at every point: 24 QLoRA runs.

**Scoring** on all 91 held-out games, coach temperature 0:

- **Every run:** grounding (`METRIC_VERSION` 2) and claims (`METRIC_VERSION` 3). Claims now
  include the defence check against every position of the game, a sensor for position-row
  defence claims leaking into game coaching. These metrics are deterministic and free.
- **Judged:**
  - **Opus 4.8 and Gemini 3.1 Pro** judge all 3 seeds of both arms at 1,700, the decision
    point (6 runs).
  - **Opus 4.8 alone** judges seed 0 at every other point, plus seeds 1 and 2 of M at 400
    and at the top size, the endpoint calibration the protocol already registered
    (10 runs).

  That is 16 judged runs in all.

## Decision rule

Primary measure: per-game Opus factual score, averaged over the 3 seeds of each arm at
1,700, then paired by game (M − G, 91 games).

**Non-inferiority, δ = 0.30.** Position rows stay in if both of these hold:
- the two-sided 90% confidence interval of the mean paired difference (t-interval over 91
  games) lies entirely above −0.30;
- the same difference under Gemini has a point estimate not below −0.30.

Otherwise they come out, and the paper's student trains on game rows only. δ = 0.30 is the
equivalence margin the protocol already named. With 91 games and a per-game SD of about
1.16, the interval's half-width is about ±0.20, less once seeds are averaged.

Reported either way:
- the paired difference with its interval and a Wilcoxon signed-rank p-value;
- better / same / worse counts by game;
- grounding, the claims-clean rate and `invented_defence` counts per arm and size;
- the Gemini result;
- per-bucket factual scores;
- the full size curve for both arms, flat or not.

## What follows from each outcome

- **Position rows stay:** M is the paper's student. The size curve runs to the top of M,
  and the headline is M at the top size.
- **Position rows come out:** G is the paper's student. The curve stops at 1,700, which is
  stated plainly as the most game rows the corpus holds. The M results are reported as the
  ablation that removed them.

## Choices (fixed by the user, 10 Oct 2026)

- **A. Decision rule:** non-inferiority at δ = 0.30, above. The strict alternative ("any
  lower mean removes the rows") was rejected: with equal arms it would remove them about
  half the time by chance.
- **B. Corpus:** every position row from the v5 prompt. The 354 older-prompt sample games
  are rewritten, about $1 more.
- **C. Budget:** Gemini judges only the decision point. The estimate is about $24–48 of GPU
  (24 runs) and about $31 of judging (6 runs at about $3 with both judges, 10 at about
  $1.30 with Opus alone), plus about $3.80 of DeepSeek to finish the corpus (1,300 games at
  $0.0029).

## Not decided here

The template-trained (no teacher) comparison arm registered in the protocol keeps its own
sizes. The prompted-8B, template, v2 and DeepSeek-as-coach arms are scored once, together
with these runs, on the same 91 games and judges.
