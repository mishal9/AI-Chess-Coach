# Literature gap analysis: `literature/` (12 PDFs, 10 distinct papers)

Date: 2026-08-30. Purpose: position the project's two agreed contributions
(see `paper-protocol.md`) against what is actually published, and name what
currently blocks a defensible novelty claim.

## 0. What's in the folder

Two files are duplicates of other files:

| File | Paper | Note |
|---|---|---|
| `2402.04494v2.pdf` | Ruoss et al., *Amortized Planning with Large-Scale Transformers* (ChessBench) | — |
| `079017-2102open.pdf` | same paper, journal version | **duplicate of 2402.04494** |
| `2309.09702v1.pdf` | Hammersborg & Strümke, *Information based explanation methods* | — |
| `s41598-024-70701-2.pdf` | same paper, Sci. Reports version | **duplicate of 2309.09702** |
| `2306.09200v2.pdf` | Feng et al., *ChessGPT* | policy + language corpus |
| `2410.05347v2.pdf` | Ju et al., *ResTNet* | Go/Hex architecture |
| `2501.17186v2.pdf` | Zhang et al., *Complete Chess Games Enable LLM Become A Chess Master* | SFT on full games, 1788 Elo |
| `2512.01992v1.pdf` | Kolasani et al., *LLM Chess* | agentic benchmark, 50+ models |
| `2602.04447v2.pdf` | Frisoni et al., *Mixture of Masters* | MoE, per-GM style routing |
| `2603.20510v2.pdf` | Tang et al., *Grounded Chess Reasoning via Master Distillation* (**C1**) | **nearest neighbour #1** |
| `2605.12519v2.pdf` | Kim et al., *Verifiable Process Supervision* (**VPS**, COLM 2026) | **nearest neighbour #2** |
| `3534678.3539367.pdf` | McIlroy-Young et al., *Learning Models of Individual Behavior in Chess* (Maia-individual, KDD'22) | **nearest neighbour #3** |

A coarse but decisive signal, from grep over all 12 extracted texts:

- `coach`: **1 hit total**, in Maia-individual, and it is aspirational ("a coach
  that understands how you could improve *in particular* would clearly be more helpful").
- `pedagog` / `learner`: only in C1's **Discussion/future-work** section.
- `amateur`: 1 hit, in passing.

Nothing in this set builds or evaluates natural-language coaching for a real
improving player. Every paper optimises **move choice** or **explanation of a
single tactical position**.

---

## 1. Gaps that this project is already positioned to fill

### Gap A: "Grounded" and "faithful" are asserted, never measured

C1 (`2603.20510`) is titled *Grounded Chess Reasoning* and its abstract promises
"faithful, grounded explanations." Its **entire evaluation is first-move accuracy**
(48.1% on 900 puzzles). §3.1 states this plainly: "The model is evaluated on
first-move accuracy, which serves as a proxy for the quality of its internal
reasoning." There is no faithfulness metric, no hallucination count, no check that
the prose refers to pieces that exist.

This project already has the instrument C1 lacks:
`eval/grounding.py` (citation-set membership), `eval/claims.py` (role inversion,
invented castling), `claims.check_board_state` (replays `fen_before`, flags
"your rook on b7" when no black rook was ever on b7). **Measured result: students
make placement claims 0.49/game vs the Opus teacher's 0.04/row (~12×), and 14% of
the students' are false.** That is the quantity C1 asserts is fine.

*Strongest framing:* the field is shipping "grounded explanation" claims on
accuracy proxies; this project measures the grounding those claims assume.

### Gap B: Deterministic verification of *free-form* prose

VPS (`2605.12519`) is the closest methodological neighbour and it deliberately
sidesteps the hard part. Its §3.2 mechanism: SFT first **induces a rigid structured
format**, so "claim extraction is automated... using simple syntactic rules rather
than semantic parsing." Its three verifiers are win-rate MAE, PV overlap, and
logic consistency, all numeric-field comparisons inside a `<think>` template.

This project verifies claims in **unconstrained coaching prose a human is meant to
read**, and the audit doc records why that is hard and how it fails:
bare-square ambiguity ("your rook on b7" parsing as a pawn move), the
recommendation trap ("the engine wanted you *to play* Bxc3" is not a claim about
what happened), negation ("by *not playing* f5"), tense (present = generic advice),
and clause boundaries. Three drafts of the role-inversion rule were each killed by
real data before landing at 0/467 false positives on teacher rows.

**VPS's structured format is a legitimate scientific choice and also an admission
that free-form verification was too hard.** Nobody has published the free-form case.

### Gap C: Measurement validity of the deterministic metric itself

Not one paper in this set audits whether its own automatic metric measures what it
claims. VPS proposes three verifiers and reports improvements on them. C1 reports
accuracy. ChessBench reports action-value accuracy and Elo.

The `2026-08-11-grounding-metric-audit.md` finding is unusual and, in my reading,
publishable on its own:

- The metric was **saturated** (18/29 games at the 1.00 ceiling), which is *why*
  it passed its gate while judged factual quality stalled.
- It was **blind** to role inversion, move-type errors, and invented board state;
  two games judged factual=2 scored grounding **1.00**.
- It **over-fired**: 84–94% of all flagged hallucinations were bare squares, and
  **64/64 rows dropped by the distillation gate failed on bare squares alone**:
  paid teacher data discarded for saying "b7".
- `r(grounding, factual) = +0.39`, about 15% of variance explained.
- The fix recovered 52 of 64 rows at zero API cost and **reversed two prior
  conclusions**: v1 never regressed grounding, and the 0.85 gate had already been
  met by the baseline.

The transferable claim: *a deterministic grounding metric can pass its gate while
the thing it proxies does not move, and the failure is legible only by reading the
judge's stored rationales.* That rationale field existed since PR #9 and was never
read until the audit.

### Gap D: The negative result on distillation, with a control

C1 §5 reports its 4B student **surpasses its teacher** Gemini-3-Flash (48.1% vs
40.8%). This project's prompted-8B control found the opposite on a different task
shape: `qwen-coach-8b-v2` and prompted `qwen3:8b` are **tied at judged factual
3.72**; the fine-tune buys grounding (0.923→0.965) and *loses* on claim violations.

These do not contradict each other, and saying why is the contribution:

| | C1 | this project |
|---|---|---|
| Task | single best move, one right answer | open-ended coaching over a whole game |
| Reward | binary, verifiable | no verifiable outcome exists |
| Training | full FT + RLVR (DAPO), 39k samples, 4×H100 | QLoRA, 319 rows, one 4090 |
| Teacher ceiling | Flash at 40.8% (beatable) | Opus at **4.97/5 judged factual** (not beatable) |

C1 explicitly notes LoRA underperforms full FT (32.1/38.8 vs 40.9) and that the
student exceeding the teacher required **RLVR on a verifiable reward**. Coaching
has no such reward, which is why the SFT-only student saturates at its
base model's quality. That gives the negative result a mechanism.

Reinforced by this project's own ablation: v2's gain came from **row shape, not row
count** (v1 82 rows 0.79 → 101 game rows 0.76 → 218 position rows 0.86 → 319 mixed
0.91), with a clean same-shape-more-rows control.

### Gap E: Cheap personalization vs. expensive personalization

Maia-individual (KDD'22) is the only paper here that reaches for the coaching use
case, and it gets there by **fine-tuning a network per player on thousands of
games**. It predicts moves; it produces no explanation.

Phase 5's memory layer gets a usable personal profile from **40 games and zero
training**: symbolic motif tagging read off Stockfish's own PV, aggregated in
SQLite. On the user's real account (`mshah509`, ~200 Elo): hangs material 40×/23
games, missed capture 26×/20, drops pawn 32×/21, forks 18×/11.

Two findings here are worth reporting, because papers usually leave this kind of thing
out:

- **The design reversal.** ~90 lines of hand-rolled static exchange evaluation were
  deleted after noticing `analyzer.py` ran Stockfish at depth 15 and threw away the
  principal variation. Motifs read tactics off the engine's own refutation line.
- **The wrong-fixture trap.** Motif tagging scored **0/8 on the held-out set and the
  tagger was correct**: those are DrNykterstein (Magnus) games where a blunder is
  positional, not a hung piece. Against the 1100–1900 corpus all four motifs fire.
  An evaluation set curated for one purpose misleads for another.

### Gap F: The distribution nobody serves

C1 trains and evaluates on Lichess puzzles. ChessBench uses Stockfish annotations
over 10M games. Mixture-of-Masters emulates world-class GMs. VPS uses the Lichess
evaluations DB. **Every dataset in this folder is either engine output or
strong-player games.**

This project's coverage measurement reframed its own roadmap: over 25 corpus games
only 31% of mistakes were tagged, but of the 61 untagged, **27 were sub-minor-piece
(dropped pawns) and 5 under the cp bar: 52% were material mistakes excluded by the
project's own thresholds**, not positional subtleties. Amateur error structure is
*not* the tail of master error structure, and thresholds calibrated on strong play
systematically miss it. PR6 took real-game coverage 34% → 47% by lowering one bar.

---

## 2. Blockers to a genuine novelty claim

Ordered by how much they threaten the claim.

### B1: The nearest neighbours are not in this folder (**most serious**)

C1's related-work section names the papers that actually border this project, and
**none of them are in `literature/`**:

- **ChessQA** (Wen et al., 2025): C1 follows its evaluation protocol. If it has a
  commentary/explanation track, it may already be the benchmark this project claims
  is missing.
- **Kim et al., 2025, "concept-guided chess commentary generation."** From the
  title alone this is the closest published work to the coaching task. **Unread.**
- **Jhamtani et al., 2018** and **Zang et al., 2019**: chess commentary generation.
  Prior art on generating natural-language chess text, ~7 years old and likely with
  an established evaluation protocol this project should either adopt or argue against.
- **Chess-R1** (Hwang et al., 2025a): found direct RLVR and SFT+RLVR both fail on
  chess. This is the direct precedent for the negative result.
- **Maia-2** (Tang et al., 2024), **ALLIE** (Zhang et al., 2025a), **Maia4All**
  (Tang et al., 2026): the personalization line has moved on four years since
  Maia-individual.

Cannot write a related-work section, let alone claim novelty, without these. This
is the top action item and it costs nothing but time.

### B2: n = 29, and the metric that can't discriminate

The held-out set is 29 games, 5 per bucket. The audit already showed what that
buys: "the concentrated weakness in one_blunder/inaccuracies was NOISE — the 7
low-factual games span 5 of 6 buckets, and at n=5/bucket on a 1–5 integer scale one
game moves a bucket mean 0.4." A whole planned iteration was targeted on that noise.

Worse for the headline: the gates doc records that **claims discriminates *less*
than grounding** (v1→v2 is +0.008 claims vs +0.075 grounding; v1 and v2 **tie** at
27/29 clean). Neither deterministic metric separates models by more than ~2 games
of 29. A reviewer will ask whether "tied at 3.72" is a real null or an
underpowered one, and right now the answer is *cannot tell*.

Cheapest fix: expand held-out, or report the null as an equivalence test with an
explicit interval rather than as a point-estimate tie.

### B3: Single judge, single rubric, no human validation

Every judged number in the project comes from `claude-opus-4-8` on a 4-axis rubric.
There is no second judge, no inter-rater check, and no human agreement study. The
teacher was also Opus, so **the teacher and the judge are the same model family**,
and the teacher scoring 4.97/5 on the judge's own rubric is the result that
setup would produce whether or not it is true. The project's own record flags a
related caveat (teacher judged on corpus games, student on held-out; zero
clean_draw and zero multi_blunder among the classifiable teacher games).

This is the single most attackable point in the paper. A ~50-item human rating pass,
or a second judge from a different family, would close it.

### B4: Compute and budget asymmetry is now a scope constraint, not just a footnote

C1: 4×H100, full fine-tuning, 39k distilled samples, SFT + RLVR. This project:
QLoRA on one rented 4090, 319 rows, **$3.73 of Anthropic credit left**, with a
judged `eval.run` costing ~$0.40 and judging all 403 teacher rows costing $4.49.

Consequence: any contribution requiring a new training axis (RLVR, full FT, a
second teacher, a scaling curve) is **out of reach**. The viable contributions are
the ones already paid for (the audit, the control, the ablation, the memory layer)
plus free deterministic re-scoring. Grounding and claims cost $0, which makes them the
place to invest.

This also rules out the clean fix for the teacher-ceiling caveat (~$1.00 to generate
teacher coaching on the 29 held-out games), already declined at 27% of runway.

### B5: The two contributions are of different kinds and pull in opposite directions

Contribution 1 is a negative result about distillation. Contribution 2 is a methods
result showing the project's *own* main metric was broken in both directions for
most of the project's life. Presented together and unhedged, a reviewer reasonably
asks: *if the metric was wrong, why should I trust the negative result?*

There is a good answer, and it must be stated up front: **the judged rubric never
touched the parser**, so the factual 3.72-vs-3.72 tie is unaffected by the metric
bug, and the ablation's *ranking* is safe because the same biased instrument was
used on every arm. But the paper has to lead with that, not leave it to be
discovered. The alternative is two shorter papers.

### B6: Task-shape mismatch makes head-to-head comparison impossible

C1, VPS, ChessBench, LLM Chess and ChessLLM all evaluate on **move prediction or
puzzle accuracy**. This project evaluates **coaching prose on whole games**. There
is no shared number. That is what makes the gap real, and also means the paper
cannot put itself on anyone's leaderboard; it must carry its own benchmark, which
raises the bar on B2 and B3 considerably.

### B7: The novel artifacts are engineering, and engineering reads as thin

The new objects are `eval/claims.py`, the context-aware bare-square
parser, and the SQLite motif profile. Each is a set of carefully-tuned heuristics
validated on real data (0/467 FP on teacher rows; 5/72 flagged held-out games,
**every one judged factual=2**). That last number is a strong precision result,
but heuristics are hard to sell as novelty unless framed as *a measurement
instrument with a validation study*, which is also an accurate description of the
work.

### B8: Not a blocker, but it will be raised: the class-C hypothesis is untested

The record notes it: students' invented board narrative may be inherited from
pretraining rather than from the corpus, in which case more teacher data cannot fix
it. Untested. It is the obvious "why don't you just..." reviewer question, and
answering it is cheap: the prompted-8B control's outputs are already on disk.

---

## 3. Recommended positioning

Do **not** claim a better chess coach. The control says that is false.

Claim instead:

> **Deterministic grounding metrics for free-form chess coaching are easy to build,
> easy to saturate, and wrong in both directions, and the field is currently
> shipping "grounded explanation" claims without measuring grounding at all.**
> We audit our own metric, correct it, show the correction reverses two of our prior
> conclusions, and report a controlled negative result: distillation from a frontier
> teacher reproduces the base model's judged quality with better citation hygiene,
> but does not exceed it, because coaching, unlike puzzle-solving, has no verifiable
> reward to bootstrap from.

That claim is supported by work already done and paid for, it is directly responsive
to C1 and VPS, and it does not require another training run.

### Immediate next actions

1. **Read the six missing papers** (B1), especially Kim et al. 2025 and ChessQA.
   Everything else is provisional until this is done. Zero cost.
2. Re-frame the null as an equivalence interval rather than a tie (B2). Zero cost.
3. Run a second judge or a small human agreement pass (B3). This is where remaining
   budget is best spent, ahead of any new dataset.
4. Test the class-C hypothesis from outputs already on disk (B8). Zero cost.

---

## Postscript (same day): B1 is cleared, and the verdict is favourable

The six missing papers were located and read. **The niche survives, and is sharper than
this document originally assumed.** Details and citations in
`2026-08-30-paper-outline.md`; the short version:

- **Kim et al., NAACL 2025, "Bridging the Gap between Expert and Language Models:
  Concept-guided Chess Commentary Generation and Evaluation"** (arXiv:2410.20811). The
  true nearest prior art. CCC generates commentary from LeelaChessZero concept vectors;
  GCC-Eval scores it with a **GPT-4o judge on relevance / completeness / clarity /
  fluency**. It has **no deterministic grounding or hallucination check**, and they
  report human agreement of only Pearson **0.40–0.56** / Kendall **0.23–0.39**. They
  evaluate **per-move** commentary against human GameKnot comments (Jhamtani et al. 2018),
  judged by **expert** players, and their own limitations section asks for a novice-player
  evaluation, which is our population.
  *This helps the paper:* it is a published data point that this whole class of
  metric has only moderate validity, which turns our audit from self-criticism into
  evidence about a field-wide problem. Our own r(grounding, factual) = 0.39 sits in the
  same range.
- **ChessQA** (Wen, Tang & Anderson, arXiv:2510.23948). Its "Semantic" category (the one
  that sounded threatening) is **4-way multiple choice with exact-match grading**. It
  measures *recognition* of good commentary, never *generation*. No generated-text
  grounding anywhere in the benchmark.
- **Chess-R1** (Hwang et al., arXiv:2507.00726, "Can Large Language Models Develop
  Strategic Reasoning?"). Finds RLVR on chess plateaus and concludes the limit "stems from
  a deficit in the pretrained models' internal understanding of chess — a deficit which RL
  alone may not be able to fully overcome." **This independently supports B8's class-C
  hypothesis** and should be cited in its support rather than treated as a rival.
- **Jhamtani et al. 2018**: the GameKnot commentary dataset the whole commentary line
  builds on, including Kim et al.
- **Maia-2 / ALLIE / Maia4All**: the personalization line has advanced, but still
  predicts moves and still requires per-player training at scale. No explanation.

**Net effect on the blockers list:** B1 is closed. B3 (single judge, no human validation)
becomes *more* important: Kim et al. did validate GCC-Eval against human
raters, so a reviewer has a precedent to hold us to.
