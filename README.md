# Chess Analyzer — AI Chess Coach

Analyzes your chess games, explains your mistakes in plain language, and coaches you
to improve. See [`PLAN.md`](./PLAN.md) for the full roadmap and architecture, and
[`docs/experiments/`](./docs/experiments/) for paper-grade records of the fine-tuning
experiments and their results.

**Core idea:** Stockfish does the objective analysis (blunders, centipawn loss, best
moves); a small fine-tuned LLM is the *coach* that explains them; a RAG/memory layer
makes it personalized and "smarter every game."

## Status: Phase 2 — LLM coaching baseline (prompting)

## Setup

Requires Python 3.12 (system Python 3.14 has no ML wheels yet) and Stockfish.

```bash
brew install stockfish          # already done if `stockfish --version` works
uv venv --python 3.12           # creates .venv
uv pip install -e .             # installs python-chess etc.

# For the Phase-2 coach, also install the LLM client and pull the local model:
uv pip install -e '.[coach]'
ollama pull qwen2.5:3b-instruct   # ~1.9GB; run `ollama serve` if not already up
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
# Download a tiny public PGN sample (Lichess)
python -m engine.fetch_data --sample

# ...or pull your most recent games from chess.com (standard games only)
python -m engine.fetch_data --source chesscom --user hikaru --max 20

# Print a parsed game to confirm the loader works
python -m engine.loader data/raw/sample.pgn
```

## Quickstart (Phase 1 — analysis report)

```bash
# Analyze a game → readable mistake summary (ACPL, blunders, worst move, top mistakes)
python -m engine.report data/raw/sample.pgn --depth 16

# Also write the full structured JSON report (per-move eval, cp-loss, win-prob, quality)
python -m engine.report data/raw/sample.pgn --json report.json

# Pick a specific game in a multi-game file; send JSON to stdout for piping
python -m engine.report games.pgn --game-index 2 --json - | jq .summary
```

Move quality is judged by the drop in the mover's **win probability** (a sigmoid over the
centipawn eval), so already-decided positions and forced mates don't produce false blunders,
and a move matching the engine's own top choice always scores as best.

## Quickstart (Phase 2 — coaching baseline)

Turns the Phase-1 engine report into natural-language coaching using a *prompted* local
model (Qwen2.5-3B via Ollama). No fine-tuning yet — this is the baseline a fine-tuned
model must beat.

```bash
# PGN in → coaching text out (coaches the side that played worse by default)
python -m coach.coach data/raw/sample.pgn --depth 15

# Coach a specific side; reuse a saved report to skip re-running Stockfish
python -m coach.coach games.pgn --side black
python -m engine.report game.pgn --json report.json
python -m coach.coach --from-json report.json --side white

# Inspect exactly what facts are sent to the model (no LLM call)
python -m coach.coach game.pgn --show-facts
```

The coaching prompt is strictly grounded in the engine facts (see `coach/prompts.py`).
Known baseline limitation: when the engine flags **no** concrete mistake for the coached
side (e.g. a slowly-lost game), the 3B model still tends to confabulate specifics despite
the grounding rules — motivating the Phase-3/4 dataset + fine-tune and the eval harness.
