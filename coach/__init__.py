"""LLM coaching layer (Phase 2).

Turns the objective engine report from :mod:`engine.analyzer` into natural-language
coaching, using a *prompted* base instruct model (no fine-tuning yet). This baseline
is the thing a later fine-tuned model must beat to justify itself.
"""
