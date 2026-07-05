"""Phase 3 — build the fine-tuning dataset (the project's moat).

The dataset is a versioned train/val/test JSONL of ``(engine analysis → coaching)`` pairs
that Phase 4 QLoRA-fine-tunes Qwen on. This first slice is the **data layer** — the record
shape and how records are filtered and split; the generation pipeline that fills it in
(``teacher``, ``distill``) lands next.

Modules:
    schema   — the on-disk record shape (:class:`~training.schema.DistillRecord`) + version.
    dataset  — JSONL I/O + deterministic, leakage-safe train/val/test splitting.
"""
