# Chess Analyzer: AI Chess Coach

Syncs your chess.com games, finds the mistakes you keep making, and coaches you on them.
Stockfish decides what is true; a local LLM explains it; a SQLite memory of your past games
lets the coach say "this is the fourth time" and mean it.

The project has two outputs, planned in [`PLAN.md`](./PLAN.md):

1. **The app:** a personal coach over your own game history (`engine/`, `coach/`, `memory/`, `api/`).
2. **The research:** a fine-tuning and evaluation study of grounded coaching (`eval/`, `training/`,
   write-ups in [`docs/experiments/`](./docs/experiments/)).

**Research status (11 Oct 2026):** the DeepSeek-V4 Pro teacher passed its gate on the 91-game
held-out set (factual 4.74), and its training data is finished: a 2,000-game Lichess corpus
(Sep 2023 – Aug 2026) and eight registered training sets. Next is the pre-registered game-only
vs mixed student comparison (24 Qwen3-8B QLoRA runs). See
[`docs/experiments/README.md`](./docs/experiments/README.md) for every result and the
current resume point.

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

## Research commands

Needs the `eval` extra (`uv pip install -e '.[eval]'`) and API keys in a git-ignored `.env`:
`DEEPSEEK_API_KEY` (teacher), `ANTHROPIC_API_KEY` (Opus judge), `GEMINI_API_KEY` (second judge).
Each stage's exact invocation, seeds and costs are in its write-up in
[`docs/experiments/`](./docs/experiments/); these are the commands behind the current data.

```bash
# 1. Training corpus: 2,000 games from the Lichess database export, balanced by rating band and
#    time control, disjoint from the held-out games and players → data/games/
python -m training.corpus --from-db 2023-09:2026-08 --canonical-seed 0

# 2. Teacher rows from DeepSeek (game rows, then v5 position rows); --resume continues a cut-off run
python -m training.distill --sources data/games/manifest.json --teacher deepseek \
    --teacher-thinking disabled --workers 8 --retries 1 --positions-per-game 4 \
    --resume --out data/distill/raw_deepseek.jsonl --max-teacher-calls 20000
python -m training.distill --sources data/games/<batch>.json --teacher deepseek \
    --teacher-thinking disabled --workers 8 --retries 1 --positions-per-game 4 \
    --no-game-rows --resume --out data/distill/raw_deepseek_pos_v5.jsonl

# 3. Quality control, then keep position rows with a clear-cut tactic
python -m training.qc data/distill/raw_deepseek.jsonl --passed-out data/distill/deepseek_qc.jsonl
python -m training.qc data/distill/raw_deepseek_pos_v5.jsonl \
    --passed-out data/distill/deepseek_pos_v5_qc.jsonl
python -m training.clear_cut data/distill/deepseek_pos_v5_qc.jsonl \
    --out data/distill/deepseek_pos_v5_clear.jsonl

# 4. Spot-check rows with the Opus judge (--batch: Message Batches API, half price)
python -m training.judge_rows data/distill/deepseek_pos_v5_clear.jsonl --n 100 --seed 0 \
    --out <verdicts>.jsonl --batch

# 5. The registered training sets: game-only (G) and mixed 1:2 (M), split 90/10 by game
python -m training.sweep --game data/distill/deepseek_qc.jsonl \
    --position data/distill/deepseek_pos_v5_clear.jsonl \
    --position data/distill/deepseek_pos_paired_plain_clear.jsonl \
    --arm G:400,1000,1700 --arm M:400,1000,1700,2500,all \
    --out-root training/datasets --prefix sweep-v5

# 6. Fine-tune: training/qlora_8b_runpod.ipynb on a Runpod GPU (Qwen3-8B QLoRA → GGUF),
#    then register the GGUF in Ollama with a Modelfile copied from models/Modelfile.qwen-coach-8b-v2

# 7. Evaluate a coach on the 91 held-out games (depth 18): grounding and claims first, judges after
python -m eval.run --coach-model <ollama model> --no-judge --out eval/reports/<run>.json --resume
python -m eval.rejudge eval/reports/<run>.json --judge anthropic --batch --out eval/reports/<run>__opus.json
python -m eval.rejudge eval/reports/<run>.json --judge gemini --out eval/reports/<run>__gemini.json

# 8. Compare runs: per-axis diff, equivalence test (TOST), and judge agreement
python -m eval.compare <baseline>.json <candidate>.json
python -m eval.equivalence <baseline>.json <candidate>.json --delta 0.30
python -m eval.equivalence --agreement <run>__opus.json <run>__gemini.json
```

Rows, games and datasets under `data/` and `training/datasets/` are git-ignored; reports in
`eval/reports/` and dataset manifests are committed.

## Tests

CI runs bare `pytest` (not `python -m pytest`). Engine tests skip when Stockfish is missing, and
the live-model test skips when Ollama is not running.
