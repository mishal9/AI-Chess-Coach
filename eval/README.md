# Eval harness

**Why this exists (and why it's built before any fine-tuning):** it is the instrument
that lets us put a *number* on coaching quality. Phase 3/4 (dataset + QLoRA fine-tune)
only makes sense if the fine-tuned model beats the Phase-2 prompted baseline *on this
harness*. It is the highest-signal piece of the project.

## What we measure

Coaching quality along two kinds of axis:

1. **Grounding (deterministic, no LLM).** Did the coach only talk about moves that were
   actually in the engine facts it was given? This directly measures the Phase-2 finding
   that a small model confabulates moves when the facts are sparse. Cheap, fast, runs in
   CI. → `eval/grounding.py`.
2. **Rubric quality (LLM-as-judge).** The subjective axes an engine can't score:
   *factual correctness vs. the engine, clarity, actionability, and whether the coach
   identifies the single key mistake.* → `eval/rubric.py` + judge (PR2).

## Build roadmap (gradual PRs)

- **PR1 — grounding metric.** `eval/grounding.py`: extract the SAN moves a coaching text
  cites, diff against the moves present in the facts block, report hallucinated moves and
  a grounding score. Deterministic; unit-tested; no model required. **(merged)**
- **PR2 — rubric + LLM-as-judge.** `eval/rubric.py` (axes, 1-5 scale, validated
  `RubricScore`) + `eval/judge.py` (judge prompt, defensive JSON parsing, `judge_coaching`).
  Scores the subjective axes with a structured, parseable verdict. Judging is
  **provider-pluggable** via `eval/backends.py`: local Ollama by default (offline, the CI
  default), or a frontier judge (`anthropic_backend` / `gemini_backend`, behind the `eval`
  extra) with a one-argument swap — `judge_coaching(..., backend=...)`. **(this PR)**
- **PR3 — held-out set + runner.** A small, fixed set of held-out games (varied mistake
  profiles), an end-to-end runner that coaches each and aggregates grounding + rubric into
  a single baseline report (JSON + readable summary), and a CLI (`python -m eval.run`).

## Design notes

- The held-out set is **fixed and versioned** so scores are comparable across model
  changes. Never tune prompts against the held-out set — that's the whole point of holding
  it out.
- Grounding is computed against the *exact facts string* the model received (from
  `coach.prompts.format_report_facts`), not the raw report — grounding means "stayed within
  what it was told," so the allowed-move set is what was actually in the prompt.
