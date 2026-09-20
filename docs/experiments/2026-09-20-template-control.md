# Control: a coach with no model in it

Date: 2026-09-20 · Cost: 29 Opus calls, 29 Gemini calls, no GPU, no training.

## Question

Every arm so far is an LLM handed the same Stockfish facts block. Nothing tested whether an LLM
adds anything beyond those facts. `eval/template_coach.py` turns the same facts into coaching with
string formatting alone: it names only the moves the facts block lists, states no motif, tactic or
evaluation the block does not, and cannot hallucinate. It is the floor the three LLM arms are
measured against.

## Result (29 held-out games, same rubric, same facts)

Opus judge (`claude-opus-4-8`):

| Arm | factual | clarity | actionability | key mistake | overall |
|---|---|---|---|---|---|
| **template** | **5.00** | 4.17 | **2.83** | 4.90 | **4.22** |
| prompted `qwen3:8b` | 3.72 | 4.41 | 3.72 | 4.83 | 4.17 |
| `qwen-coach-8b-v2` | 3.72 | 4.45 | 3.59 | 4.79 | 4.14 |

Second judge (`gemini-3.1-pro-preview`, stored text re-judged by `eval.rejudge`):

| Arm | factual | clarity | actionability | key mistake | overall |
|---|---|---|---|---|---|
| **template** | **5.00** | 4.41 | **2.31** | 5.00 | **4.18** |
| prompted `qwen3:8b` | 2.86 | 4.52 | 3.03 | 5.00 | 3.85 |
| `qwen-coach-8b-v2` | 3.28 | 4.34 | 3.24 | 4.79 | 3.91 |

Deterministic: grounding 1.00 and claims 1.00 on 29/29 games (by construction).

## What it says

1. **Both 8B arms are less factual than the script.** 5.00 against 3.72 (Opus) and 2.86 / 3.28
   (Gemini). The 8B models' factual deficit is invented content the facts do not contain.
2. **The LLM's contribution is actionability, not correctness.** The template is 0.9 lower on
   actionability under Opus and 0.7 to 0.9 lower under Gemini. Clarity is within about 0.3 either
   way, and the template is above the fine-tune on clarity under Gemini.
3. **On the overall mean the template ties or beats both 8B arms** under both judges. The overall
   is the mean of the four axes, so the factual axis carries it. That reads as "a script matches
   an 8B model on this rubric", and the rubric weights factual as heavily as it does everything
   else, so state that weighting in the paper.
4. **Judges agree on the ranking, not the level.** On identical text: clarity r = 0.54,
   actionability r = 0.20. Factual and key-mistake have no variance to correlate, since nearly
   every game scores 5 (a ceiling effect, `nan`).

## Threats

- **Circular by construction on factual.** The judge sees the facts block, and the template is a
  near-verbatim rendering of it. A 5.00 factual score measures fidelity to the facts, which is
  the template's whole design. It says nothing about coaching quality beyond that.
- **Rubric ceiling.** Factual and key-mistake are 5 for almost every template game, so those two
  axes cannot separate the template from a better coach. Only clarity and actionability can.
- **The template's text is formulaic.** A judge may grade it on its rhythm as much as its content.
  Human raters are the check, and are not yet in.
- **Weaker second judge earlier.** A first Gemini pass used the default `gemini-3.6-flash`. It was
  discarded in favour of `gemini-3.1-pro-preview`, the judge the other arms were scored with.
- **`identifies_worst_move` (72%) is a metric artefact.** It checks the game's worst move for
  either side, but the facts block lists only the coached side's mistakes. 5 of 8 misses are an
  opponent's move that no coach could cite. Do not report it.

## A defect found on the way

`eval.rejudge` refreshed `rubric_<axis>` / `rubric_overall` in a re-judged report's `aggregate`,
while `eval.run` and readers use `rubric_axis_means` / `rubric_overall_mean`. The nested block
therefore kept the first judge's means beside the second judge's per-game scores. `_reaggregate`
now rebuilds the summary with `eval.run.aggregate`. The older `__gemini31pro.json` reports in
`eval/reports/` predate the fix and still carry the stale nested block; their per-game rubrics
are correct, and readers should recompute from `games`.

## Reproduce

```bash
python -m eval.run --coach-model template --judge anthropic --out eval/reports/template_2026-09-20__opus.json
python -m eval.rejudge eval/reports/template_2026-09-20__opus.json --judge gemini \
    --judge-model gemini-3.1-pro-preview --out eval/reports/template_2026-09-20__gemini31pro.json
python -m eval.equivalence --agreement eval/reports/template_2026-09-20__opus.json \
    eval/reports/template_2026-09-20__gemini31pro.json
```
