# Position rows with the evaluation in words, judged on a fresh sample

**Status:** pre-registered 8 Oct 2026, before any row was generated. Code on branch
`feat/position-facts-board`. Follows `2026-10-07-position-facts-board.md`, whose
spot-check failed (factual 4.38, confirmed errors 10 of 133 = 7.5%).

## Why

The board fixed the error it was added for: only 3 of the 10 confirmed errors misplace or
misdescribe a piece, against all 8 before. Half of the 10 (#397, #590, #666, #1053,
#1092) are a new kind: the row tells a student who was losing that they "were already
better" or "clearly winning". The facts block was right. It said "(in pawns; + favours
you)" and gave −3.1, and the teacher ignored the sign. That line was added in pilot 3,
after the pilots were read by hand.

## The change

1. **The evaluation in words.** `coach.prompts._eval_text` now writes "with the preferred
   move, you are worse by about 3.1 pawns; after your move, you are worse by about 8.9
   pawns". Under 0.3 pawns either way is "the position is about level". Mates are "you have
   a forced mate" / "the opponent has a forced mate". `POSITION_SYSTEM_PROMPT` adds one
   rule: say the student was better, worse or level only as the evaluation states it.
2. **A QC check for the sign.** `eval.claims.check_eval_sign` reads the evaluation line from
   the row's own facts (both the words form and the earlier signed form). It flags a row
   that calls the student better, winning or on top when even the preferred move leaves
   them worse by a pawn or more. A hypothetical ("would have left you clearly better")
   describes that preferred move, so it is flagged too. It also flags a row that calls the
   student worse or losing when they stayed a pawn or more better after the move played.
   It skips advice ("when you're winning, …"), "better or worse", "better off" and
   material ("winning a pawn"). `training.qc` runs it on every row as violation kind
   `eval_sign`. Facts without an evaluation line (whole-game facts) check nothing, and the
   held-out evaluation's claim metric is unchanged (`METRIC_VERSION` stays 2).

   **How it was tuned, stated plainly.** The patterns were written against the 487 rows of
   the 8 Oct run. On those rows the first draft flagged 15. Reading them, 2 were false
   ("leaves you better or worse", "you're winning a central pawn") and 3 were advice. With
   those excluded it flags 10, all real when read, including all 5 sign errors the board
   check confirmed. It was developed on these rows, so its precision on new rows is
   measured below, not assumed.
3. `training.judge_rows --exclude <verdicts>` leaves an earlier verdict file's rows out of
   the random sample.

The board, captures, attacked pieces, lines and line material are unchanged. 590 tests
pass.

## Run

The same 146 games as the 8 Oct run (`data/games/spotcheck146.json`), same settings, into
a new file. The 8 Oct rows stay as they are.

```
python -m training.distill --sources data/games/spotcheck146.json --teacher deepseek \
    --teacher-thinking disabled --workers 8 --retries 1 --positions-per-game 4 \
    --no-game-rows --resume --out data/distill/raw_deepseek_pos_v3.jsonl \
    --max-teacher-calls 16000
python -m training.qc data/distill/raw_deepseek_pos_v3.jsonl \
    --passed-out data/distill/deepseek_pos_v3_qc.jsonl
```

About 560 DeepSeek calls, about $0.70 off-peak (the 8 Oct run: 558 calls, 0.60M input +
0.15M output tokens). There is no pilot: the change is one line of the facts block and
one sentence of the prompt, and this run is itself small.

## Spot-check

One sample, judged by `claude-opus-4-8` with rubric `eval/rubric.py`, each row against its
own facts block. The Anthropic balance is $4: a judged position row measured 1,695 input
tokens (mean of 5, `count_tokens`) and about 160 output tokens, so about $0.0125 a call at
$5 / $25 per million, and 100 calls is about $1.25.

- **Fresh sample (decides the reading).** 100 rows drawn with seed 20261008 from the
  QC-passed v3 rows, leaving out the 150 positions judged twice already
  (`--exclude data/distill/deepseek_qc_judged.jsonl`). These positions have not been
  judged before and did not shape the facts block or the QC check. They come from the same
  146 games: the remaining 1,854 games are not generated until the reading passes.
- **Same 150 positions: not judged again.** For those positions only the free numbers are
  reported against the 8 Oct rows: QC pass rate, each violation kind (including how many
  `eval_sign` flags remain), grounding rate and completion length.

```
python -m training.judge_rows data/distill/deepseek_pos_v3_qc.jsonl --n 100 \
    --seed 20261008 --exclude data/distill/deepseek_qc_judged.jsonl \
    --out data/distill/deepseek_pos_v3_fresh_judged.jsonl --max-judge-calls 100
```

Reported for the fresh sample: factual mean, counts below 5 and below 4, and confirmed
errors with a 95% Wilson interval. At n = 100 the interval is wide (4 errors would be 4.0%,
1.6–9.8%), and the reading below still uses the point estimate, as before.

Every row scoring factual 3 or lower is checked against the board with python-chess and
marked a real error or a judge miss, as before. Every `eval_sign` flag in the v3 run is
read and marked true or false, which gives the check's precision on rows it was not tuned
on.

## Reading (fixed now)

On the **fresh sample** of 100:

- **Pass** if both hold: factual mean ≥ 4.5, and hand-confirmed real errors under 5% of the
  judged rows. Then the account is topped up and the other 1,854 games are generated with
  this facts block (`--sources data/games/manifest.json --resume` into
  `raw_deepseek_pos_v3.jsonl`). The training set is the 1,928 QC-passed game rows plus
  the QC-passed v3 position rows.
- **Fail:** the error kinds are reported. No further facts-block iteration is judged on
  these 146 games again. The fallbacks to weigh then are fine-tuning on game rows alone,
  or keeping only the position rows whose facts carry a clear-cut tactic.

If `eval_sign` turns out to be under 80% precise on the v3 run, it is reported and its
flags are reviewed before any row it drops is discarded for training. The pass reading does
not depend on it.

## Cost

About $0.70 of DeepSeek (balance about $6.10 before the run) and 100 Opus judge calls,
about $1.25 of the $4 Anthropic balance.

## Result

Not run yet.
