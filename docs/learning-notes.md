# Chess Analyzer: AI engineering notes

*Building an AI chess coach end to end, and learning **production AI engineering** by building it.*

*Rewritten 2026-10-08 to match the code. The first version described the original plan
(centipawn thresholds, Qwen2.5-3B on Colab, Chroma RAG, a hosted demo); that is in git history.
What changed and why is in [`PLAN.md`](../PLAN.md) and [`docs/experiments/`](./experiments/).*

---

## 1. Why split the system?

> **LLMs are unreliable chess players.** They hallucinate moves and evaluations.

So we **separate responsibilities**, and each component does only what it's good at:

| Layer | Job | Tool |
|---|---|---|
| **Engine** | Objective truth (what's a blunder?) | Stockfish + `python-chess` |
| **LLM Coach** | Explain it in plain language | Qwen3-8B (fine-tuned or base) on Ollama |
| **Memory** | Personalize over time | SQLite history + rule-based motif tags |
| **Serving** | Make it usable | FastAPI, server-rendered pages |
| **Eval** | Decide whether any of it is good | Grounding metric, claim checkers, LLM judges, statistics |

Narrowing the LLM's job to *"explain these facts"* is what lets a **small** model succeed. It talks about chess positions; it never has to calculate them.

---

## 2. The pipeline

```
PGN game (chess.com sync or upload)
   │
   ▼
[Stockfish, depth 18] ──► per-move analysis, cached per game + depth + engine build
   │                      (win-prob loss, label, best move, engine line)
   ▼
[Memory] ──► motif tags (hung material, dropped pawn, missed capture, fork, back rank)
   │         + a profile of recurring mistakes with a noise-aware trend
   ▼
[Facts block] ──► the only things the coach is allowed to cite
   │
   ▼
[LLM Coach] ──► natural-language explanation + lessons
   │
   ▼
[Grounding check] ──► "every move it cited was real" note, stored with the coaching
   │
   ▼
[FastAPI pages] ──► dashboard → game list → game page → "coach this game"
```

---

## 3. Win-probability loss

Evaluations come from Stockfish in **centipawns (cp)** from **White's point of view**:
- `+100` ≈ "White is up one pawn"
- negative = good for Black

The first version judged moves by raw **centipawn loss**. That breaks in decided positions:
going from +900 to +600 is a 300cp "blunder" that changes nothing. So each eval is mapped
onto a **win probability** with a logistic sigmoid (Lichess's fitted constant):

```
win_prob(cp) = 1 / (1 + e^(−0.00368208 · cp))      cp = 0 → 0.5
```

A move's loss is the drop in the **mover's** win probability (White's, or its complement for
Black), clamped at 0:

```
loss = max(0, wp_mover(eval_before_best) − wp_mover(eval_after))
```

> **Why this works:** the sigmoid saturates. Already-winning or already-lost positions sit
> near 1 or 0, so even large cp swings there produce small win-probability drops and no fake blunders.

> **Why clamp at 0?** Search noise at finite depth can make a move look *better* than the
> engine's earlier "best." That's an artifact, so we floor it at zero.

### Mistake classification (Lichess convention, on win-probability loss)

| Label | Win-prob loss | Symbol |
|---|---|---|
| Best | 0 | |
| Good | < 0.10 | |
| Inaccuracy | 0.10–0.19 | ?! |
| Mistake | 0.20–0.29 | ? |
| Blunder | ≥ 0.30 | ?? |

### Handling forced mate
A mate means the game is won, whatever the material. Map **"mate in N"** to `10 000 − N` cp, so a
mate-in-1 outranks a mate-in-5. Through the sigmoid, any mate saturates near 1/0.

### ACPL is still kept, with a cap
Average centipawn loss is shown for familiarity. Each eval is capped at **±1000** before
differencing, so one decided position can't swamp the average.

### Labels depend on depth
Re-running the held-out games at depth 20 changed 8% of game labels (12% from 16 → 18).
Labels near a threshold are noisy; treat them as such
(`experiments/2026-09-26-depth-20-label-stability.md`).

---

## 4. Evaluate each position once, cache each game once

> The position **after** move *i* is the **same** as the position **before** move *i+1*.

So each board position is evaluated **exactly once** and reused as both the *"after"* of the
move that created it and the *"before"* of the next move, which roughly **halves** engine calls.

The same idea one level up: Stockfish is deterministic at a fixed depth, so a whole game's
report is cached (`engine/cache.py`), keyed by the game, the depth, the Stockfish build and a
hash of the analyzer code. Change the scoring code and old entries invalidate themselves.

---

## 5. Small model first

> **Extract all the performance you can from a small model before scaling parameters.**

The order of attack when quality is lacking:
1. **Better data** (more / cleaner training pairs)
2. **Better prompts**
3. **Better training** (fine-tuning recipe)
4. *Only then*, a bigger model

In practice the project started on Qwen2.5-3B and moved to **Qwen3-8B**, which still runs
locally on a 16GB Mac as a Q4 GGUF. The 3B fine-tune was superseded before it was evaluated, so
the comparisons that matter use the 8B base, prompted, as the control
(`experiments/2026-08-14-prompted-8b-control.md`).

---

## 6. Fine-tuning: QLoRA and distillation

We can't train an 8B model on a 16GB M1. So:

- **QLoRA** = base model quantized to **4-bit NF4** (with double quantization) + **LoRA**
  adapters (small low-rank trainable matrices). Only the adapters train.
- Recipe (`training/qlora_8b_runpod.ipynb`, on a rented RunPod GPU): rank **r = 16**,
  **α = 32**, dropout 0.05; learning rate **1e-4** with a **cosine** schedule and 5% warmup;
  batch 2 × **gradient accumulation** 8 = effective batch 16; 3 epochs.

**The export path:**
```
LoRA adapter → merge into base → convert to GGUF (Q4_K_M) → Modelfile → Ollama
```

**Distillation** builds the dataset: a *large* teacher model writes coaching for analyzed
positions, and those `(facts → coaching)` pairs train the small model. Rows are filtered by a
QC step (grounding + claim checks) before training.

**Leakage-safe split:** a row's train/val/test split comes from a SHA-256 hash of its game key,
so the split is reproducible with no stored shuffle and every position from one game lands in
the same split.

**What it showed:** distillation reproduced the base model's judged factual quality (3.72 vs
3.72) and improved citation hygiene, but did not exceed it. A template coach with no
model at all scored higher on factual accuracy. The LLM's edge is actionability.

> **Teacher licence:** some providers' terms forbid using outputs as training targets. Check
> before training on a teacher's rows (see `PLAN.md`).

---

## 7. Memory

Per user, every analyzed game is stored in **SQLite** (`memory/store.py`). No vector database:
the questions the coach needs answered ("how often do you hang material?") are counts over
structured data, which SQL answers exactly.

- **Motif tags** (`memory/motifs.py`): deterministic rules replay the engine line to tag hung
  material, dropped pawns, missed captures, allowed forks and back-rank problems.
- **Profile** (`memory/profile.py`): recurring motifs, mistakes by game phase and opening, and
  a trend.
- **The profile is rendered into the facts block**, so the coach can say "this is the fourth
  time" and the grounding check still applies to it.

### The trend is noise-aware
Comparing earlier games with recent ones, the gap in mistakes per game is only reported when
it exceeds one **standard error of the difference in means**:

```
noise_floor = √( s₁²/n₁ + s₂²/n₂ )
```

Smaller gaps are reported as *"unclear"* rather than "you're getting worse". A
severity-weighted signal (win probability thrown away per game) is shown alongside, because a
raw count jumps by a whole unit when a move crosses a threshold.

*Not built:* embedding-based retrieval ("find past positions like this one") is parked in
`PLAN.md`, as is a periodic re-fine-tune.

---

## 8. Evaluation

The **eval harness** (`eval/`) decides whether a change helped:

- **Held-out set:** 29 games in buckets (one blunder, multi-blunder, slow loss, clean draw, …).
- **Grounding metric** (`eval/grounding.py`): every move the coaching cites, minus the moves in
  the facts block = hallucinated moves. A set difference, no LLM. Its first version flagged
  square names in prose ("your rook on b7") as moves (84–94% of all its flags), so it was
  audited and fixed.
- **Claim checkers** (`eval/claims.py`): catch true moves described falsely, such as swapping
  the played move with the engine's move, or calling a king move castling.
- **LLM judge with a rubric** (`eval/rubric.py`, `eval/judge.py`): factual accuracy, clarity,
  actionability and more, on a 1–5 scale. Re-scored with a second judge to check agreement.
- **Controls:** a prompted base model (same size, no fine-tune) and a **template coach** with no
  model at all. A result with no floor can't be placed on a scale.
- **Human ratings** (`eval/human_rating.py`): a stratified sample, scored by people, with
  consensus by median.

### The statistics

| Question | Tool |
|---|---|
| Is the fine-tune *the same as* the baseline? | **TOST** (two one-sided t-tests) on paired per-game differences, against a pre-registered margin (Δ = 0.30 rubric points), with the matching **90% CI** |
| Does it hold without normality? | **Wilcoxon signed-rank** test on the same differences |
| Could this sample have seen an effect at all? | **Minimum detectable effect** at 80% power, and `n ≈ ((z₀.₉₇₅ + z₀.₈)·σ/Δ)²` for planning |
| Do two judges (or a judge and humans) agree? | **Pearson r** and **Kendall's τ** (τ because 1–5 scores are ordinal), exact match, within-one, bias |
| What counts as a pass? | Thresholds **pre-registered** in each experiment doc before the run |

> The fine-tuned model must **beat the prompting baseline** and the template floor to
> justify its existence. The eval is what *enforces* the "small model first" rule.

---

## 9. The stack, and why each choice

| Concern | Choice | Why |
|---|---|---|
| Engine | Stockfish + `python-chess` | Free, superhuman, scriptable |
| Base model | Qwen3-8B | Strong small instruct model; Q4 GGUF fits a 16GB Mac |
| Fine-tuning | QLoRA (`trl`/`peft`/`bitsandbytes`) on RunPod | 4-bit base + adapters fit one rented GPU |
| Local serving | Ollama (GGUF + Modelfile) | One command, runs on the laptop |
| Memory | SQLite | Zero-infra; the questions are counts, not similarity |
| Backend | FastAPI + Jinja2 | Server-rendered, no JS toolchain |
| Judges | Claude Opus, Gemini 3.1 Pro (API) | Two judges to check each other |
| Statistics | `scipy` | t-distribution, Wilcoxon, correlations |

Hosting for other players is parked; the app runs locally.

**Environment gotcha learned the hard way:** system Python 3.14 has no ML wheels yet → pin a
**Python 3.12** venv (managed with `uv`) for all ML work.

---

## 10. Transferable lessons

These outlive the chess project (the full list is in [`lessons-learned.md`](./lessons-learned.md)):

1. **Decompose by reliability:** give deterministic work to deterministic tools; give language work to the LLM.
2. **Validate each layer alone** before stacking the next (the engine report is useful *before* any LLM).
3. **Baseline before fine-tuning**, and add a no-model floor; each control changed a conclusion here.
4. **Measure with a rubric**, then **audit the metric**; this one was wrong in both directions.
5. **Cheap and small first:** scale only when the data shows you must.
6. **Pre-register the pass bar**, and report a failed result as a failure.
7. **Respect noise:** small samples and threshold labels fool you; say "unclear" when it is.
