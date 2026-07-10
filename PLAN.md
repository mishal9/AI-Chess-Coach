# Chess Coaching AI — Project Plan

## Context

**Goal:** Build a production AI system that analyzes a user's chess games, explains
their mistakes in plain language, coaches them to improve, and gets more
personalized over time. Host it online for others to use. Secondary goal: **learn
AI engineering end-to-end** by building this. Start with a *small* model and only
scale parameters if we genuinely can't extract more performance.

**Key constraint / environment (verified on this machine):**
- MacBook Pro **M1 Pro, 16GB RAM** — good for local dev + serving small *quantized*
  models; **not** for training 3B+ models. Training happens on **Google Colab** (free T4).
- `ollama` and `mlx` already installed; `docker`, `git`, `node`, `brew` present.
- **Stockfish not installed yet** (`brew install stockfish`).
- ⚠️ System Python is **3.14** — PyTorch/transformers/trl have no 3.14 wheels yet.
  All ML work must run in a pinned **Python 3.12** virtual env.
- Project home (currently empty): `~/Work/chess_analyzer`.
- Data: **public datasets** (Lichess open database, Kaggle, Lichess puzzles).

## The core architecture decision (read this first)

LLMs are unreliable chess players — they hallucinate moves and evals. So we split
responsibilities:

```
PGN game
   │
   ▼
[Stockfish engine]  ── objective truth: per-move eval, centipawn loss,
   │                    blunder/mistake/inaccuracy tags, best move, missed tactics
   ▼
[Fine-tuned small LLM = "the Coach"]  ── turns engine facts into natural-language
   │                                       explanation + lessons, in a coaching voice
   ▼
[RAG / Memory layer]  ── stores every analyzed game & mistake per user in a vector DB;
   │                       retrieves the player's recurring weaknesses to personalize
   ▼
[FastAPI + web UI]  ── upload/paste a game or connect a username → get coaching
```

- **"Gets smarter with every game"** = the RAG/memory layer accumulating the player's
  history + a *periodic* (e.g. monthly) fine-tune refresh on aggregated coaching data.
  **Not** per-game retraining (impractical and unnecessary).
- This keeps the LLM's job narrow and learnable, which is exactly why a *small* model
  can succeed at it.

## Recommended stack

| Concern | Choice | Why |
|---|---|---|
| Engine | **Stockfish** + `python-chess` | Free, superhuman, scriptable |
| Base model | **Qwen2.5-3B-Instruct** (fallback: Llama-3.2-1B/3B) | Strong small instruct model; QLoRA-friendly on a T4 |
| Fine-tuning | **QLoRA** via `trl`/`peft` on **Colab**; MLX-LM as a local alt | Fits free T4; LoRA adapters are tiny |
| Local serving/dev | **Ollama** (GGUF) on the M1 | One command, runs a Q4 3B in ~2-3GB |
| Vector DB | **Chroma** (local, embedded) | Zero-infra to start; swap later if needed |
| Embeddings | `sentence-transformers` (e.g. `bge-small`) | Runs locally, free |
| Backend | **FastAPI** | Standard, async, easy to containerize |
| Hosting | Start free: **HF Spaces / Fly.io / Render**; serverless GPU only if required | Keep cost ~$0 until there's real usage |

Whole stack can run at **$0** to start.

## Phased plan (each phase is a learning milestone + a working artifact)

### Phase 0 — Foundations & data (no ML)
- Init repo at `~/Work/chess_analyzer`, git, README, structure (see below).
- Create **Python 3.12 venv** (`brew install python@3.12`; manage with `uv`).
  Do NOT use system Python 3.14.
- `brew install stockfish`; `pip install python-chess`.
- Acquire public data: a slice of the **Lichess open database** (monthly PGN dumps,
  many games already carry `%eval` computer annotations → saves engine time) and the
  **Lichess puzzle database** (great for tactics). Optionally a Kaggle chess dataset.
- **Deliverable:** scripted download + a PGN loader that prints games.

### Phase 1 — Engine analysis pipeline (still no ML)
- For each game: walk moves with `chess.engine.SimpleEngine`, capture eval before/after,
  compute **centipawn loss**, classify each move (blunder / mistake / inaccuracy / good),
  detect missed tactics, tag opening (ECO) & game phase.
- Output a structured JSON "analysis report" per game.
- **Deliverable:** a CLI that takes a PGN and emits an objective mistake report. This is
  already useful on its own — validate it before adding any LLM.

### Phase 2 — LLM coaching baseline (prompt engineering, no fine-tuning yet)
- Feed the Phase-1 JSON into a base instruct model (run **Qwen2.5-3B via Ollama locally**)
  with a carefully designed coaching prompt → natural-language explanations.
- This establishes a **baseline** and teaches prompt engineering. Critical: it's the
  thing fine-tuning must *beat* to justify itself.
- **Deliverable:** end-to-end "PGN in → coaching text out" using only prompting.

### Phase 3 — Build the fine-tuning dataset
- Generate `(position + engine analysis) → (coaching explanation)` pairs.
- Sourcing: **distillation** from a strong model (have a large model write high-quality
  coaching for many analyzed positions) + curated human annotations where available.
  Teacher = `claude-opus-4-8` (via `training.distill`); grounding-self-checked so no teacher
  hallucination reaches the student.
- Define a consistent coaching style/schema. This dataset *is* the project's moat.
- **Deliverable:** a versioned train/val/test dataset (JSONL).
- **Dataset versions — deliberately staged so we can *measure* the gain from richer data:**
  - **v1 — one row per game (current).** One coaching paragraph per whole game. Simplest;
    gets a first fine-tune + eval loop working end-to-end. ~93-game corpus → ~93 rows.
  - **v2 — one row per critical position (revisit for a second fine-tune).** Emit a separate
    coaching example for each flagged mistake/moment in a game, multiplying the same corpus
    into hundreds of rows. This is where the leakage-safe *per-game* split (`assign_split`,
    already built) becomes load-bearing — all positions from one game must stay in one split.
  - **Comparison is the point:** fine-tune on v1, then on v2, and report the `eval.run` delta
    on the *same* held-out set (overall / factual / grounding). Quantifies how much per-position
    data volume buys us — a concrete result to show, not just "we made it bigger."

### Phase 4 — Fine-tune the small model (Colab)
- **QLoRA** fine-tune Qwen2.5-3B on Colab (start even smaller, Llama-3.2-1B, as a cheap
  sanity baseline). Export LoRA → merge → **GGUF** → run via Ollama on the M1.
- **Evaluate vs. the Phase-2 baseline** (see eval harness below). Only move to a larger
  model if the gap to "good" can't be closed with data/prompt/training improvements.
- **Deliverable:** a fine-tuned coach model + an eval report showing it beats baseline.

### Phase 5 — Memory / RAG / "gets smarter" loop
- Per user: store each analyzed game, its mistakes, and recurring **themes** in **Chroma**.
- At coaching time, retrieve the player's history ("you keep hanging pieces in the
  middlegame") to personalize and track progress over time.
- Define the continuous-improvement loop: new game → analysis → stored → informs future
  coaching now, and feeds the **periodic fine-tune refresh** later.
- **Deliverable:** personalized coaching that references the user's past patterns.

### Phase 6 — Serving & hosting (the production artifact)
- **FastAPI** wrapping the full pipeline; endpoints: submit game (PGN / paste / username),
  get report, get coaching, get progress.
- Minimal web UI (upload/paste a game; show board + annotated mistakes + coaching).
- Containerize (Docker). Deploy app on a free/cheap tier; keep model inference on Ollama
  (small VPS) and reach for serverless GPU only when load demands it.
- **Deliverable:** a public URL where someone can paste a game and get coached.

## Proposed repo structure
```
chess_analyzer/
├── data/            # downloaded PGNs, puzzles, generated datasets (gitignored)
├── engine/          # Stockfish wrapper, centipawn-loss + mistake classification
├── coach/           # prompts, LLM client (Ollama), coaching generation
├── training/        # dataset builders + Colab QLoRA notebooks
├── memory/          # Chroma store, embeddings, RAG retrieval
├── api/             # FastAPI app
├── web/             # minimal UI
├── eval/            # eval harness + rubrics + reports
└── README.md
```

## Evaluation harness (how we decide "small model is enough")
- Held-out test games with known engine analysis.
- A coaching-quality rubric: factual correctness (matches engine), clarity,
  actionability, correct identification of the *key* mistake.
- Compare: prompted baseline vs. fine-tuned vs. (only if needed) larger model.
- This is what enforces your "extract all performance from the small model first" rule.

## Verification (end-to-end checkpoints)
1. **Phase 0:** `stockfish` runs; loader prints a known game's moves.
2. **Phase 1:** run the analyzer on a famous game (e.g. a known blunder) and confirm it
   flags the blunder with correct centipawn loss.
3. **Phase 2 & 4:** run the eval harness; fine-tuned model scores higher than baseline on
   the rubric over the held-out set.
4. **Phase 5:** submit two games from the same user; confirm the second coaching session
   references a pattern from the first (RAG working).
5. **Phase 6:** hit the deployed URL, paste a PGN, receive a board + mistake report +
   personalized coaching.

## Open decisions to revisit later (not blocking)
- Exact base model (Qwen2.5-3B vs Llama-3.2-3B) — pick empirically in Phase 4.
- Hosting provider for public launch — decide when the app actually works (Phase 6).
- Whether to add user accounts/auth — only when going truly public.

## First concrete steps once approved
1. `brew install stockfish python@3.12`
2. Scaffold `~/Work/chess_analyzer` repo + 3.12 venv (via `uv`) + `python-chess`.
3. Download a small Lichess PGN slice and build the Phase-1 engine analyzer.
4. Validate the analyzer on a known game before any LLM work.
