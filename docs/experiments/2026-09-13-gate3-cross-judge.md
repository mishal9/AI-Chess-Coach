# Gate 3: a second judge. The §6 tie does not survive it.

Date: 2026-09-13. Plan step P2. Cost: 58 Gemini calls on a paid key, zero Anthropic spend.

## What was done

`eval.rejudge` re-scored the **stored coaching text** of both arms with `gemini-3.1-pro-preview`,
using the same rubric prompt, facts blocks and 29 held-out games. Only the judge changed. Stockfish
rebuilt the facts blocks at depth 15, and the reports were joined positionally with a pgn check.

- `eval/reports/prompted_8b_2026-08-14__gemini31pro.json`
- `eval/reports/8b_v2_2026-08-10__gemini31pro.json`

Gemini 3.1 Pro is a peer-strength judge from a different model family, which answers the
outline's §7 threat that "Opus taught, Opus judged". It is a *preview* model, and the paper must
say so.

Reproduce:

```bash
python -m eval.equivalence --agreement eval/reports/8b_v2_2026-08-10.json eval/reports/8b_v2_2026-08-10__gemini31pro.json
python -m eval.equivalence --agreement eval/reports/prompted_8b_2026-08-14.json eval/reports/prompted_8b_2026-08-14__gemini31pro.json
python -m eval.equivalence eval/reports/prompted_8b_2026-08-14__gemini31pro.json eval/reports/8b_v2_2026-08-10__gemini31pro.json
```

## 1. Agreement on identical text is moderate, and Gemini is harsher

| axis | prompted base: r / τ | fine-tune: r / τ | mean, Opus → Gemini (base) | mean, Opus → Gemini (fine-tune) |
|---|---|---|---|---|
| factual correctness | 0.51 / 0.45 | 0.65 / 0.61 | 3.72 → **2.86** | 3.72 → **3.28** |
| clarity | 0.31 / 0.20 | 0.48 / 0.43 | 4.41 → 4.52 | 4.45 → 4.34 |
| actionability | 0.15 / 0.13 | 0.42 / 0.37 | 3.72 → 3.03 | 3.59 → 3.24 |
| identifies key mistake | n/a (Gemini gave 5 to every game) | 0.51 / 0.20 | 4.83 → 5.00 | 4.79 → 4.79 |

Factual agreement of r = 0.51–0.65 falls in or above the human-vs-judge range Kim et al. (NAACL
2025) report for chess commentary (Pearson 0.40–0.56). Exact factual agreement is only 21% on the
base and 34% on the fine-tune.

## 2. Under Gemini, the fine-tune is *not* tied with its base

| axis (fine-tune − base) | Opus judge | Gemini judge |
|---|---|---|
| factual correctness | +0.000, 90% CI [−0.37, +0.37] | **+0.414, 90% CI [−0.12, +0.95]** |
| rubric overall | −0.034, equivalent at δ = 0.30 | +0.060, **not** equivalent (TOST p = 0.079) |

Neither judge's factual difference is statistically distinguishable from zero. But the Opus
reading, "reproduces, does not exceed", is **one judge's reading**: Gemini puts the point estimate
at +0.41 in the fine-tune's favour. Under Opus, overall quality was a genuine equivalence; under
Gemini it is inconclusive.

## 3. Why they disagree: severity, not detection

The four games with the largest disagreement (all prompted base; Opus factual 3–4, Gemini 1–2)
show both judges **naming the same errors**: invented tactics ("Bc5+ would attack your queen"),
a king move described as "overextending with pawn moves", alternative moves not in the facts.
Opus files these as "unsupported interpretation … not contradicting facts" and scores 4. Gemini
calls the same thing "fabricates" and scores 1.

The gap is not explained by invented-move counts (Spearman ρ with the per-game judge gap = −0.13
on the base, 0.04 on the fine-tune; the fine-tune's stored counts come from the pre-#41 parser).
The disagreement lies in **how much invented narrative should cost** on a 1–5 scale. That is a
property of the rubric, not of either judge.

## Consequences for the paper

1. **§6's headline cannot stand as written.** "Distillation reproduces the base model's judged
   quality" has to become "whether distillation improved factual quality depends on the judge,
   and neither judge's difference is significant at n = 29".
2. **This strengthens the meta-evaluation frame.** The paper's own automatic references, the
   grounding metric (§4) and now the LLM-judge factual axis, are both unstable. A holistic 1–5
   factual score mixes *detecting* an error with *weighing* it, and two frontier judges weigh
   differently.
3. **P3 (human ratings) is now the decisive evidence**, not a nice-to-have. Human ratings are
   what decide which judge's sense of severity to trust.
4. The fix a reviewer will name is **claim-level error rates instead of a holistic score**, which
   is ACT-Eval's design (Hebbar et al., arXiv:2608.04240). See
   `2026-09-13-literature-refresh.md`.
