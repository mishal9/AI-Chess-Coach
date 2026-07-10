"""Phase 3 — build the fine-tuning dataset (the project's moat).

Turns analyzed games into ``(engine analysis → coaching explanation)`` pairs by
**distillation**: a strong teacher model (Claude) writes gold-standard coaching for the
exact same facts block the small student model will see at inference. Those pairs become
a versioned train/val/test JSONL that Phase 4 QLoRA-fine-tunes Qwen on.

Modules:
    corpus   — assemble source games (CC0), guaranteed disjoint from ``eval/heldout/``.
    schema   — the on-disk record shape (:class:`~training.schema.DistillRecord`) + version.
    teacher  — Claude-as-teacher coaching generation (reuses ``eval.backends``).
    distill  — the pipeline: sources → Stockfish → teacher → grounding-checked JSONL.
    dataset  — JSONL I/O + deterministic, leakage-safe train/val/test splitting.
"""
