# Literature refresh: is the paper still novel?

Date: 2026-09-13. Extends `2026-08-30-literature-gap-analysis.md`, which covered the 12 PDFs in
`literature/` plus Gate 1's five papers. This pass searched two areas that analysis did not cover:
(a) work since 30 Aug on chess commentary and coaching, and (b) the general research on whether
faithfulness and grounding metrics can be trusted, where the paper's main contribution will be
judged. Sources were web search plus arXiv abstracts and HTML pages, read through a summarizing
fetch tool. **Check every number against the PDF before citing it**; none has been read in full yet.

## Verdict

**The project is still novel, but narrower than the outline claims, and one new paper forces a
reframe.** Two of the outline's sentences are no longer true:

- *"No prior work deterministically verifies free-form generated chess prose against board
  state."* ACT-Eval (Aug 2026) verifies atomic claims in LLM chess commentary with 15+ board and
  engine tools, validated against human chess players.
- *"No prior work audits the validity of its own automatic grounding metric."* Auditing
  grounding and attribution metrics is an established genre (below). An audit alone is not the
  contribution. What it found, in this setting, is.

## New papers that change the positioning

| Paper | What it does | Relation to us |
|---|---|---|
| **Hebbar, Sheng, Oh, Viswanath. *Hallucinations on the Board: Tool-Augmented Evaluation of LLM Chess Commentary* (ACT-Eval). arXiv:2608.04240, 4 Aug 2026** | LLM splits commentary into atomic claims; an LLM judge verifies each with deterministic tools (board queries, attacks, legality, Stockfish at depth 18). 325 position–move pairs, 125 with expert gold atoms; 4 human raters (1800–2200 Elo), judge–human agreement 69–83%. Shows GCC-Eval (plain LLM judge) still gives ≥4/5 relevance to 39.8% of majority-erroneous commentaries | **Closest neighbour, and it overlaps §5.** Differences: per-move commentary on single positions, not whole-game coaching of an amateur; hybrid LLM-plus-tools, where our checkers are fully deterministic with no LLM; no fine-tuning or distillation; no audit of a cheap metric used as a *training-data filter*. Their evidence that plain LLM judges miss errors is also a direct threat to our use of an LLM judge as the reference in §4 and §6 |
| Cui, Ling, Ng. *Communicating Chess Strategies in Natural Language.* arXiv:2607.11486, Jul 2026 | Verbalizes Stockfish strategy trees for puzzles; evaluates by downstream puzzle-solving plus a 30-person human study | Different task (puzzles, utility-based evaluation). Useful for related work: an evaluation that measures usefulness, not faithfulness |
| Soliman, Ehab. *Caïssa AI.* KI 2025 | Fine-tuned LLM plus Prolog rules plus a knowledge graph; a verification module cross-checks commentary | Another neuro-symbolic verifier, reporting tactic-detection hit rate. Cite in related work |
| Ding et al. *Do LLM Attribution Metrics Transfer?* arXiv:2606.23915, Jun 2026 | Audits 8 attribution scorers across datasets and constructs; no metric transfers (Kendall W = 0.07); lexical metrics blind to large rewrites | **The audit genre, in RAG.** Their conclusion ("validate the metric on the target dataset") is what our §4 shows in a new domain |
| Godbole, Jia. *Verify with Caution: The Pitfalls of Relying on Imperfect Factuality Metrics.* arXiv:2501.14883 | 5 factuality metrics on 11 datasets: inconsistent with each other, misestimate system-level performance | Precedent for "metrics disagree and mislead system comparisons". Our Gate 3 result is an instance |
| Kulkarni et al. *Evaluating Evaluation Metrics — The Mirage of Hallucination Detection.* arXiv:2504.18114 | Meta-evaluates 9+ hallucination metrics; weak inter-metric correlation; only the LLM judge aligns with humans | Precedent for lexical and overlap metrics failing; our set-membership metric belongs to that family |
| Tang et al. *StudentSim.* arXiv:2609.01591, Sep 2026 | LLM student simulators, including chess | Tangential; cite only if the paper discusses evaluating coaching by student outcome |

## What is still novel (checked against all of the above)

1. **Whole-game coaching of an improving player**, grounded in an engine facts block and
   personalized over the player's history. Every paper found works on single positions,
   puzzles or per-move commentary.
2. **A cheap deterministic grounding metric used simultaneously as an evaluation gate and a
   distillation data filter**, audited and found to fail in both directions. It over-fired on
   64/64 discarded rows, which were then recovered. The "metric as training filter" consequence
   is not mentioned in any abstract or summary read here (Ding et al. was checked explicitly).
3. **A fully deterministic, LLM-free claim checker** as a precise, low-recall floor: 0 false
   positives on 467 teacher rows. Positioned *against* ACT-Eval: cheaper and reproducible with no
   judge, at the cost of recall.
4. **A controlled distillation null with a same-base prompted control, whose sign depends on the
   judge** (Gate 3). Judge dependence of a headline system comparison, with the rationales showing
   it comes from how each judge weighs severity, is a concrete meta-evaluation result.

## Recommended reframe (changes P6, not the evidence plan)

- **Title direction:** from "auditing a grounding metric" to *three cheap references for grounded
  coaching (a set-membership metric, a deterministic claim checker, an LLM judge) and how each
  one misled us*.
- **§2:** add the audit genre (Ding 2026, Godbole & Jia 2025, Kulkarni 2025) and ACT-Eval as the
  closest neighbour. Drop both "no prior work" sentences.
- **§5:** present the checkers as the deterministic, LLM-free end of the spectrum ACT-Eval
  occupies, with the precision and recall trade-off stated.
- **§6:** rewrite around judge dependence (see the Gate 3 doc).

## One evidence question to decide before P4 (the 20 Sep freeze)

**Run ACT-Eval on our 58 stored coachings?** It is open source (github.com/hebbarashwin/act_eval).
It would give a claim-level error rate as a third reference, sidestepping the severity problem
Gate 3 exposed, and answer the reviewer who asks "why not ACT-Eval?".

- **Against:** it is per-position, and our coaching is whole-game, so adapting it is real work.
  It also needs GPT-5.4 or Gemini-class API calls on long texts. Cost and effort are unmeasured.
- **Alternative:** cite it, state the difference, and let the human ratings (P3) serve as the
  reference.

Recommendation: spend at most half a day checking whether it runs on whole-game text. If it
doesn't, cite it and move on. The standing rule against new experiments after the freeze still
applies.
