# Publication protocol — run ONCE, on the final configuration

During iteration we deliberately run **single-seed, single-judge** experiments: iteration
is search, and large deltas are visible through seed noise. The rigor below is paid one
time, when a configuration hits the quality gates (grounding ≥ 0.85, judge factual ≥ 4.0)
and becomes "the result" — it converts an engineering win into a defensible claim.

Estimated one-time cost: ~$1 GPU + ~200 judge calls.

## Checklist

- [ ] **Seed variance (the "lucky roll" defense).** Train the final config with 3 seeds
      (0, 1, 2 — change only `seed` in the SFT config), eval each on the 29-game set,
      report every headline metric as **mean ± std** across seeds. With ~15 optimizer
      steps on a tiny dataset, run-to-run wobble is real; this is the first thing a
      reviewer probes.
- [ ] **Significance on the paired design.** The eval is already paired (same 29 games,
      baseline vs fine-tune). Run a **Wilcoxon signed-rank test** on per-game scores
      (factual and overall) and report p-values alongside the better/same/worse counts.
      `scipy.stats.wilcoxon` on the per-game arrays from the two report JSONs.
- [ ] **Second judge (circularity defense).** The rubric judge and the distillation
      teacher are the same model (`claude-opus-4-8`), so rubric gains could partly be
      self-preference. Re-judge the final runs with `--judge gemini` (already pluggable
      via `eval.backends`) and report both judges. The deterministic grounding metric is
      the third, bias-free leg.
- [ ] **Scale vs fine-tuning ablation.** The baseline is *prompted 3B*; the treatment is
      *fine-tuned 8B* — confounded. The 3B fine-tune GGUF (v1 dataset, 1 epoch) already
      exists locally: register it in Ollama and run one eval pass to fill the 2×2
      (prompted/fine-tuned × 3B/8B) as far as budget allows.
- [ ] **Dataset ablation (free, no new teacher calls).** If the winning config trains on
      the v2 mixed-granularity dataset, retrain on row-type subsets (game-only /
      position-only) using the `kind` field to attribute the gain — volume vs shape.
- [ ] **Judge stability note.** The Claude judge is nondeterministic (Opus rejects
      `temperature`); either re-judge one run 3× and report rubric std, or state the
      variance is absorbed by the multi-seed std.
- [ ] **Splits/leakage statement.** One paragraph citing the mechanisms already built:
      per-game SHA-256 split (`training.dataset.assign_split`), corpus↔held-out
      disjointness by GameId **and** normalized-movetext hash (`training.corpus`),
      distill guardrail refusing `eval/heldout/` sources.

## Reporting conventions

Every number in the paper traces to a committed `eval/reports/*.json` plus the experiment
record in this directory that produced it. No number in prose without its JSON.

## Analysis depth (decided 2026-09-26)

Every Stockfish analysis that feeds a result uses **depth 18**: training data, held-out
bucketing, and every evaluation run. The constant is `engine.analyzer.DEFAULT_DEPTH`, and
`tests/test_analysis_depth.py` fails if any research script defaults to anything else.

**Why one depth.** The facts block a coach sees depends on depth: a borderline move can
change label (the inaccuracy threshold is 0.10 win-probability loss) and the engine's
preferred move can change. Before this decision the pipeline mixed four depths:

| Where | Before | Now |
|---|---|---|
| Training data (`training.distill`) | 18 | 18 |
| Held-out bucketing (`eval.expand_heldout`) | 16 | 18 |
| Evaluation (`eval.run`, `training.n2_eval`) | 15 | 18 |
| App (`memory.store.SYNC_DEPTH`) | 12 | 15 |

A model was trained on depth-18 facts and scored on depth-15 facts, and some held-out games
were bucketed on facts the coaches never saw.

**Why 18.** It matches the depth v2's training data was generated at, so v2 needs no
exception, and it matches ACT-Eval (Hebbar et al., 2026), the closest related work. The
cost is time: about 1 s per move on the development machine, 4–5× depth 15.

**The app stays at 15.** Syncing analyzes dozens of games while someone waits. The app is
not part of any reported number. Deployment depth is stated once in the paper.

**Existing reports.** Every report in `eval/reports/` up to this date was run at depth 15 on
the 29-game set and records `"depth": 15`. They remain the historical record and are not
compared with depth-18 results. `eval.recheck`, `eval.rejudge` and `eval.human_rating` now
rebuild facts at the depth a report records, never at the current default, so re-judging
an old report still gives the judge the facts its coach was given. The judge-drift check
re-judges old depth-15 texts against depth-15 facts, which isolates the judge as the only
change.

**v2's depth is inferred.** v2's rows predate depth recording. The `training.distill`
default was 18 from 5 Jul and the v2 data was generated on 9 Aug, so it was almost
certainly 18. State it as inferred. Rows generated from now on store `source.depth`.

**Held-out labels at depth 18 (applied 2026-09-26).** `python -m eval.expand_heldout
--relabel` re-derived every game's bucket at depth 18. 14 of 91 labels changed:

- 10 of the 85 games that `expand_heldout` had sorted at depth 16 changed with depth alone
  (about 12%).
- Of the 6 hand-picked originals, 4 no longer match. `inaccuracies` #0 changed with depth
  (inaccuracies at 15 and 16, two_mistakes at 18). `slow_loss` #0, `one_blunder` #0 and
  `multi_blunder` #0 never fit the rules at depth 15, 16 or 18: the hand-picked
  "slow loss" contains a real mistake at every depth.
- `slow_loss` is the least stable bucket: 6 of its 17 games moved, mostly to
  `inaccuracies`, because a game with no single bad move sits on the thresholds.

Counts at depth 18: clean_draw 5, slow_loss 12, inaccuracies 19, two_mistakes 18,
one_blunder 19, multi_blunder 16, unsorted 2. No top-up.

How the change was applied: only the manifest's `bucket` label changed. Games stay in their
original PGN file at the same `game_index`, so every existing report still joins to its
games and the original 29 stay a prefix. Coached sides are unchanged; in `one_blunder` #9
the worse-playing side is black at depth 18 but the manifest still coaches white. The two
games that fit no bucket are labelled `unsorted`: they count in overall scores and are
left out of per-bucket results. Each changed entry keeps its old label in
`bucket_previous`. Per-bucket results come from the manifest label, never the file name
(`eval.run` records it per game; `eval.human_rating` stratifies on it).

Per-bucket results for `slow_loss` and `inaccuracies` carry label uncertainty of this
size, and the paper says so.

## Data-scale sweep and held-out expansion (pre-registered 2026-09-25)

N3 asks whether more DeepSeek-taught training rows help. Pre-registering the design here,
before any row beyond the pilot is generated, is what stops "one more size worth trying"
from becoming the failure mode this project already named once (see `PLAN.md`, "The rule").
**Nothing below changes once the sweep starts.**

### Why the held-out set grows first

Every existing headline number comes from 29 games. The per-game SD on the factual axis
(v2 vs. prompted-base, `eval/reports/8b_v2_2026-08-10.json` and `prompted_8b_2026-08-14.json`)
is **1.16**, which gives a 90%-CI half-width of **±0.37** at n=29 — already the bound Gate 3
reports. A data-scale sweep exists to detect a *difference between sizes*, and ±0.37 cannot
resolve that against noise this size.

| n (games) | 90% CI half-width (factual axis, SD 1.16) |
|---|---|
| 29 (today) | ±0.37 |
| 60 | ±0.26 |
| **100 (target)** | **±0.20** |
| 150 | ±0.16 |

**Target: ~100 held-out games, 17 per mistake-profile bucket** (`eval.expand_heldout
--per-bucket 17`). At ±0.20, a difference of ~0.4 becomes detectable and a TOST equivalence
claim at δ=0.30 becomes meaningful — both out of reach at n=29. Beyond 150 games the bound
flattens while judge spend keeps rising, so 100 is the stopping point, not a floor.

Caveat: SD 1.16 is one comparison (v2 vs. prompted-base); template-vs-prompted gives 0.7. The
bound is a planning estimate, not a guarantee — re-state it from the actual n once expansion
finishes.

**Order, because each step depends on the last:**
1. `eval.expand_heldout --per-bucket 17` (writes new held-out PGNs), then `training.corpus`
   (re-derives the corpus so it stays disjoint from the wider held-out set — it reads
   `eval/heldout/` fingerprints, so this must run *after* step 1, not before).
2. Re-run every existing arm (template, prompted 8B, v2, DeepSeek-as-coach) on the widened
   set — the old 29-game reports are not comparable to anything scored on 100 games.
3. Only then generate sweep training data and fine-tune.

### Reproducible game selection (added 2026-09-25)

"Nested" only holds if the same games sit in the same order every time, independent of
when the corpus was fetched — `training.corpus.assemble` otherwise orders games by fetch
order, which drifts as the roster keeps playing new games on Lichess. Fixed by
`training.corpus.canonical_order`: games are sorted by a SHA-256 hash of each game's own
identity (`engine.pgn.game_key`, same id-or-movetext-hash scheme `heldout_fingerprints`
already uses), so the order depends only on the games themselves, not on fetch time or
manifest position. Row-count prefixes of a `training.distill` run over a canonically
ordered manifest are then the same games at every tier, reproducible months later against
a corpus that has moved on.

`training.corpus --canonical-seed 0` opts into this (default: unchanged fetch order, so
existing usage is untouched). Use it for every corpus fetch that feeds the sweep.

**What this does not make reproducible:** DeepSeek's completions themselves.
`training.teacher.DEEPSEEK_TEMPERATURE = 0.7` on purpose — a re-roll after a failed
grounding check only helps if it can produce a different answer — so re-running
distillation on the same canonically ordered games will not reproduce byte-identical
training text. This matches how the original Opus/v2 dataset was already generated (the
teacher is nondeterministic there too); state it as a limitation rather than a gap
specific to the DeepSeek arm. What must and does reproduce is *which* games and rows make
up each tier, and the train/val/test split of whatever text they end up holding
(`training.dataset.assign_split`, seed 0).

### Training-size sweep

Four **nested** train-row sizes, each a superset of the smaller ones so only size varies:

| Rows (train split) | Role |
|---|---|
| ~400 | replicates v2's size, like-for-like |
| 1,000 | |
| 2,500 | |
| 5,000 | upper end of this sweep |

- **Fixed shape mix**: hold v2's ~1 game-row : 2 position-row ratio at every size — the
  shape-vs-volume ablation (`2026-08-10-ablation-shape-vs-volume.md`) already showed shape
  drives the grounding gain, so a sweep that let the mix drift would confound size with shape.
- **Same recipe throughout**: same base model (Qwen3-8B), same QLoRA config, same held-out
  set (the widened one from above).
- **Report every point**, including a flat curve. A flat curve at 5,000 rows is itself the
  answer to "is 400 rows undertrained" — say that plainly rather than only reporting the win
  case.
- Template-trained (N3, no teacher) rows sweep further (1k/5k/20k) at effectively no cost and
  run alongside this as the free comparison — did DeepSeek's text add anything the row shape
  alone didn't already provide?

### Seeding (revised 2026-09-25)

A 4-point curve with a noise estimate only at its two ends leaves the middle two points
undefended — a reviewer has no way to tell a real step from seed wobble at 1,000 or 2,500
rows. GPU is cheap here (~$1–2/run); judging is what's expensive. So seed and judge are
decoupled:

- **Train 3 seeds (0, 1, 2) at all 4 sizes** — 12 QLoRA runs, ~$18–24 GPU total.
- **Score grounding + claims on all 12** — deterministic, no judge call, effectively free.
  This alone bounds how much a run wobbles before any judge spend.
- **Rubric-judge (Opus + Gemini) one seed per size** for the headline curve — 4 points, the
  same judge cost as before.
- **Rubric-judge all 3 seeds at the two endpoints** (~400 and 5,000) as the calibration: how
  much does the *judged* rubric itself wobble across seeds, independent of the deterministic
  metrics. That figure is what licenses trusting the single-seed middle points.

### Cost (at DeepSeek V4 Pro peak pricing; roughly half off-peak)

| Item | Approx. cost |
|---|---|
| Held-out expansion Stockfish pass (~70 new games) | compute only, no API spend |
| Re-scoring 4 existing arms on ~100 games (Opus judge) | ~$5.60 (4 × ~100 × $0.014) |
| 5,000-row dataset (≈5,750 raw rows ≈ 1,700 source games) | ~$13 |
| QLoRA training, 4 sizes × 3 seeds | ~$18–24 GPU (~$1–2/run) |
| Grounding + claims on all 12 seed runs | free (deterministic) |
| Headline judging: 1 seed × 4 sizes, Opus + Gemini, ~100 games | ~$11–15 |
| Endpoint seed-variance judging: 2 extra seeds × 2 sizes, Opus + Gemini | ~$5.60 |

Total for the full sweep: roughly **$53–72**, most of it the widened held-out judging, which
is paid once and reused by every arm after it.
