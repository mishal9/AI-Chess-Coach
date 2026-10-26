# 12-week interleaved schedule: build and learn

> **Historical plan, kept for the record (note added 2026-10-08).** The build steps below were
> later changed: the coach is Qwen3-8B (QLoRA on RunPod, not Qwen2.5-3B on Colab), memory is
> SQLite with rule-based motif tags (no Chroma), and the app runs locally (no public demo yet).
> For the current system see [`learning-notes.md`](./learning-notes.md) and [`PLAN.md`](../PLAN.md).

**Goal:** finish the chess analyzer through a deployed, evaluated demo while learning AI/ML
fundamentals, AI engineering, and ML system design, and publishing as you go.

**Assumptions:** ~8–12 hrs/week (evenings + weekends). ~45–60 min/weekday theory; building
on weekends. Slipping a week is fine; protect the two non-negotiables below.

## Non-negotiables
1. **The eval harness** (Weeks 5–6): rubric, held-out games and a baseline score. Few candidates can show one.
2. **A live deployed demo** (Week 12): a public URL where you paste a game and get coaching.
3. **Fine-tuned model that beats the baseline on your harness** (Week 9), with a number you can quote.

## Always-on tracks (run every week, not as phases)
- **Theory:** ~45–60 min/weekday. Alternate Chip Huyen *AI Engineering* (priority) with fundamentals (pick one of the Ng Specialization or CS229; they overlap, so don't do both).
- **Writing:** one Substack post per milestone (~6 total). Include tradeoffs and what went wrong.
- **Networking:** start Week 1. Identify Bloomberg AI/NLP teams; reach out steadily. Applications become the *result* of this, not a separate step.
- **Learn pull-based:** when the build raises a question, go pull that chapter. The project generates the questions; the books answer them.

---

## Weeks 1–2: finish Phase 1, kickoff
- **Build:** Merge Phase 1 PR2. Emit the structured JSON analysis report. Validate on the Opera Game (confirm it flags the known blunder with correct cp-loss). Polish the CLI.
- **Theory:** Chip *AI Engineering* ch. 1–2 (foundation models, intro to evaluation). Begin fundamentals: linear/logistic regression (Ng C1 *or* CS229 L1–3), light.
- **Write:** Post #1, *"Why I'm building an AI chess coach: the engine/LLM reliability split."* (You already have the notes + diagrams.)
- **Network:** List 5 people on Bloomberg AI/NLP teams to contact. Send 1.

## Weeks 3–4: Phase 2, LLM coaching baseline (prompting)
- **Build:** Wire Phase-1 JSON → Qwen2.5-3B via Ollama with a coaching prompt. End-to-end "PGN in → coaching text out." Iterate on the prompt.
- **Theory:** Chip's prompt engineering and evaluation chapters (they apply to this step). Fundamentals: classification.
- **Write:** Post #2, *"Prompt-engineering a chess coach: the baseline fine-tuning must beat."*
- **Network:** Send 2–3 coffee-chat messages.

## Weeks 5–6: eval harness, transformer intuition
- **Build:** Build the **eval harness**: a rubric (factual correctness vs. engine, clarity, actionability, identifies the *key* mistake), held-out games, and a score for the prompted baseline. Every later comparison depends on it.
- **Theory:** Karpathy's **"Let's build GPT"** (transformers from scratch), one weekend, to understand attention from the inside. Chip's evaluation chapter in depth.
- **Write:** Post #3, *"How do you evaluate an LLM coach? Designing a rubric + harness."* Few people write about this.
- **Network:** 1–2 coffee chats. Ask what their team actually values in a hire.

## Weeks 7–9: Phases 3–4, dataset and QLoRA fine-tune
- **Build:**
  - *Phase 3:* distillation dataset. A strong model writes high-quality coaching for many analyzed positions → versioned `(analysis → coaching)` JSONL (train/val/test).
  - *Phase 4:* QLoRA fine-tune Qwen2.5-3B on Colab T4 → merge → GGUF → run on Ollama. **Evaluate vs. baseline using your Week-5 harness.**
- **Theory:** Chip's fine-tuning chapter. Learn how LoRA and quantization work. Fundamentals: neural nets.
- **Write:** Post #4, *"Fine-tuning a 3B model on a free GPU: QLoRA, and did it beat the baseline?"* Include the metric.
- **Network:** You now have an *evaluated, demoable* model. Start naming the AI-move goal in conversations.

## Weeks 10–11: Phase 5, RAG and memory
- **Build:** Chroma per-user store; retrieve recurring weaknesses; personalize coaching. (The future image-search project uses the same embedding and retrieval skills.)
- **Theory:** Chip's RAG chapter; embeddings and retrieval. Start **ML system design** (Alex Xu, *ML System Design Interview*) for interviews.
- **Write:** Post #5, *"Making the coach remember: RAG over a player's game history."*
- **Network:** Begin informal internal-transfer conversations.

## Week 12: Phase 6, serving and shipping
- **Build:** FastAPI + minimal web UI + Docker; deploy to a free tier. **Public URL:** paste a game → board + annotated mistakes + personalized coaching.
- **Theory:** ML system design: deployment, monitoring.
- **Write:** Post #6, *"Shipping it: notebook → public URL"*, and a capstone *"What I learned building an AI system end-to-end."*
- **Network:** Live demo + 6 posts + an evaluated fine-tuned model in hand. **Start actively applying/interviewing internally.** Ramp ML system-design interview drills.

---

## After Week 12
- **Image-search project** (embeddings, retrieval, IR evaluation). It covers what the chess project's LLM and fine-tuning work doesn't, and reuses the Week 10–11 retrieval skills.
- **Continued ML system-design interview prep** (Xu cases + mock interviews).
- **In parallel, if possible:** build a small AI tool inside your day job. For an internal move, one shipped AI feature at Bloomberg counts for more than the side projects.

## Reality checks
- Timeline assumes ~8–12 hrs/week; treat dates as direction, not deadlines.
- If you fall behind, **protect the two non-negotiables** (eval harness, deployed demo) and cut scope elsewhere (e.g., simpler UI, smaller dataset).
- Don't let theory or writing become procrastination from building. Building is the primary output.
