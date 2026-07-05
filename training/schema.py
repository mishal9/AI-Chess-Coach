"""The distillation record — one ``(analysis → coaching)`` training example.

A record is deliberately richer than the raw training row: it keeps the exact student
*prompt* (so training targets the input we actually deploy), the teacher *completion*
(the gold coaching), and *quality* metadata (grounding self-check, mistake count, ACPL)
so the dataset can be filtered before it ever reaches the fine-tune. ``dataset.py``
projects a record down to the minimal chat row a trainer consumes.

Bump :data:`SCHEMA_VERSION` whenever the record shape changes so older JSONL is easy to
spot and migrate — the dataset *is* the moat, and a silent schema drift would poison it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

SCHEMA_VERSION = 1


@dataclass
class DistillRecord:
    """One teacher-written coaching example, plus the input and metadata that made it."""

    source: dict          # {"pgn": str, "game_index": int, "coached_side": str}
    coached_side: str
    facts: str            # deterministic facts block (the body the model was grounded on)
    prompt: list[dict]    # the student's exact [system, user] chat messages
    completion: str       # teacher coaching — the gold target
    teacher: dict         # {"backend": str, "model": str}
    quality: dict = field(default_factory=dict)  # grounding self-check + difficulty signals
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "source": self.source,
            "coached_side": self.coached_side,
            "facts": self.facts,
            "prompt": self.prompt,
            "completion": self.completion,
            "teacher": self.teacher,
            "quality": self.quality,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DistillRecord":
        return cls(
            source=d["source"],
            coached_side=d["coached_side"],
            facts=d["facts"],
            prompt=d["prompt"],
            completion=d["completion"],
            teacher=d["teacher"],
            quality=d.get("quality", {}),
            schema_version=d.get("schema_version", SCHEMA_VERSION),
        )

    def to_chat_example(self) -> dict:
        """Project to the minimal training row: the deployed prompt + the gold answer.

        This is what a QLoRA trainer consumes — ``{"messages": [system, user, assistant]}``
        — with everything else (source, quality) dropped. Keeping this the single place the
        projection lives means the trainer never sees, and so can never train on, the
        teacher's identity or our internal metadata.
        """
        return {
            "messages": [
                *self.prompt,
                {"role": "assistant", "content": self.completion},
            ]
        }

    def source_key(self) -> str:
        """Stable per-game identity used to keep all of a game's positions in one split."""
        return f"{self.source.get('pgn', '?')}#{self.source.get('game_index', 0)}"
