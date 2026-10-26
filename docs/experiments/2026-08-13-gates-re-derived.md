# Re-deriving the release gates against the prompted-8B control

**Date:** 2026-08-13 · **Status:** framework agreed, numbers pending the prompted-8B rerun · **Cost:** $0 (Stockfish only, no model or judge)

Two things invalidated the existing gates at once.

**The grounding gate broke.** It was **≥ 0.85**, and correcting the parser (#41) lifted every
model above it. It no longer separates anything.

**The reference model was wrong.** Every gate and every experiment record until now was
anchored to the prompted **3B** (`qwen2.5:3b-instruct`), so "factual ≥ 4.0" meant
"meaningfully above 2.90". But the shipped coach is an 8B fine-tune, and comparing it to a
prompted 3B confounds two changes: the size jump *and* the fine-tune. It cannot answer the
question the project asks: **does fine-tuning beat simply prompting the same base
model?** The 3B comparison is retired here and is not carried into iteration 3.

The correct control is **prompted `qwen3:8b`**: same base weights, same prompt pipeline,
same held-out set, no fine-tune. That run is being redone, so the numbers below are marked
pending; the framework does not depend on them.

## 1 · Where the fine-tune stands

Backfilled with `python -m eval.recheck` (Stockfish re-analysis, no API). The join to the
manifest is positional and **verified**, not assumed — see §4.

| model | grounding | games at 1.00 | claims | claim-clean games | violations | judge factual |
|---|---|---|---|---|---|---|
| 8b_v1 | 0.890 | 20/29 | 0.966 | 27/29 | 2 | 3.45 |
| **8b_v2** | **0.965** | **25/29** | 0.974 | 27/29 | 2 | 3.72 |
| **prompted 8B control** | 0.923 | 23/29 | **0.989** | **28/29** | **1** | **3.72** |

**The control landed 2026-08-14 and the progress gate fails outright** — see
[the control write-up](./2026-08-14-prompted-8b-control.md). Judged factual is *identical*
(3.72 both), so the fine-tune's improvement over its own un-fine-tuned base is **+0.00**
against a required **+0.30**. It wins grounding (+0.042, two more clean games) and loses
claims (one extra violation). The gates below stand as written; v2 simply does not meet
them, and the next move is diagnosis rather than another dataset.

Violations by kind: v1 — 2 × `invented_placement`; v2 — 1 × `invented_placement`,
1 × `role_inversion`.

Note what the correction did to the v1→v2 story: v1 gained most from the parser fix
(+0.103, against v2's +0.058), because it named squares most often. The fine-tune's margin
over its predecessor is real but thinner than the original numbers implied — **+0.075
grounding, +0.27 factual, and no separation at all on claims** (0.008, tied at 27/29 clean).

## 2 · Neither deterministic metric can be the progress gate

I expected the claim metric to replace grounding as the deterministic gate, since grounding
had saturated. **The data says otherwise: claims discriminates less, not more.**

| metric | v1 → v2 separation |
|---|---|
| grounding | **+0.075** |
| claims | **+0.008** (tied on clean games) |
| judge factual | **+0.27** |

Claims starts nearer its ceiling than grounding and has less room to fall. Between them the
two free metrics separate models by about two games out of 29 — enough to catch a
regression, nowhere near enough to certify progress.

So the deterministic checks are demoted from gates to **regression detectors**. They stay:
they are free, offline, and the only thing that would catch a v3 silently inventing again.
They just are not what "the iteration shipped" is measured on.

## 3 · Proposed gates

**Progress gate — stated as a margin over the control, not an absolute.**

The old `factual ≥ 4.0` was an absolute derived from a 3B baseline that no longer figures.
Against a prompted 8B, an absolute bar is untethered: if the control scores 3.8, then 4.0 is
a 0.2 ask; if it scores 3.0, the same 4.0 is a 1.0 ask. The gate should be the *effect of
fine-tuning*, which is what the project is actually claiming:

> **judge factual ≥ prompted-8B control + 0.30**, and ≥ 4.0 in absolute terms.

The margin is the real gate; the absolute floor keeps a weak control from making a weak
fine-tune look good. 0.30 is roughly the v1→v2 step (+0.27) — one iteration's worth of
genuine movement, and comfortably outside the ±0.13 range the judged axes wander over.

**Regression gates (free, must not get worse):**

- **claim violations = 0** across the 29 games. v1 and v2 both sit at 2, so this is not yet
  met and has honest headroom.
- **grounded games ≥ 27/29.** v2 is at 25.

Counts, not means, in both cases: a mean over mostly-perfect games moves too little to
notice, which is close to the failure that started this whole thread.

**Retired:**

- `grounding mean ≥ 0.85` — cleared by every model after #41. Keep reporting it; stop
  gating on it.
- **The prompted-3B baseline as a reference point.** Superseded by the prompted-8B control
  for every forward-looking comparison.

### What this implies for iteration 3

Close **2 claim violations**, convert **2 more games** to fully grounded, and beat the
prompted-8B control by **+0.30 factual**. The last of those is the one in doubt: on the
superseded control run the fine-tune was *not* ahead on any judged axis, only on grounding.
**If the rerun confirms that, iteration 3's problem is not data volume but whether
fine-tuning is buying judged quality at all** — and that question should be settled before
another dataset is built.

## 4 · Why the backfilled numbers can be trusted

Reports written before #43 record neither `claims` nor `game_index`, and a bucket file holds
~5 games, so the name alone does not identify one. `eval.recheck` joins positionally
(`eval.run` iterates the manifest in order, the same assumption `eval.compare` already pairs
on) and then **verifies** it two independent ways per game:

1. the record's `pgn` and `coached_side` must match its manifest entry;
2. the record's stored grounding score **and** hallucinated set must be reproducible from
   the facts block that entry generates, under the pre-#41 parser that wrote them.

Both reports pass on 29/29. A report failing either check is refused rather than backfilled
on a guess.

An earlier join, on the grounding signature alone, matched only 24/29: the `clean_draw`
and `slow_loss` games cite no moves at all, so their signature is identical across every
candidate in the file and carries no information. That is what motivated the positional
join plus verification rather than either method alone.

## 5 · Threats

- **Re-analysis is not the original analysis.** The reports do not store the analyzed game,
  so `recheck` re-runs Stockfish at depth 15 and assumes determinism. The grounding
  reproduction check in §4 is what makes this safe: had the re-analysis produced a different
  facts block, the stored scores would not fall out of it.
- **n=29, and violations are counted in single digits.** "2 violations vs 0" is a difference
  of two games. The regression gates are tripwires, not evidence of improvement.
- **`claims` covers three failure classes only**: role inversion, invented castling,
  invented placement. Whatever the judge sees beyond those is uncovered, which is part of
  why factual stays the progress gate.
- **The control is pending.** Every margin-based number here is a shape, not a value, until
  the prompted-8B rerun lands.

## 6 · Reproduction

```bash
python -m eval.recheck eval/reports/8b_v1_2026-08-08.json \
                       eval/reports/8b_v2_2026-08-10.json
```

Roughly 10 minutes of Stockfish, no API calls. Add `--out` to write a rechecked report.
Re-run with the prompted-8B report once it exists to fill in §1.
