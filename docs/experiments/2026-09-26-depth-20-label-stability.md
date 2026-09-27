# Label stability from depth 18 to depth 20

**Status:** pre-registered 2026-09-26, before any depth-20 analysis was run. Result added the same day.

## Question

The held-out labels were re-derived at depth 18 (see `paper-protocol.md`, "Analysis
depth"). From depth 16 to 18, 10 of the 85 rule-sorted games changed bucket (about 12%).
How many change again from 18 to 20?

## Why it's worth running

It gives the paper one number for how depth-sensitive the bucket labels are past the
chosen depth. That bounds the label uncertainty in per-bucket results.

## Design, fixed before running

- All 91 held-out games, analyzed at depth 20 with the same Stockfish build (18) and
  analyzer code as the depth-18 labels.
- Each game classified with `eval.expand_heldout.classify`, the same rules used for the
  depth-18 labels.
- Compared with the depth-18 label in `eval/heldout/manifest.json` (bucket, and separately
  the worse-playing side).
- Reported as counts: all 91, the 85 rule-sorted games, and per bucket.
- One run. No depth 22 or beyond.

## What the result can and cannot change

**The research depth stays 18 whatever the result.** The manifest is not relabelled at
depth 20. The outcome only decides how the paper describes label uncertainty:

- Clearly fewer changes than 16 → 18 (for example 5% or less): labels are mostly settled
  by depth 18, and the paper says so.
- About as many or more: labels near the bucket thresholds stay depth-sensitive, and
  per-bucket results for the affected buckets are reported with that caveat, alongside
  results that exclude games whose label changed.

## Cost

CPU only, no API spend. Depth 20 is expected to take roughly 3–4× depth 18 per move.

## Result (run 2026-09-26)

All 91 games analyzed at depth 20 with Stockfish 18 (about 3 CPU-hours, 45 minutes on 8
cores). No worse-playing side changed between depth 18 and 20.

| | 16 → 18 | 18 → 20 |
|---|---|---|
| Rule-sorted games (85) whose label changed | 10 (12%) | **7 (8%)** |
| Hand-picked games (6) whose label changed | 1 | 3 |
| All 91 | 11 of 91 by depth, plus 3 that never fit | 10 (11%) |

Every change from 18 to 20:

| Game | Hand-picked | Label as curated | Depth 18 | Depth 20 |
|---|---|---|---|---|
| `slow_loss` #0 | yes | slow_loss | two_mistakes | slow_loss |
| `one_blunder` #0 | yes | one_blunder | two_mistakes | one_blunder |
| `inaccuracies` #0 | yes | inaccuracies | two_mistakes | inaccuracies |
| `multi_blunder` #4 | | multi_blunder | multi_blunder | one_blunder |
| `slow_loss` #11 | | slow_loss | slow_loss | inaccuracies |
| `slow_loss` #14 | | slow_loss | inaccuracies | slow_loss |
| `inaccuracies` #13 | | inaccuracies | inaccuracies | slow_loss |
| `two_mistakes` #10 | | two_mistakes | slow_loss | two_mistakes |
| `two_mistakes` #13 | | two_mistakes | one_blunder | two_mistakes |
| `one_blunder` #14 | | one_blunder | one_blunder | multi_blunder |

"Label as curated" is the depth-16 rule label for rule-sorted games and the hand-chosen
label for the 6 hand-picked ones.

**Labels do not converge; they oscillate.** Of the 10 rule-sorted games that changed from
16 to 18, 3 went back to their depth-16 label at depth 20 (`slow_loss` #14,
`two_mistakes` #10, `two_mistakes` #13). All 3 hand-picked games that depth 18 put in
`two_mistakes` went back to their curated label at depth 20. In each case one borderline
move crosses a quality threshold one way at one depth and back at the next. The
`slow_loss` / `inaccuracies` boundary accounts for most of the traffic in both steps.

**Outcome under the pre-registered rule: the second case.** 8% is fewer than 12% but not
"clearly fewer" (the pre-registered example was 5% or less). Labels near the bucket
thresholds stay depth-sensitive past 18. As pre-registered, the research depth stays 18
and the manifest is not relabelled at depth 20.

**What the paper does with this:**

- Per-bucket results are reported with a label-uncertainty caveat, strongest for
  `slow_loss` (7 of the 17 games in `slow_loss.pgn` change label somewhere across depths
  16, 18 and 20) and `inaccuracies`.
- Headline results are also reported on the **label-stable subset**: the 73 games whose
  label is the same at depths 16, 18 and 20 (the curated label, for hand-picked games).
  If a conclusion holds on all 91 and on these 73, label instability does not drive it.

The 18 games outside the stable subset:

`clean_draw` #2; `inaccuracies` #0, #6, #13; `multi_blunder` #0, #4; `one_blunder` #0, #14;
`slow_loss` #0, #4, #5, #8, #11, #13, #14; `two_mistakes` #3, #10, #13.

Stable subset by depth-18 bucket: clean_draw 5, slow_loss 10, inaccuracies 14,
two_mistakes 14, one_blunder 15, multi_blunder 15.

Each manifest entry carries `label_stable` (true for these 73). `eval.run` and
`training.n2_eval` copy it into every record and repeat the headline vector for the stable
subset under `aggregate.label_stable_subset`.

The depth-20 analyses are saved in the analysis cache (`data/analysis/20/`), so this
comparison can be re-run in seconds.
