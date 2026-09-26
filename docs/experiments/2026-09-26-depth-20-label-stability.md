# Label stability from depth 18 to depth 20

**Status:** pre-registered 2026-09-26, before any depth-20 analysis was run.

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

## Result

_To be filled in after the run._
