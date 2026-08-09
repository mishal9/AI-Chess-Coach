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
