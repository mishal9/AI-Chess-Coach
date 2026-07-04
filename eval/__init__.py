"""Evaluation harness (Phase 3, Weeks 5-6).

Measures coaching quality so a later fine-tuned model can be compared against the
Phase-2 prompted baseline. Two axes: deterministic *grounding* (did the coach only cite
moves it was actually given?) and, later, an LLM-judged *rubric* for the subjective
qualities. See ``eval/README.md`` for the design and the PR roadmap.
"""
