# Phase 3 — the fine-tuning dataset (distillation)

This package builds the `(engine analysis → coaching)` dataset that Phase 4 QLoRA-fine-tunes
Qwen2.5-3B on. It **is the project's moat**: the eval harness (`eval/`) already proved the
prompted 3B baseline hallucinates (factual **2.33 / 5**, grounding **0.76** on the held-out
set — `eval/reports/baseline_2026-07-04.json`). Distillation is how we teach it not to.

## The idea

A strong **teacher** (Claude) writes gold coaching for the *exact same facts block* the
small **student** sees at inference — same grounding rules, same input — so every training
pair is a faithful `deployed-prompt → gold-answer` mapping. Fine-tuning transfers the
teacher's quality onto the standard prompt. Teacher outputs are **grounding-self-checked**
(reusing `eval.grounding`) and anything that invented a move is dropped before it can teach
the student to hallucinate.

## Pipeline

```
training.corpus              fetch CC0 games → drop any that collide with eval/heldout → data/games/
  └─ training.distill        Stockfish → facts → Claude teacher → grounding check → raw JSONL
       └─ training.dataset   filter (grounding gate) → deterministic train/val/test split
            └─ training/datasets/<version>/{train,val,test}.jsonl  +  manifest.json
                 └─ Phase 4: QLoRA on Colab → GGUF → re-run `python -m eval.run`
```

### 0. Assemble a corpus
```bash
python -m training.corpus \
  --user DrNykterstein --user Sharkfang \        # fetch CC0 game exports from Lichess
  --max 40                                        # (or --input some.pgn to reuse local PGNs)
```
Fetches public games, then **drops every game that collides with `eval/heldout/`** — matched
by Lichess `GameId` *and* a normalized-movetext hash, so nothing leaks the scoreboard. Writes
`data/games/corpus.pgn` + a distill-ready `manifest.json`.

### 1. Distill
```bash
python -m training.distill \
  --sources data/games/manifest.json \        # or a directory of .pgn files
  --teacher anthropic \                        # Claude via eval.backends (needs .env key)
  --out data/distill/raw.jsonl \
  --max-teacher-calls 200                       # spend guard
```
Emits one `DistillRecord` (`training/schema.py`) per game: the student prompt, the teacher
completion, and `quality` metadata (grounding score, mistake count, ACPL).

### 2. Build splits
```bash
python -m training.dataset \
  --in data/distill/raw.jsonl \
  --out-dir training/datasets/v1 \
  --min-grounding 1.0 \                         # drop teacher outputs that hallucinated
  --as-chat                                     # {messages:[system,user,assistant]} training rows
```
The split is **deterministic and leakage-safe**: hashed by per-game key, so a game never
straddles train/test and re-runs reproduce the identical split (see `assign_split`).

## Guardrails / conventions

- **Never distill on `eval/heldout/`** — that leaks the scoreboard. `load_sources` refuses it.
- Raw generations (`data/distill/`) and built splits (`training/datasets/`) are gitignored;
  they're reproducible artifacts. The *deliverable* is a versioned, checked-in `manifest.json`
  per dataset version once we're happy with one.
- Teacher backends are the same pluggable `eval.backends` (Claude default). Keys load from the
  gitignored `.env`. Teacher/analysis are injectable, so the logic is fully unit-tested offline.

## Dataset versions

Staged on purpose so we can **measure** what richer data buys us (see `PLAN.md` Phase 3):

- **v1 — one row per game (current target).** One coaching paragraph per whole game; simplest
  path to a working fine-tune + eval loop. `distill.build_record` already emits exactly one
  record per game.
- **v2 — one row per critical position (revisit for a second fine-tune).** A separate example
  per flagged moment, multiplying the corpus into hundreds of rows. Only *then* does the
  leakage-safe per-game split (`assign_split`) become load-bearing. Compare `eval.run` on the
  same held-out set to quantify the v1→v2 gain.

## Status

- [x] Scaffold: schema, teacher, distill pipeline, dataset splitter, tests.
- [x] Corpus assembler (`training.corpus`): fetch CC0 games, guaranteed disjoint from held-out.
- [x] Assemble the corpus: 137 games, 843–3284 Elo, disjoint from the 29-game held-out set.
- [x] **v1 distilled** (teacher = `claude-opus-4-8`, depth 15): 137 games → 104 strictly-grounded
      (76% teacher pass-rate at grounding 1.0; 33 dropped for naming a move not in the facts)
      → `training/datasets/v1` = train 82 / val 9 / test 13 (chat format).
- [ ] Phase 4: QLoRA fine-tune on v1 — notebook `training/qlora_v1_colab.ipynb` (Colab T4:
      4-bit NF4 base + LoRA r=16 → SFT → merge → GGUF). Run it, then `eval.run` on the 29-game
      set vs baseline (beat factual 2.90 / overall 3.38; watch clean_draw grounding vs 0.38).
- [ ] **v2**: per-position distillation → second fine-tune → report the v1→v2 eval delta.
- [ ] First distillation run + `v1` dataset; eyeball teacher quality and grounding pass-rate.
- [ ] Phase 4: QLoRA fine-tune on Colab, re-run `eval.run`, beat **3.04 / factual 2.33**.
