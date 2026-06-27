# Chess Analyzer — AI Chess Coach

Analyzes your chess games, explains your mistakes in plain language, and coaches you
to improve. See [`PLAN.md`](./PLAN.md) for the full roadmap and architecture.

**Core idea:** Stockfish does the objective analysis (blunders, centipawn loss, best
moves); a small fine-tuned LLM is the *coach* that explains them; a RAG/memory layer
makes it personalized and "smarter every game."

## Status: Phase 0 — Foundations & data

## Setup

Requires Python 3.12 (system Python 3.14 has no ML wheels yet) and Stockfish.

```bash
brew install stockfish          # already done if `stockfish --version` works
uv venv --python 3.12           # creates .venv
uv pip install -e .             # installs python-chess etc.
```

## Layout

```
engine/    Stockfish wrapper, centipawn-loss + mistake classification
coach/     prompts, LLM client (Ollama), coaching generation        (Phase 2+)
training/  dataset builders + Colab QLoRA notebooks                 (Phase 3+)
memory/    Chroma store, embeddings, RAG retrieval                  (Phase 5+)
api/       FastAPI app                                              (Phase 6)
web/       minimal UI                                               (Phase 6)
eval/      eval harness + rubrics + reports
data/      downloaded PGNs + generated datasets (gitignored)
```

## Quickstart (Phase 0)

```bash
# Download a tiny public PGN sample
python -m engine.fetch_data --sample

# Print a parsed game to confirm the loader works
python -m engine.loader data/raw/sample.pgn
```
