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
- **PR3 — held-out set + runner.** `eval/heldout/` (6 fixed Lichess games with varied
  mistake profiles + `manifest.json`) and `eval/run.py` (`python -m eval.run`): coaches
  each game, scores grounding + rubric, aggregates into a baseline report (JSON under
  `eval/reports/` + readable summary). Coach and judge models are both selectable
  (`--coach-model`, `--judge {ollama,anthropic,gemini}`); `--max-judge-calls` is a spend
  guard; `--no-judge` runs grounding only (free/offline). **(this PR)**

## Baseline (as of 2026-07-04)

Phase-2 prompted coach (`qwen2.5:3b-instruct`) judged by `claude-opus-4-8` over the 6
held-out games — the number Phase 3/4 must beat (`eval/reports/baseline_2026-07-04.json`):

- Grounding mean **0.76**, fully grounded **50%**, worst move identified **67%**
- Rubric (1-5): factual **2.33**, clarity **3.50**, actionability **2.50**,
  identifies-key-mistake **3.83**, **overall 3.04**

Low factual-correctness is the hallucination problem quantified — the primary target.

## Design notes

- The held-out set is **fixed and versioned** so scores are comparable across model
  changes. Never tune prompts against the held-out set — that's the whole point of holding
  it out.
- Grounding is computed against the *exact facts string* the model received (from
  `coach.prompts.format_report_facts`), not the raw report — grounding means "stayed within
  what it was told," so the allowed-move set is what was actually in the prompt.
