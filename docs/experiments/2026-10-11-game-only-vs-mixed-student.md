# Game-only vs mixed student, and the amended size sweep

**Status: DRAFT, not registered.** It becomes the registration when the user approves the
open choices below, and is committed with that date before any student is trained. Nothing
in it has run.

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

- Only **clear-cut** position rows are kept (`2026-10-08-clear-cut-position-rows.md`). The
  full corpus yields about 2,170 of them, or about 2,630 if the 354 older-prompt sample games
  are redone (`2026-10-10-v5-corpus-batch1.md`). At 1:2 that caps the mixed train split
  at about 2,900 rows (or about 3,550). **5,000 cannot be reached.**
- A game-only arm has at most 1,928 game rows, about **1,735** in a 90% train split.

## Design

**Arms.** Both arms use the same recipe as v2: Qwen3-8B, the QLoRA config in
`training/qlora_8b_runpod.ipynb`, and the 90/10/0 split by game (`training.dataset --ratios
0.9 0.1 0`). Row-level filters are QC passed, grounding 1.0 and, for position rows, the
clear-cut filter.

- **G (game-only):** QC-passed DeepSeek game rows (`deepseek_qc.jsonl`, kind `game`).
- **M (mixed):** the same game rows plus clear-cut v5 position rows, at 1 game : 2
  position.

**Sizes (train rows), nested.** Each size is a superset of the smaller ones, drawn by a
seeded shuffle of whole games, so only size varies within an arm:

| Size | G | M | Role |
|---|---|---|---|
| 400 | ✓ | ✓ | v2's size, like for like |
| 1,000 | ✓ | ✓ | |
| **1,700** | ✓ | ✓ | **the decision point: the largest size G can fill** |
| 2,500 | | ✓ | |
| all at 1:2 (≈ 2,900 or ≈ 3,550) | | ✓ | replaces the registered 5,000 |

**Seeds.** 0, 1 and 2 at every point: 24 QLoRA runs.

**Scoring** on all 91 held-out games, coach temperature 0:

- **Every run:** grounding (`METRIC_VERSION` 2) and claims (`METRIC_VERSION` 3). Claims now
  include the defence check against every position of the game, a sensor for position-row
  defence claims leaking into game coaching. These metrics are deterministic and free.
- **Judged (Opus 4.8 primary, Gemini 3.1 Pro second):**
  - all 3 seeds of both arms at 1,700;
  - seed 0 at every other point;
  - plus seeds 1 and 2 of M at 400 and at the top size, the endpoint calibration the
    protocol already registered.

  That is 16 judged runs.

## Decision rule (open choice A, below)

Primary measure: per-game Opus factual score, averaged over the 3 seeds of each arm at
1,700, then paired by game (M − G, 91 games).

- **Recommended (non-inferiority, δ = 0.30):** position rows stay in if the 90% confidence
  interval of the mean paired difference lies above −0.30, and Gemini's point estimate is
  not below −0.30. Otherwise they come out, and the paper's student trains on game rows
  only. δ = 0.30 is the equivalence margin the protocol already named. With 91 games and a
  per-game SD of about 1.16, the interval's half-width is about ±0.20 (less once seeds are
  averaged).
- **Alternative (strict):** position rows come out if M's mean is lower at all. This is
  simpler, but if the arms are truly equal it removes the rows about half the time by
  chance.

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

## Open choices for the user

- **A. Decision rule:** non-inferiority at δ = 0.30 (recommended), or strict.
- **B. Redo the 354 older-prompt sample games with v5** (about $1 more): M's top size is
  then about 3,550 train rows instead of about 2,900, and every position row comes from one
  prompt.
- **C. Budget:** about $24–48 GPU (24 runs) and about $48 of judging (16 judged runs at about
  $3 for Opus plus Gemini on 91 games), plus about $2.75–3.75 of DeepSeek to finish the
  corpus. A cheaper variant judges only Opus outside the decision point (about $35 of
  judging).

## Not decided here

The template-trained (no teacher) comparison arm registered in the protocol keeps its own
sizes. The prompted-8B, template, v2 and DeepSeek-as-coach arms are scored once, together
with these runs, on the same 91 games and judges.
