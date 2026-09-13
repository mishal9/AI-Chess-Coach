# Eval harness (research)

Measures coaching quality on a fixed held-out set, so a change of model, prompt or training
data can be compared on a number rather than an impression. The experiments it ran, and what
they found, are written up in [`docs/experiments/`](../docs/experiments/); this file only says
what each piece is.

## Instruments

| Module | Measures | Cost |
|---|---|---|
| `grounding.py` | fraction of moves cited in the coaching that appear in the facts block the model was given | free, deterministic |
| `claims.py` | role inversion ("you played" the engine's move), invented castling, and piece placement the game never had — by replaying the PGN | free, deterministic |
| `rubric.py` + `judge.py` | 1–5 LLM-judge scores: factual correctness, clarity, actionability, identifies key mistake | ~$0.40 per 29-game run |
| `backends.py` | pluggable judge/teacher: Ollama, Anthropic, Gemini (keys from a gitignored `.env`) | — |

## Workflow

```bash
python -m eval.run --coach-model qwen-coach-8b-v2 --judge anthropic   # coach + score the held-out set
python -m eval.run --coach-model qwen3:8b --no-judge                  # grounding + claims only, free
python -m eval.compare eval/reports/A.json eval/reports/B.json        # paired, per-bucket diff
```

`eval.compare` refuses to diff reports scored under different metric versions or judges, and
names the command that repairs them (`eval.rescore` for grounding, `eval.recheck` for claims).

## The held-out set

`heldout/` holds 29 Lichess CC0 games in six mistake-profile buckets (`clean_draw`, `slow_loss`,
`inaccuracies`, `two_mistakes`, `one_blunder`, `multi_blunder`), built by `expand_heldout.py`
and guaranteed disjoint from the training corpus by game id **and** movetext hash. Never tune a
prompt against it.

## Where things stand

Headline results (29 games, `claude-opus-4-8` judge), from
[`2026-08-14-prompted-8b-control.md`](../docs/experiments/2026-08-14-prompted-8b-control.md):

| Coach | grounding | judged factual | overall |
|---|---|---|---|
| prompted `qwen3:8b` | 0.923 | 3.72 | 4.17 |
| `qwen-coach-8b-v2` (QLoRA on distilled rows) | 0.965 | 3.72 | 4.14 |
| teacher (`claude-opus-4-8`, corpus games) | — | 4.97 | 4.85 |

Fine-tuning bought citation hygiene, not judged quality. The grounding metric itself was audited
and found wrong in both directions — see
[`2026-08-11-grounding-metric-audit.md`](../docs/experiments/2026-08-11-grounding-metric-audit.md).
