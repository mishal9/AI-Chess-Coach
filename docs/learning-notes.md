# Chess Analyzer — AI Engineering Notes

*Building an AI chess coach, end-to-end. The goal isn't just the app — it's learning **production AI engineering** by building it.*

---

## 1. The Big Idea — Why split the system?

> **LLMs are unreliable chess players.** They hallucinate moves and evaluations.

So we **separate responsibilities** — each component does only what it's good at:

| Layer | Job | Tool |
|---|---|---|
| **Engine** | Objective truth (what's a blunder?) | Stockfish |
| **LLM Coach** | Explain it in plain language | Fine-tuned small LLM |
| **Memory** | Personalize over time | RAG / vector DB |
| **Serving** | Make it usable | FastAPI + Web UI |

**Key insight:** narrowing the LLM's job to *"explain these facts"* is exactly what lets a **small** model succeed. We never ask it to *calculate* chess — only to *talk about* it.

---

## 2. The Pipeline at a Glance

```
PGN game
   │
   ▼
[Stockfish] ──► objective per-move analysis
   │            (cp-loss, blunder tags, best move)
   ▼
[LLM Coach] ──► natural-language explanation + lessons
   │
   ▼
[RAG / Memory] ──► personalized to the player's history
   │
   ▼
[FastAPI + UI] ──► paste a game → get coached
```

---

## 3. Core Concept — Centipawn Loss

Everything is measured in **centipawns (cp)** from **White's point of view**:
- `+100` ≈ "White is up one pawn"
- negative = good for Black

**Centipawn loss** = how much a move *worsened* your position vs. the engine's best:

```
White to move:   loss = eval_before_best − eval_after
Black to move:   loss = eval_after − eval_before_best
(clamp negatives to 0 — you can't beat "best")
```

> 💡 **Why clamp at 0?** Search noise at finite depth can make a move look *better* than the engine's earlier "best." That's an artifact, not brilliance — so we floor it at zero.

### Mistake classification (Lichess/chess.com convention)

| Label | cp-loss | Symbol |
|---|---|---|
| Best | 0 | |
| Good | 1–49 | |
| Inaccuracy | 50–99 | ?! |
| Mistake | 100–299 | ? |
| Blunder | ≥ 300 | ?? |

### Handling forced mate
A mate isn't a material count — it's *winning*. Map **"mate in N"** to a huge cp value (`10 000 − N`), so a mate-in-1 outranks a mate-in-5, and any mate outranks any material edge.

---

## 4. Engineering Detail — Evaluate Each Position *Once*

A subtle but important optimization in the analysis loop:

> The position **after** move *i* is the **same** as the position **before** move *i+1*.

So we evaluate each board position **exactly once** and reuse the result as both:
- the *"after"* for the move that created it, and
- the *"before"* for the next move.

This roughly **halves** the number of (expensive) engine calls. *Small idea, big runtime win — this is the kind of thinking that matters at scale.*

---

## 5. The "Small Model First" Philosophy

The project's discipline rule:

> **Extract all the performance you can from a small model before scaling parameters.**

The order of attack when quality is lacking:
1. **Better data** (more / cleaner training pairs)
2. **Better prompts**
3. **Better training** (fine-tuning recipe)
4. *Only then* — a bigger model

**Why?** A 3B model that fits a free GPU and runs on a laptop is cheap, fast, and learnable. Scaling params is the *last* resort, not the first.

---

## 6. Fine-Tuning — QLoRA in a Nutshell

We can't train a 3B+ model on a 16GB M1. So:

- **QLoRA** = Quantized base model (4-bit) + **LoRA** adapters (tiny trainable matrices).
- Only the adapters train → fits a **free Colab T4**.
- Adapters are *small* (MBs), easy to version and swap.

**The export path:**
```
LoRA adapter → merge into base → convert to GGUF → run via Ollama on the Mac
```

**Distillation** builds the dataset: a *large* model writes high-quality coaching for many analyzed positions → those `(analysis → coaching)` pairs train the small model. **This dataset is the project's moat.**

---

## 7. RAG / Memory — "Gets Smarter Every Game"

Per user, store every analyzed game + its mistakes + recurring **themes** in a **vector DB (Chroma)**.

At coaching time, **retrieve** the player's history:
> *"You keep hanging pieces in the middlegame."*

**Two timescales of "learning":**
- **Now (RAG):** retrieval personalizes *this* session immediately.
- **Later (periodic refresh):** a *monthly* fine-tune on aggregated coaching data.

⚠️ **Not** per-game retraining — that's impractical and unnecessary. The memory layer does the fast personalization; retraining is occasional.

---

## 8. Evaluation — How We Know It's Good Enough

You can't improve what you don't measure. The **eval harness** is the referee:

- Held-out test games with **known** engine analysis.
- A **coaching-quality rubric**:
  - **Factual correctness** (matches the engine)
  - **Clarity**
  - **Actionability**
  - Correctly identifies the **key** mistake
- Compare: *prompted baseline* vs. *fine-tuned* vs. *(only if needed)* larger model.

> The fine-tuned model must **beat the prompting baseline** to justify its existence. The eval is what *enforces* the "small model first" rule.

---

## 9. The Stack (and why each choice)

| Concern | Choice | Why |
|---|---|---|
| Engine | Stockfish + `python-chess` | Free, superhuman, scriptable |
| Base model | Qwen2.5-3B-Instruct | Strong small instruct model, QLoRA-friendly |
| Fine-tuning | QLoRA (`trl`/`peft`) on Colab | Fits a free T4 |
| Local serving | Ollama (GGUF) | One command, ~2–3GB for a Q4 3B |
| Vector DB | Chroma | Zero-infra, embedded |
| Embeddings | `sentence-transformers` (bge-small) | Local, free |
| Backend | FastAPI | Async, easy to containerize |
| Hosting | HF Spaces / Fly.io / Render | Start at **$0** |

**Environment gotcha learned the hard way:** system Python 3.14 has no ML wheels yet → pin a **Python 3.12** venv (managed with `uv`) for all ML work.

---

## 10. Transferable Lessons

These outlive the chess project:

1. **Decompose by reliability** — give deterministic work to deterministic tools; give language work to the LLM.
2. **Validate each layer alone** before stacking the next (the engine report is useful *before* any LLM).
3. **Baseline before fine-tuning** — prompting sets the bar that training must clear.
4. **Measure with a rubric**, not vibes.
5. **Cheap + small first** — scale only when the data shows you must.
6. **Two learning loops:** fast (retrieval) vs. slow (retraining).

---

*Phase 0 ✅ Foundations · Phase 1 ◐ Engine analysis (in progress) · Phases 2–6 ahead.*
