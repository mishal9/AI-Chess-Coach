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

## Where to resume (state at 11 Oct 2026)

Written so the next session can pick up from here. **This is the project's current resume
point.** The "Where to resume" sections in earlier notes are superseded.

### State

Everything up to training is on `master` (`97f638a`; PRs #74–#77 merged; 633 tests pass):

- the v5 position-row corpus;
- the eight registered training sets;
- the confirmation samples;
- batch judging.

No student has been trained, so the registration above still holds unchanged.

### Decisions taken, in order

| Date | Decision | Where recorded |
|---|---|---|
| 8 Oct | Keep position rows as a stated deviation from the 5% bar. This comparison decides whether they enter training. | `2026-10-08-explicit-defence-claims.md` |
| 8 Oct | DeepSeek stays the teacher. Its terms allow distillation; Gemini's forbid developing competing models, and Gemini is a judge. | `2026-10-09-tool-augmented-teacher-pilot.md` |
| 10 Oct | Fold the pending v5 judge into a paired tools vs no-tools run. | `2026-10-08-explicit-defence-claims.md` |
| 10 Oct | Write the corpus with the plain v5 prompt, no tools: tools 8 vs no tools 7 confirmed errors in 100 paired rows. | `2026-10-10-tools-vs-no-tools-paired.md` |
| 10 Oct | The defence-check negation fix; the held-out claim metric becomes v3. | `2026-10-09-tool-augmented-teacher-pilot.md` |
| 10 Oct | Keep the checker v2 placement filter; split 90/10/0 by game. | `2026-10-07-deepseek-training-rows-and-placement-audit.md` |
| 10 Oct | This registration: non-inferiority at δ = 0.30; every position row from v5; Gemini only at the decision point. | above |
| 11 Oct | The confirmation samples pass (position 4 / 100, game 1 / 100), so training proceeds. | `2026-10-10-v5-corpus-batch1.md` |
| 11 Oct | Judge with the Message Batches API (half price, same requests). Prompt caching cannot apply: the judge prefix is under Opus 4.8's 1,024-token minimum. | PR #77; `eval/backends.py` |

### Numbers to carry

- **Position rows, confirmed errors:**

  | Sample | Errors |
  |---|---|
  | Old one-line facts | 5.3% |
  | Board in the facts | 7.5% |
  | v3 | 6.0% |
  | Clear-cut filter | 6.0% |
  | Named defenders | 6.0% |
  | v5, paired | 7.0% |
  | Batch-2 confirmation | 4.0% |

  Pooled across the no-tools samples: 29 / 500 = 5.8% (95% Wilson 4.1–8.2%). This is a lower
  bound: only rows the judge scored 3 or lower were board-checked.
- **Game rows:** 1 / 150 confirmed (factual 4.71–4.78).
- **v5 corpus:** 1,900 games, 5,395 rows, 4,649 passing QC, and 2,690 clear-cut position rows
  (with `paired100`).
- **Training sets:** G-400, G-1000, G-1700, M-400, M-1000, M-1700, M-2500, and M-all (3,645 rows).
- **Templating:** DeepSeek's game rows are heavily templated (84% open with "Let's …"; 76% have
  "To work on:"). This is a stated limitation.

### Next steps, in order

1. **Get the training notebook ready** (`training/qlora_8b_runpod.ipynb`). It hard-codes
   `seed=0` and trains one set per pod.
   - Make the seed a parameter next to `RUN_TAG` and `DATA_SUBDIR`, and name runs
     `sweep-v5-<ARM>-<SIZE>-s<SEED>`.
   - Keep the v2 recipe as registered: Qwen3-8B QLoRA, 3 epochs, lr 1e-4, effective batch
     16. Larger sets therefore train for more steps.
   - Commit this on its own branch before any run.
2. **Confirm GPU cost with the user, then train the 24 runs** (8 sets × seeds 0, 1, 2).
   - Check Runpod availability and price first. A 24 GB card (RTX A5000) is enough.
   - Upload each set's `train.jsonl` and `val.jsonl` to `/workspace/data/<set>/` on the
     network volume.
   - The notebook writes `qwen-coach-8b-<RUN_TAG>-q4_k_m.gguf` and terminates its own pod.
   - Estimate: about $1–2 a run on v2's 319 rows, more on the larger sets. Measure the first
     run and re-quote before the rest.
3. **Register each GGUF in Ollama** with a Modelfile copied from
   `models/Modelfile.qwen-coach-8b-v2` (ChatML template, `num_ctx 4096`).
4. **Coach the 91 held-out games and score the free metrics** for every run:
   `python -m eval.run --coach-model <ollama name> --no-judge --out
   eval/reports/sweep-v5-<ARM>-<SIZE>-s<SEED>.json`.
   - This writes grounding and claims (`METRIC_VERSION` 3, including the defence sensor).
   - It runs locally, and 24 runs × 91 games of 8B coaching take hours. Run them in the
     background with `--resume`.
5. **Judge as registered.**
   - **Opus**, 16 runs: `python -m eval.rejudge <report> --judge anthropic --batch --out
     <report stem>__opus.json`. That is about $16. A rerun with the same `--out` resumes the
     same batch.
   - **Gemini**, the 6 runs at 1,700: `--judge gemini`.

   **Settle the Gemini model first.** The registration says Gemini 3.1 Pro, but
   `eval/backends.py` defaults to `gemini-3.6-flash` (3.1 Pro is paid-only; the August
   `__gemini31pro` reports used it). Either set `GEMINI_MODEL` with a paid key, or record the
   substitution as a deviation **before** judging.
6. **Run the decision test.** `eval.equivalence` compares one report with another, axis by
   axis. The registered test averages each game's Opus factual score over the 3 seeds of each
   arm at 1,700, then pairs M − G over 91 games: a two-sided 90% t-interval with lower bound
   above −0.30, and Gemini's point estimate not below −0.30.
   - Write that as a small script with tests, reusing `eval.equivalence` where it fits.
   - Report everything the registration lists.
7. **Score the comparison arms in the same pass** (prompted 8B, template coach, v2, DeepSeek
   as coach) on the same 91 games with the same judges. The August 29-game reports are not
   comparable.

### Balances and accounts (11 Oct)

- **DeepSeek:** $2.75. Corpus generation is finished; no more teacher calls are planned.
- **Anthropic:** topped up 11 Oct. About $0.30 has gone on judging since (21 rows and the
  3-row batch check). Check the balance before step 5.
- **Gemini:** free tier, daily quota. `eval.rejudge` stops cleanly on it, and a rerun
  continues.

### Still open

- **The human rating round** (0 of 29): the largest credibility gap. It is needed before the
  paper, not before training.
- **The template-trained (no teacher) arm** in `paper-protocol.md` keeps its own sizes. It
  has not been scheduled.
- **`eval.recheck` cannot backfill reports scored with grounding v2.** Its alignment check
  uses the v1 move extractor. This matters only if old reports need claims v3; the new runs
  get v3 directly.

### Things that went wrong once and how they were handled

- **Out of Anthropic credit mid-run:** `training.judge_rows` and `eval.rejudge` keep what was
  judged; top up and rerun with `--resume` (or the same `--out`).
- **A DeepSeek connection dropped** (`ChunkedEncodingError`): the game is left out of the
  ledger; rerun the same distill command with `--resume`.
- **A balance watchdog that greps for "Error"** stops on per-game failures that the run
  survives. Match `Traceback` or the final `Wrote` line instead.

### Code and data

- **Code:** `training/sweep.py` builds the training sets. Batch judging is
  `eval/backends.py` (`anthropic_params`, `anthropic_batch`). Phrasing variety is
  `scripts/phrasing.py`. The defence claim measures are `scripts/claim_subjects.py` and
  `scripts/claim_support.py`.
- **Rows (git-ignored):**
  - in `data/distill/`: `raw_deepseek_pos_v5.jsonl` and its `_qc` and `_clear` files;
    `deepseek_pos_paired_plain_clear.jsonl`; and the game rows in `deepseek_qc.jsonl`
    (kind `game`);
  - in `training/datasets/sweep-v5-*/`: `train.jsonl` and `val.jsonl`. The manifests are
    tracked.
- **Game samples (git-ignored, `data/games/`):** `spotcheck146`, `pilot10`, `clearcut100`,
  `named100`, `explicit100` (holds `tools_pilot20`), `paired100`, `corpus_batch1_500`, and
  `corpus_batch2_rest`.
