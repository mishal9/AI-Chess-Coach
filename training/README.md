# Training (research)

Builds an `(engine facts → coaching)` dataset by distillation from a strong teacher model, and
fine-tunes a small local coach on it. Results are in
[`docs/experiments/`](../docs/experiments/); in short, the fine-tune matched its un-fine-tuned
base on judged quality and improved citation hygiene.

## Pipeline

```
training.corpus    fetch CC0 games → drop any that collide with eval/heldout → data/games/
  training.distill   Stockfish → facts block → Claude teacher → grounding self-check → raw JSONL
    training.dataset   grounding gate → deterministic, per-game train/val/test split
      training/datasets/<version>/          committed: the teacher calls are not cheaply reproducible
        qlora_8b_runpod.ipynb               QLoRA on Qwen3-8B → merge → GGUF → `ollama create`
```

```bash
python -m training.corpus --max 40                            # default rating-spanning roster
python -m training.distill --sources data/games/manifest.json --teacher anthropic \
    --out data/distill/raw.jsonl --max-teacher-calls 200       # spend guard
python -m training.dataset --in data/distill/raw.jsonl --out-dir training/datasets/vN \
    --min-grounding 1.0 --as-chat
```

## Guardrails

- The teacher sees the student's byte-identical facts block, so every row is a faithful
  `deployed prompt → gold answer` pair.
- `training.distill` refuses `eval/heldout/` sources, and `training.corpus` drops any game that
  matches a held-out game by id or by movetext hash.
- The split hashes a per-game key, so every position from one game lands in the same split and
  re-runs reproduce it exactly.

## Dataset versions

| Version | Rows | Shape |
|---|---|---|
| `v1` | 82 / 9 / 13 | one coaching row per whole game |
| `v2` | 319 / 34 / 50 | whole-game rows plus one row per critical position |
| `v2-game-only`, `v2-position-only` | manifests only | ablation arms |

The ablation found v2's gain came from row *shape*, not row count.
