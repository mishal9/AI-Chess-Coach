# Paper outline, draft v1 (2026-08-30)

Companion to `2026-08-30-literature-gap-analysis.md` and `paper-protocol.md`.
Status: outline + evidence map. Gates 1 and 2 cleared (below); gate 3 open.

## Working title

Preferred:
> **Grounded in What? Auditing Deterministic Grounding Metrics for Free-Form Chess Coaching**

Alternates:
- *A Grounding Metric That Passed Its Own Gate: A Validity Audit in LLM Chess Coaching*
- *Distillation Reproduces, It Does Not Exceed: A Controlled Study of Coaching LLMs*

The first is preferred because the audit is the more defensible contribution and the
one no one else has done. The negative result is the second act, not the headline.

## Venue

Workshop-first, preprint alongside. Natural fits: evaluation//meta-evaluation workshops
(NeurIPS/ICML/COLM), or an NLP-for-education venue. **Not** a chess-AI venue: the
audience that cares is the "how do we know our automatic metric measures anything"
audience, which is much larger than the chess audience.

---

## Abstract (draft)

> Automatic metrics for grounded natural-language generation are typically introduced
> and then trusted. We report a validity audit of one such metric in a setting where the
> ground truth is unusually accessible: natural-language chess coaching, where every
> factual claim can in principle be checked against a replayable board. We built a
> deterministic grounding metric (the fraction of moves cited in generated coaching
> that appear in the engine-derived facts the model was given), used it as both an
> evaluation gate and a training-data filter, and found it wrong in both directions. It
> was *saturated* (18/29 held-out games at the ceiling), *blind* to the errors that
> mattered (two games a judge scored 1–2/5 for factual accuracy scored a perfect 1.00),
> and *over-firing* (84–94% of flagged hallucinations were bare square names in prose
> such as "your rook on b7"; 64 of 64 distillation rows discarded by the metric's gate
> failed on this pattern alone). Correcting it recovered 52 of 64 discarded rows at zero
> cost and reversed two of our own published conclusions. We then replace the broken
> component with claim-level checkers that replay the game (role binding, move type,
> and piece placement) and validate them at 0/467 false positives on teacher-written
> coaching, with 5 of 72 flagged held-out games all independently judged 2/5. Finally,
> using a same-base prompted control, we report that QLoRA distillation from a frontier
> teacher **reproduces** the base model's judged factual quality (3.72 vs 3.72; 90% CI
> on the paired difference [-0.37, +0.37]) while improving citation hygiene; it does
> not exceed it. We argue this is expected: unlike puzzle-solving, coaching admits no
> verifiable reward to bootstrap from.

---

## 1. Introduction

Frame: the field is shipping *grounded explanation* claims validated by *accuracy proxies*.

- C1 (Tang et al., 2026) is titled "Grounded Chess Reasoning" and evaluates first-move
  accuracy only; §3.1 states accuracy "serves as a proxy for the quality of its internal
  reasoning." No faithfulness measurement appears in the paper.
- Kim et al. (NAACL 2025) evaluate generated commentary with an LLM judge (GCC-Eval)
  and report human correlations of Pearson **0.40–0.56** / Kendall **0.23–0.39**.
- ChessQA (Wen et al., 2025) evaluates commentary *recognition* (4-way multiple choice,
  exact match), not generation.

So: the one paper that measures generated-commentary quality against humans finds only
moderate agreement, and the papers claiming grounding do not measure it. That is the
opening.

Contributions (state plainly):
1. A validity audit of a deterministic grounding metric, showing saturation, blindness,
   and over-firing, with the corrected scoreboard and two reversed conclusions.
2. Claim-level deterministic checkers over *free-form* prose (role inversion, invented
   castling, invented board state) with a precision study.
3. A controlled negative result on distillation for coaching, with a same-base prompted
   control and an equivalence analysis rather than a bare null.

## 2. Related work

Four buckets. Positioning sentence for each is the point.

| Bucket | Representative | Our relation |
|---|---|---|
| Chess LLMs, move prediction | ChessBench (Ruoss et al.), ChessLLM (Zhang et al.), Mixture-of-Masters | Different task: we generate prose, not moves |
| Grounded chess reasoning / distillation | **C1** (Tang et al., 2026) | They assert grounding, measure accuracy. We measure grounding |
| Chess commentary generation + evaluation | **Kim et al. 2025 (CCC/GCC-Eval)**, Jhamtani et al. 2018 | Per-move commentary vs. whole-game coaching; their eval is an LLM judge with no deterministic check |
| Verifiable process supervision | **VPS** (Kim et al., COLM 2026) | They SFT a rigid format so extraction is syntactic; we verify unconstrained prose |
| Chess benchmarks | **ChessQA** (Wen et al., 2025), LLM Chess | Semantic category is MCQ recognition, not generation |
| Personalization | Maia-individual (KDD'22), Maia-2, ALLIE | Thousands of games + per-player training; ours is 40 games, no training, and explains |
| RLVR limits in chess | **Chess-R1** (Hwang et al., 2025) | Independently finds the bottleneck is pretrained chess understanding — supports our §6 hypothesis |

**Key positioning sentence:** *no prior work deterministically verifies free-form
generated chess prose against board state, and no prior work audits the validity of its
own automatic grounding metric.*

## 3. Setup

- Pipeline: Stockfish (depth 15) → deterministic facts block → coach LLM → coaching prose.
- Held-out set: 29 Lichess CC0 games, 6 mistake-profile buckets, disjoint from the
  training corpus by game-id **and** normalized-movetext hash.
- Judge: `claude-opus-4-8`, 4-axis rubric (factual correctness, clarity, actionability,
  identifies key mistake), 1–5.
- Models: prompted `qwen3:8b` control; `qwen-coach-8b-v2` = QLoRA on 319 distilled rows.
- **Metric versioning:** reports stamp `metric_versions`; `eval.compare` refuses
  cross-version and cross-judge diffs. (This is itself a small methods point; see §5.)

## 4. The grounding metric and its audit ← **primary contribution**

4.1 The metric. Cited-move set membership against the facts block. Cheap, deterministic,
    no API cost. Used as an eval gate *and* a distillation filter.

4.2 How the failure was found. By reading the judge's stored `rationale` field, present
    since the first judged run but never read; only scores were aggregated. State it; it
    is the transferable lesson.

4.3 Three failure modes, with numbers:
    - **Saturated:** 18/29 at the 1.00 ceiling; `r(grounding, factual) = +0.39`,
      ρ = 0.45, ~15% of variance. Passed its gate while judged factual stalled.
    - **Blind:** cannot see role inversion (played ↔ engine-preferred swapped),
      move-type errors ("castling" for `Kh1`), or invented board state. Two games judged
      factual = 2 scored grounding **1.00**.
    - **Over-firing:** the SAN regex made the piece letter optional, so "your rook on
      b7" parsed as a pawn move. 84–94% of all flagged hallucinations were bare squares;
      **64/64** rows dropped by the distillation gate failed on bare squares alone.

4.4 The fix and what it reversed. Context-aware bare-square resolution (a move unless
    adjacent words prove it a location); a cue-verb allowlist was tried **first and
    rejected**: it dropped 47 genuine citations. Facts-side extraction provably
    unchanged (0/1367 tokens), so re-scores are exact, not approximate.

    | Model | grounding (old) | grounding (corrected) |
    |---|---|---|
    | prompted 3B baseline | 0.812 | **0.861** |
    | 8B v1 | 0.787 | **0.890** |
    | 8B v2 | 0.907 | **0.965** |

    Two conclusions reversed: v1 never regressed grounding (the old metric put it below
    baseline, an artifact), and the 0.85 gate had already been met by the baseline, so
    the gate was never a gate. Distillation gate recovered 52/64 rows at zero teacher cost.

## 5. Claim-level checkers over free-form prose ← **secondary contribution**

Frame it as a *precise partial* instrument, not a judge replacement.

- Role inversion + invented castling. **Precision took three drafts, each killed by real
  data**, worth reporting as a negative-design result:
  1. immediate adjacency missed "you chose a passive rook move (Rc8)";
  2. nearest-cue-in-window flagged 8.4% of the *teacher's own* rows, all false
     positives on recommendations ("the engine wanted you **to play** Bxc3") and
     negations ("by **not playing** f5");
  3. shipped rule: agent named beside the cue, past tense only, no clause crossing, stop
     at an intervening citation.
- Board-state checking by replaying every `fen_before` plus the final position.
- **Results:** 0/467 false positives on teacher rows. On held-out, 5 of 72 flagged games
  were **every one** judged factual = 2.
- **Key quantity:** teacher makes placement claims 0.04/row; students 0.49/game (~12×),
  and 14% of the students' are false. Students *reach for* board narrative the facts
  never gave them.
- **State it:** recall is low. The judge faults 7 games; this flags 1–5. And
  claims *discriminates less* than grounding (v1→v2: +0.008 claims vs +0.075 grounding;
  v1 and v2 tie at 27/29 clean). Neither deterministic metric can serve as the progress
  gate. Report it; do not hide it.

## 6. Does distillation help? A controlled comparison ← **third contribution**

6.1 The control that was missing. Every earlier comparison was fine-tuned **8B** vs
    prompted **3B**, confounding model size with fine-tuning. Same base, same prompt,
    same 29 games, same judge, depth 15 / temp 0; only the LoRA differs.

6.2 Result. Judged factual **identical at 3.72**. Fine-tune wins grounding
    (0.923 → 0.965) and *loses* claims (1 violation → 2).

6.3 **Equivalence framing** (gate 2, computed 2026-08-30, n = 29 paired, positional join
    verified 0/29 mismatches on pgn + coached side):

    | Axis | paired Δ | 90% CI (TOST) | TOST vs δ=0.30 |
    |---|---|---|---|
    | factual correctness | +0.000 | [-0.368, +0.368] | p = 0.088 — **not** equivalent |
    | clarity | +0.034 | [-0.225, +0.294] | p = 0.047 — equivalent |
    | actionability | -0.138 | [-0.321, +0.046] | p = 0.072 — not equivalent |
    | identifies key mistake | -0.034 | [-0.192, +0.123] | p = 0.004 — equivalent |
    | rubric overall | -0.034 | [-0.234, +0.165] | p = 0.016 — equivalent |

    **Report this precisely, because it is not a clean win.** Overall quality,
    clarity, and key-mistake identification are statistically equivalent at the
    pre-registered δ = 0.30. **The factual axis, the headline, is not.** We can exclude
    an effect larger than ±0.37 rubric points, but we cannot exclude the 0.30 effect we
    pre-registered as meaningful. sd(paired diff) = 1.165; MDE at 80% power = 0.63;
    detecting δ = 0.30 would need **~120 games**.

    Stating this plainly is stronger than claiming a tie. The defensible sentence is:
    *"fine-tuning does not produce a large factual improvement (|Δ| < 0.37 with 90%
    confidence), and produces no detectable improvement at all in overall quality; a
    moderate factual effect of the size we pre-registered cannot be ruled out at n = 29."*

6.4 Why reproduction rather than improvement is the expected outcome. Teacher ceiling
    measured at **4.97/5** factual (29/30 at 5, sd 0.18), so the facts block *does*
    support 5/5 coaching, and the ~1.25 gap is headroom neither prompting nor SFT
    captures. Contrast with C1, whose student beat its teacher, but with full
    fine-tuning + RLVR on a binary verifiable reward, 39k samples, 4×H100, and a teacher
    at only 40.8%. Coaching has no verifiable outcome. Chess-R1 (Hwang et al.) reaches a
    compatible conclusion from the RL side.

6.5 Supporting ablation: v2's gain came from **row shape, not row count**
    (v1 82 rows 0.79 → 101 game rows 0.76 → 218 position rows 0.86 → 319 mixed 0.91),
    with a clean same-shape-more-rows control. Cost ~$1.20 GPU, zero API calls.

## 7. Threats to validity ← **do not bury this**

- **Single judge, and judge and teacher share a model family.** Opus taught, Opus judged;
  the teacher scoring 4.97/5 on the judge's own rubric is what that setup would produce
  either way. No human validation yet. *(Gate 3.)*
- **n = 29**, and §6.3 quantifies exactly what that does and does not buy.
- **Teacher ceiling measured on a different distribution:** corpus games, not held-out;
  of the classifiable ones, zero clean_draw and zero multi_blunder.
- **Claim checkers have low recall** by construction.
- **A `worst-move` metric we dropped**: 72.4% for all four models *and* the prompted
  baseline; it tracked the facts block, not model quality. Reporting the metric we
  retired is part of the argument.

## 8. Discussion

The generalizable claims:
1. A deterministic grounding metric can pass its gate while the quantity it proxies does
   not move. Saturation is the tell; check the ceiling rate before trusting a mean.
2. Set-membership metrics are blind to *role*: cite the right token, invert the claim,
   and still score perfectly. Verifying *which* entity did *what* needs replay, not matching.
3. Recurring root cause, hit four times in this project: **the artifact did not record
   enough to know whether the work could be checked or compared** (missing cited/allowed;
   missing game index; a resume key that silently skipped games; unversioned metrics
   producing a cross-version comparison that reversed a sign). Versioning and provenance
   stamps are cheap; discovering you cannot compare two numbers is not.
4. Evaluation sets are purpose-bound: motif tagging scored 0/8 on the held-out set and
   the tagger was *correct*: those are super-GM games where a blunder is positional.

## 9. Limitations and future work

- Human validation of the rubric (the top priority).
- The **class-C hypothesis, untested**: students' invented board narrative may be
  inherited from pretraining rather than from the corpus, in which case more teacher data
  cannot fix it. Chess-R1's finding that the bottleneck is pretrained chess understanding
  makes this the live hypothesis. Testable from outputs already on disk. *(Gate 4.)*
- Amateur distribution: every dataset in the surveyed literature is engine output or
  strong-player games; our coverage study found 52% of untagged amateur mistakes were
  *material* errors excluded by our own thresholds, not positional subtleties.

## Appendix candidates
- Full prompt / facts block (needed for reproduction; also the object under audit).
- The three rejected claim-checker drafts with the sentences that killed each.
- Per-bucket tables.
- Corrected vs. original scoreboard in full.

---

## Figures and tables (build list)

| # | Content | Status |
|---|---|---|
| F1 | Pipeline: Stockfish → facts → coach → three checkers | to draw |
| F2 | Grounding score distribution showing the ceiling pile-up (18/29 at 1.00) | **data on disk** |
| F3 | Scatter: grounding vs. judged factual, r = 0.39 | **data on disk** |
| F4 | Forest plot of paired differences + TOST intervals (§6.3) | **computed** |
| T1 | Corrected scoreboard, all four models, both metric versions | **computed** |
| T2 | Claim-checker precision: teacher 0/467, held-out 5/72 | **on disk** |
| T3 | Ablation: shape vs. volume | **on disk** |
| T4 | Related-work positioning table (§2) | drafted above |

Everything except F1 comes from data already collected. No new compute, no API spend.

---

## Gate status

- **Gate 1, read the missing papers: CLEARED.** Kim et al. 2025 (arXiv:2410.20811,
  NAACL), ChessQA (arXiv:2510.23948), Chess-R1 (arXiv:2507.00726), Jhamtani et al. 2018,
  Maia line. Verdict: **the niche survives and is sharper.** Nobody deterministically
  verifies free-form generated chess prose against board state; ChessQA's Semantic
  category is MCQ recognition; GCC-Eval is an LLM judge with no deterministic component
  and only moderate human agreement. Kim et al.'s own limitations section explicitly asks
  for evaluation with *novice* players, our population.
- **Gate 2, equivalence framing: CLEARED**, and it changed the claim. See §6.3. The
  overall null is an equivalence result; the factual null is underpowered and must
  be stated as a bound, not a tie.
  Script: `scratchpad/equivalence.py`; it **should land as `eval/equivalence.py` with tests
  in the paper PR**, per the project's own "record enough to be checked" lesson.
- **Gate 3, independent judge: BLOCKED on a key.** `eval/backends.py` already has
  `gemini_backend` (default `gemini-2.5-pro`); `.env` has `GEMINI_API_KEY` commented out.
  Free key at https://aistudio.google.com/apikey. Then:
  `python -m eval.run --coach-model qwen-coach-8b-v2 --judge gemini` and the same for the
  prompted control, and report cross-judge agreement. This is the single highest-value
  remaining action.
- **Gate 4 (new), test the class-C hypothesis** from stored outputs. Free.
