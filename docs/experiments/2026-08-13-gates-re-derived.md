# Re-deriving the release gates against the corrected metrics

**Date:** 2026-08-13 · **Status:** proposal, needs a decision before iteration 3 · **Cost:** $0 (Stockfish only, no model or judge)

The gates were **grounding ≥ 0.85** and **judge factual ≥ 4.0**. Correcting the grounding
parser (#41) invalidated the first: the prompted 3B baseline now scores **0.861**, so the
bar it was meant to represent is one the *un-fine-tuned* model already clears. Any v3 run
measured against it would prove nothing.

This backfills the new claim metrics onto all three committed reports so the deterministic
axes have a baseline at all, then proposes replacements.

## 1 · The full corrected scoreboard

Backfilled with `python -m eval.recheck` (Stockfish re-analysis, no API). The join to the
manifest is positional and **verified**, not assumed — see §4.

| model | grounding | games at 1.00 | claims | claim-clean games | violations | judge factual |
|---|---|---|---|---|---|---|
| prompted 3B baseline | 0.861 | 20/29 | 0.909 | 24/29 | 6 | 2.90 |
| 8b_v1 | 0.890 | 20/29 | 0.966 | 27/29 | 2 | 3.45 |
| 8b_v2 | **0.965** | **25/29** | **0.974** | 27/29 | 2 | **3.72** |

Violations by kind:

| model | role_inversion | invented_placement |
|---|---|---|
| baseline | 3 | 3 |
| 8b_v1 | 0 | 2 |
| 8b_v2 | 1 | 1 |

## 2 · Both deterministic metrics are running out of room

I expected the claim metric to take over as the deterministic gate, since grounding had
saturated. **The data does not support that.**

| metric | baseline → v2 range | v1 → v2 separation |
|---|---|---|
| grounding | 0.861 → 0.965 (0.104) | 0.890 → 0.965 (**+0.075**) |
| claims | 0.909 → 0.974 (0.065) | 0.966 → 0.974 (**+0.008**) |
| judge factual | 2.90 → 3.72 (0.82) | 3.45 → 3.72 (**+0.27**) |

Claims discriminates *less* than grounding, not more: v1 and v2 tie on clean games (27/29)
and differ by 0.008 on the mean — well inside noise at n=29. It starts nearer its ceiling
than grounding does and has less room to fall.

So the honest position is that **neither deterministic metric can serve as the progress
gate**. Between them they now separate models by a couple of games out of 29. The judged
factual score remains the only instrument with real discrimination, and it is the only one
that ordered v1 and v2 by a margin worth trusting.

That is not an argument for dropping the deterministic checks. It is an argument for
demoting them from *gates* to *regression detectors*: they are free, they run offline, and
they are the only thing that would catch a v3 that silently started inventing again. But
they should not be what "iteration 3 succeeded" is measured on.

## 3 · Proposed gates

**Progress gate (the one that decides whether an iteration shipped):**

- **judge factual ≥ 4.0** — unchanged. It is untouched by the parser correction (the judge
  reads the facts block directly), it has the widest dynamic range of the three, and v2's
  3.72 leaves a real gap to close.

**Regression gates (free, must not get worse):**

- **claim violations = 0** across the 29 games. v1 and v2 both sit at 2, so this is not yet
  met and has honest headroom. Counting violations rather than averaging scores resists
  the failure mode that got us here: a mean over mostly-perfect games moves too little to
  notice, while a count of games that said something false is directly interpretable.
- **grounded games ≥ 27/29.** v2 is at 25. Again a count, for the same reason, and again
  not yet met.

**Retired:**

- **grounding mean ≥ 0.85** — met by the prompted baseline under the corrected parser, and
  saturating besides. Keep reporting the mean; stop gating on it.

The shape of the proposal is deliberate: one judged gate that measures progress, two free
counting gates that catch regression, and nothing gating on a mean that sits near its
ceiling.

### What this implies for iteration 3

v2 must gain **+0.28 factual**, close **2 claim violations**, and convert **2 more games**
to fully grounded. The claim-violation target is the concrete one — §5 of the
[audit](./2026-08-11-grounding-metric-audit.md) and the
[board-state work](https://github.com/mishal9/chess-analyzer/pull/45) identify exactly what
those violations are.

## 4 · Why the backfilled numbers can be trusted

Reports written before #43 record neither `claims` nor `game_index`, and a bucket file
holds ~5 games, so the name alone does not identify one. `eval.recheck` joins positionally
— `eval.run` iterates the manifest in order, the same assumption `eval.compare` already
pairs on — and then **verifies** it two independent ways per game:

1. the record's `pgn` and `coached_side` must match its manifest entry;
2. the record's stored grounding score **and** hallucinated set must be reproducible from
   the facts block that entry generates, under the pre-#41 parser that wrote them.

All three reports pass on 29/29. A report failing either check is refused rather than
backfilled on a guess.

An earlier join, on the grounding signature alone, matched only 24/29 — the five
`clean_draw` and `slow_loss` games cite no moves at all, so their signature is identical
across every candidate in the file and carries no information. That is what motivated the
positional join plus verification rather than either method alone.

## 5 · Threats

- **Re-analysis is not the original analysis.** The reports do not store the analyzed
  game, so `recheck` re-runs Stockfish at depth 15 and assumes determinism. The grounding
  reproduction check in §4 is what makes this safe: if the re-analysis had produced a
  different facts block, the stored scores would not fall out of it.
- **n=29, and violations are counted in single digits.** "2 violations vs 0" is a
  difference of two games. The regression gates are usable as tripwires, not as evidence
  of improvement.
- **`claims` only covers three failure classes** — role inversion, invented castling,
  invented placement. Whatever the judge sees beyond those is still uncovered, which is
  part of why factual stays the progress gate.

## 6 · Reproduction

```bash
python -m eval.recheck eval/reports/baseline_29g_2026-07-10.json \
                       eval/reports/8b_v1_2026-08-08.json \
                       eval/reports/8b_v2_2026-08-10.json
```

Roughly 10 minutes of Stockfish, no API calls. Add `--out` to write a rechecked report.
