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

## Result (8 Oct 2026): fail

**Generation.** 487 rows (471 grounded), 552 calls, 0.61M input + 0.15M output tokens,
about $0.71 off-peak, 6.6 minutes, no failures. QC passes 451 (93%), median 1,224
characters. Violations: 20 placement flags, 1 `eval_sign`.

**`eval_sign` precision.** Its one flag on the v3 run was false: "suddenly you're losing your
rook in the corner" is about material. That fix (commit `2828787`) mirrors the "winning a
pawn" exclusion. With it, the check flags 0 v3 rows and still 10 of the 8 Oct rows. Its
measured precision on rows it was not tuned on is 0 of 1. There are almost no sign errors
left for it to catch, so the measurement says little.

**Same 150 positions (not judged).**

| | 8 Oct rows | v3 rows |
|---|---|---|
| Pass QC | 128 | 137 |
| Grounded | 145 | 145 |
| Placement flags | 11 | 8 |
| Rows with an `eval_sign` flag (current check) | 5 | 0 |
| Median length (characters) | 1,254 | 1,217 |

**Fresh sample** (`claude-opus-4-8`, 100 rows, `data/distill/deepseek_pos_v3_fresh_judged.jsonl`):
**factual mean 4.44**, counts 2 / 3 / 4 / 5 = 2 / 7 / 36 / 55, 9 below 4, overall 4.78.

**Board check of the 9 rows at 3 or lower:** 6 real errors (2 borderline), 3 judge misses.

| Row | Factual | Verdict | What is wrong |
|---|---|---|---|
| #103 p52 | 3 | real | "by dropping to g2 you gave Black a free hand" on f2: a king on g2 still defends f2 (2 defenders before and after) |
| #237 p17 | 3 | judge miss | interpretation of the queen's role; nothing stated is false on the board |
| #405 p17 | 3 | real | "e4 … already well-supported by your pawn on e3": the e4 pawn *is* the e3 pawn |
| #666 p24 | 3 | judge miss | h7 was attacked, and the queen does land on g6 with check; the light/dark square talk is interpretation |
| #987 p11 | 3 | real (borderline) | "left your bishop on e6 hanging": 2 attackers, 2 defenders |
| #1070 p29 | 2 | real | "your queen on c3 staring at Black's queen on d6 with nothing in between": c3 and d6 share no line |
| #1070 p26 | 3 | real (borderline) | "you were up a pawn in practical terms after the trade": material 26–26 |
| #1154 p14 | 3 | judge miss | "you lose the exchange (a rook for a bishop)" is right; the judge read it as a free rook |
| #1595 p26 | 2 | real | "your queen … no longer defended your knight on f5" and "Qe2 protects the knight": f5 had 0 defenders, and the line shows Qxf5 |

**Confirmed errors: 6 of 100 = 6.0% (95% Wilson interval 2.8–12.5%)**, 4.0% (1.6–9.8%)
without the two borderline rows.

**Reading.** Both conditions fail: factual mean 4.44 < 4.5, and confirmed errors 6.0% ≥ 5%.
As fixed above, these 146 games are not used again to judge a facts-block change, and the
remaining 1,854 games are not generated.

**What changed in the errors.** No row calls a losing student better: the evaluation in
words removed that error. Four of the six real errors (#103, #405, #987, #1595) misstate
what defends what, though the facts list attacker and defender counts. One misreads board
geometry (#1070 p29), and one spins material (#1070 p26).

**Across the three versions.**

| | Old rows (1-line facts) | 8 Oct (board) | v3 (evaluation in words) |
|---|---|---|---|
| Factual mean | 4.18 (same 133) | 4.38 (133) | 4.44 (fresh 100) |
| Confirmed errors | 8 / 150 = 5.3% | 10 / 133 = 7.5% | 6 / 100 = 6.0% |

The v3 figure is on different positions from the other two, so the columns are not paired.

**After the reading, not pre-registered.** Splitting the fresh 100 by whether the facts
show a clear-cut tactic (the opponent's best reply captures at once, or the move leaves a
piece attacked with no defender): 49 such rows score factual 4.49 with 1 real error; the
other 51 score 4.39 with 5. This split was looked at after the result, on the rows that
produced it, so it is a lead for the next decision, not evidence.
