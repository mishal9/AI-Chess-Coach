# Lessons learned, and a pre-flight checklist for the next research project

Written 2026-09-20, while Goal 1 (the paper) is still open. Every item below is something that
happened in this repo, with the file or number that shows it. The second half turns each lesson
into a check that runs *before* the money or the time is spent.

Most of what went wrong here was caught by the project's own process, and each catch became a result.
Two things were not: the teacher licence, and the human-rating protocol. Those are the ones to read twice.

## 1. What happened, and the lesson

### Caught late, and expensive

| # | What happened | Evidence | Lesson |
|---|---|---|---|
| L1 | **The teacher's terms were never read.** Opus outputs were used as training targets for a fine-tune. Anthropic prohibits using Outputs "as training targets for models" without written permission. Found on 20 Sep, after the fine-tune, the eval and the paper outline. | Help Center, updated 16 Mar 2026; Commercial Terms §D.4; nothing in `docs/` mentions it | Read the terms of every model, dataset and API *before* it enters the pipeline. A licence problem found after training can invalidate the training. |
| L2 | **The cheap metric was wrong, and it was also a training filter.** The grounding metric was saturated (18/29 games at the ceiling), blind to inverted claims, and over-fired on bare square names (84–94% of flags). r(grounding, judged factual) was only +0.39. It discarded 64/64 already-paid teacher rows. | `2026-08-11-grounding-metric-audit.md` | Validate a metric against ground truth *before* using it to gate models or filter data. A metric that decides what gets trained on is part of the method. |
| L3 | **Controls came after the treatment.** v1 (2026-08-08) and v2 (08-10) were compared to a prompted 3B, which confounded model size with fine-tuning. The prompted-8B control arrived on 08-14. The template control (no model at all) arrived on 09-20. Each control changed the conclusion. | `2026-08-13-gates-re-derived.md`, `2026-08-14-prompted-8b-control.md`, `2026-09-20-template-control.md` | List the control arms *before* the first training run: same base, no tuning; and a no-model floor. A result with no floor cannot be placed on a scale. |
| L4 | **One judge, and it was the teacher.** Opus generated the training data and judged the result. A second judge reversed the headline: the "tie" became +0.41 factual for the fine-tune (not significant), and the two judges disagreed on how much invented narrative should cost. | `2026-09-13-gate3-cross-judge.md` | Plan a second judge and a human sample at the start. The judge must not be the teacher. |
| L5 | **Human ratings are the long pole and were left to last.** The tooling, the blinded sheet and the agreement code are merged. `ratings.csv` still has 0 ratings. Gate 3 made these ratings the tiebreak between two judges. | `eval/human/round1/ratings.csv`; `PLAN.md` N4 | Recruit raters and write the protocol in week one. It depends on people, not compute, so it cannot be compressed at the end. |

### Caught by the process, and worth keeping

| # | What happened | Lesson |
|---|---|---|
| L6 | **A plan built on a misdiagnosis.** Iteration 3 planned more position rows; reading the judge rationales showed the failure was role confusion, not coverage. | Read raw outputs, not aggregates, before spending on a fix. |
| L7 | **`eval.compare` inverted a delta by differencing two metric versions.** | Version-stamp every metric and make comparison tools refuse to mix versions. `metric_versions` now does. |
| L8 | **Derived data went stale.** `eval.rejudge` refreshed different `aggregate` keys from the ones readers used, so a re-judged report showed the first judge's means beside the second judge's games. | One definition of every summary, and derive it from the per-item records, never a parallel copy. |
| L9 | **A metric was named for something it does not measure.** `identifies_worst_move` scores the game's worst move for either side, but the facts block lists only the coached side's. 5 of the template's 8 misses were moves no coach could cite. | Name a metric for what it computes. Check the ceiling by asking what a perfect coach would score. |
| L10 | **Ceiling effects hide differences.** Factual and key-mistake are 5 for almost every template game under both judges, so agreement is `nan`: there is no variance to correlate. | Check each rubric axis for range before relying on it. An axis everyone maxes out cannot separate arms. |
| L11 | **Scope crept.** `PLAN.md` says it plainly: "Everything that slipped on this project slipped by adding 'one more thing worth auditing'". The TMLR date and the evidence freeze both slipped. | One goal at a time, a written "not in this goal" list, and a dated freeze. |
| L12 | **Dependencies were implied that did not exist.** The plan sequenced human ratings and the template fine-tune behind the licence answer. Neither depends on it. Rating a fine-tune that might not survive the licence answer would also have wasted the ratings. | For each step, ask "what does this really need?" Separate arms that are stable from arms that might change, and rate the stable ones first. |
| L13 | **Assessments were written from a stale summary.** An outside review critiqued a one-paragraph description of the project that omitted the controls, the audit and the second judge, and reported gaps that were already closed. | Keep one living status document and paste that, not a from-memory summary. |
| L14 | **Provider availability changes.** Gemini 2.5 refuses new keys; the Opus judge may be next. | Store every raw output and every judge verdict, so a number can be re-derived without the API. This repo did, and it is why the template arm and the re-judging were cheap. |

## 2. Habits that worked, and should carry over

- One experiment note per run: hypothesis, data lineage, exact config, results, threats, reproduction commands.
- Resumable runs with a sidecar file that refuses to mix a different coach or judge.
- A spend guard on judge calls (`--max-judge-calls`).
- Injectable fakes for the coach and the judge, so aggregation and reporting are unit-tested with no model.
- Holding the held-out set disjoint by game id and by movetext hash, and never tuning against it.
- Reporting a null as a null, with an equivalence test that says which kind (`eval.equivalence`).
- Writing down the conclusion a result reverses.

## 3. Pre-flight checklist for the next project

Run this before the first paid call or training run. Each line names the lesson it comes from.

### Week 0: rights and claims
- [ ] Read the terms for every model, API and dataset. Record what each allows: training on outputs, redistribution, research use, commercial use. Save the URL and date. (L1)
- [ ] If the terms are unclear or restrictive, ask for written permission now, or choose a permissive alternative, before any output enters training data. (L1)
- [ ] Write the one-sentence claim the paper will make, and the result that would kill it. (L3, L4)
- [ ] Name the venue and the date, plus the freeze date, and the things that are out of scope. (L11)

### Week 0: evaluation design
- [ ] List the control arms: the untuned base with the same prompt, a no-model floor, and any teacher upper bound. Build the floor first because it is cheap. (L3)
- [ ] Choose the judge so it is not the teacher, and add a second judge from a different family. (L4)
- [ ] Recruit at least two human raters, state their strength, write the rubric, and schedule the rating session. (L5)
- [ ] Decide which arms are stable. Rate stable arms first; hold any arm that depends on an open question. (L12)
- [ ] Estimate power. State the smallest effect n can detect, and plan an equivalence test for a null. (L4, L10)

### Before trusting a metric
- [ ] Validate it against ground truth or a human sample. Report its correlation, its ceiling and its false-positive rate. (L2)
- [ ] Ask what a perfect system scores. If a system that copies the input scores 100%, the metric cannot separate good from copied. (L9, L10)
- [ ] Check every rubric axis for variance. Drop or redesign axes that everyone maxes out. (L10)
- [ ] Give the metric a version number and stamp it in every report. Make comparison tools refuse to mix versions. (L7)

### Before any training run
- [ ] Read 20 raw outputs from the current best model. Write down what is actually failing. (L6)
- [ ] Confirm the data filter is a validated metric, not a first draft. Count what it discards. (L2)
- [ ] Confirm the held-out set is disjoint by id and by content hash. (§2)

### While running
- [ ] Store every raw output and every judge verdict. (L14)
- [ ] Derive every summary from per-item records, with one definition. (L8)
- [ ] Add one new experiment at a time and log it with its hypothesis and threats. New ideas go on a "later" list. (L11)
- [ ] Update the living status document when something merges, so any outside review starts from the truth. (L13)

### Before writing
- [ ] Freeze the evidence with a tag. No new experiments after it. (L11)
- [ ] State every disclosure the paper needs: the teacher and its permission, judge strength and family, rater count and strength, n, the stated bound.
- [ ] Do not omit or rename a model that produced training data. It is a core part of the method, and the repo, the reports and the history already record it.
- [ ] Write the three reviews you fear, and answer each in the text.

## 4. One sentence for each

1. **Read the terms before the pipeline.**
2. **Validate the metric before it gates anything.**
3. **Build the floor before the fine-tune.**
4. **The judge is not the teacher, and humans start in week one.**
5. **One goal at a time, with a freeze date.**
