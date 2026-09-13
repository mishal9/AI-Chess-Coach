# Chess Analyzer — AI Chess Coach

Syncs your chess.com games, finds the mistakes you keep making, and coaches you on them.
Stockfish decides what is true; a local LLM explains it; a SQLite memory of your past games
lets the coach say "this is the fourth time" and mean it.

The project has two outputs, planned in [`PLAN.md`](./PLAN.md):

1. **The app** — a personal coach over your own game history (`engine/`, `coach/`, `memory/`, `api/`).
2. **The research** — a fine-tuning and evaluation study of grounded coaching (`eval/`, `training/`,
   write-ups in [`docs/experiments/`](./docs/experiments/)).

## Layout

```
engine/    Stockfish analysis, win-probability move scoring, PGN handling, game fetching
coach/     the facts block + grounded prompt, and the Ollama client
memory/    SQLite store of your games, motif tagging, profile/trends, background jobs
api/       FastAPI + server-rendered pages (no JavaScript, no build step)
eval/      research: grounding metric, claim checkers, LLM judge, held-out set, reports
training/  research: corpus assembly, distillation from a teacher model, QLoRA notebook
```

The product packages (`engine`, `coach`, `memory`, `api`) never import `training`, and use
`eval` for one thing only: the move extractor in `eval.grounding`, which checks that stored
coaching cited real moves.

## Setup

Requires Python 3.12 (system Python 3.14 has no ML wheels), Stockfish and Ollama.

```bash
brew install stockfish
uv venv --python 3.12
uv pip install -e '.[coach,api,dev]'

# The coach model. The fine-tune is built from training/qlora_8b_runpod.ipynb; without it,
# use the un-fine-tuned base, which scores the same judged quality:
ollama pull qwen3:8b
export COACH_MODEL=qwen3:8b
```

## Run the app

```bash
uvicorn api.app:app --reload     # then open http://127.0.0.1:8000 and enter a chess.com username
```

Sync fetches and analyzes your recent games in the background; the dashboard shows your recurring
mistakes, where in the game they happen, and whether you are improving; each game page lists its
mistakes and can generate coaching, with a note on whether every move it cited was real.

## Command line

```bash
python -m engine.fetch_data --user mshah509 --max 40          # chess.com games → data/raw/mshah509.pgn
python -m memory.store --user mshah509 data/raw/mshah509.pgn   # analyze + remember them
python -m memory.profile --user mshah509                       # what you keep getting wrong
python -m coach.coach game.pgn --user mshah509                 # coach one game against your history
python -m engine.report game.pgn --json report.json            # the raw engine report
```

Move quality is judged by the drop in the mover's **win probability**, so already-decided
positions and forced mates don't produce false blunders, and playing the engine's own top choice
always scores as best.

## Tests

CI runs bare `pytest` (not `python -m pytest`). Engine tests skip when Stockfish is missing, and
the live-model test skips when Ollama is not running.
