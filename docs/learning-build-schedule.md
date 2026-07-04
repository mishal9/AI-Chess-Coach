# 12-Week Interleaved Schedule — Build + Learn

**Goal:** finish the chess analyzer through a deployed, evaluated demo while learning AI/ML
fundamentals, AI engineering, and ML system design — and publishing as you go.

**Assumptions:** ~8–12 hrs/week (evenings + weekends). ~45–60 min/weekday theory; building
on weekends. Slipping a week is fine — protect the two non-negotiables below.

## Non-negotiables (the things that actually move the needle)
1. **The eval harness** (Weeks 5–6) — rubric + held-out games + baseline score. Rarest, highest-signal skill.
2. **A live deployed demo** (Week 12) — public URL, paste a game → coaching. Demonstrable > describable.
3. **Fine-tuned model that beats the baseline on your harness** (Week 9) — with a number you can quote.

## Always-on tracks (run every week, not as phases)
- **Theory:** ~45–60 min/weekday. Alternate Chip Huyen *AI Engineering* (priority) with fundamentals (pick ONE of Ng Specialization *or* CS229 — they overlap; don't do both).
- **Writing:** one Substack post per milestone (~6 total). Depth > volume; include tradeoffs and what went wrong.
- **Networking:** start Week 1. Identify Bloomberg AI/NLP teams; reach out steadily. Applications become the *result* of this, not a separate step.
- **Learn pull-based:** when the build raises a question, go pull that chapter. The project generates the questions; the books answer them.

---

## Weeks 1–2 — Finish Phase 1 + kickoff
- **Build:** Merge Phase 1 PR2. Emit the structured JSON analysis report. Validate on the Opera Game (confirm it flags the known blunder with correct cp-loss). Polish the CLI.
- **Theory:** Chip *AI Engineering* ch. 1–2 (foundation models, intro to evaluation). Begin fundamentals: linear/logistic regression (Ng C1 *or* CS229 L1–3), light.
- **Write:** Post #1 — *"Why I'm building an AI chess coach: the engine/LLM reliability split."* (You already have the notes + diagrams.)
- **Network:** List 5 people on Bloomberg AI/NLP teams to contact. Send 1.

## Weeks 3–4 — Phase 2: LLM coaching baseline (prompting)
- **Build:** Wire Phase-1 JSON → Qwen2.5-3B via Ollama with a coaching prompt. End-to-end "PGN in → coaching text out." Iterate on the prompt.
- **Theory:** Chip — prompt engineering + evaluation chapters (directly applicable right now). Fundamentals: classification.
- **Write:** Post #2 — *"Prompt-engineering a chess coach: the baseline fine-tuning must beat."*
- **Network:** Send 2–3 coffee-chat messages.

## Weeks 5–6 — Eval harness + transformer intuition
- **Build:** Build the **eval harness** — rubric (factual correctness vs. engine, clarity, actionability, identifies the *key* mistake), held-out games, score the prompted baseline. **This is the highest-signal piece of the whole project.**
- **Theory:** Karpathy **"Let's build GPT"** (transformers from scratch) — a weekend; understand attention from the inside. Chip — evaluation deep-dive.
- **Write:** Post #3 — *"How do you evaluate an LLM coach? Designing a rubric + harness."* (Rare, high-signal content.)
- **Network:** 1–2 coffee chats. Ask what their team actually values in a hire.

## Weeks 7–9 — Phase 3–4: Dataset + QLoRA fine-tune
- **Build:**
  - *Phase 3:* distillation dataset — a strong model writes high-quality coaching for many analyzed positions → versioned `(analysis → coaching)` JSONL (train/val/test).
  - *Phase 4:* QLoRA fine-tune Qwen2.5-3B on Colab T4 → merge → GGUF → run on Ollama. **Evaluate vs. baseline using your Week-5 harness.**
- **Theory:** Chip — fine-tuning chapter. Understand LoRA + quantization properly. Fundamentals: neural nets.
- **Write:** Post #4 — *"Fine-tuning a 3B model on a free GPU: QLoRA, and did it beat the baseline?"* (Include the metric — your strongest post.)
- **Network:** You now have an *evaluated, demoable* model. Start naming the AI-move goal in conversations.

## Weeks 10–11 — Phase 5: RAG / memory
- **Build:** Chroma per-user store; retrieve recurring weaknesses; personalize coaching. (Directly bridges to the future image-search project — same embeddings/retrieval skills.)
- **Theory:** Chip — RAG chapter; embeddings + retrieval. Start **ML system design** (Alex Xu, *ML System Design Interview*) — now relevant for interviews.
- **Write:** Post #5 — *"Making the coach remember: RAG over a player's game history."*
- **Network:** Begin informal internal-transfer conversations.

## Week 12 — Phase 6: Serving + ship
- **Build:** FastAPI + minimal web UI + Docker; deploy to a free tier. **Public URL:** paste a game → board + annotated mistakes + personalized coaching.
- **Theory:** ML system design — deployment, monitoring.
- **Write:** Post #6 — *"Shipping it: notebook → public URL"* + a capstone *"What I learned building an AI system end-to-end."*
- **Network:** Live demo + 6 posts + an evaluated fine-tuned model in hand. **Start actively applying/interviewing internally.** Ramp ML system-design interview drills.

---

## After Week 12
- **Image-search project** (embeddings / retrieval / IR-evaluation axis) — complements the chess project's LLM/fine-tuning axis; reuses the Week 10–11 retrieval skills.
- **Continued ML system-design interview prep** (Xu cases + mock interviews).
- **Higher-leverage in parallel if possible:** manufacture a small AI-building tool inside your day job — one shipped AI feature at Bloomberg outweighs the side projects for an internal move.

## Reality checks
- Timeline assumes ~8–12 hrs/week; treat dates as direction, not deadlines.
- If you fall behind, **protect the two non-negotiables** (eval harness, deployed demo) and cut scope elsewhere (e.g., simpler UI, smaller dataset).
- Don't let theory or writing become procrastination from building. Building is the primary output; everything else serves it.
