"""LLM coaching layer.

Turns the objective engine report from :mod:`engine.analyzer` into natural-language
coaching: a strictly grounded facts block and system prompt (:mod:`coach.prompts`), sent to
a local Ollama model (:mod:`coach.client`).
"""
