# Position rows that name both pieces in every attack or defence claim

**Status:** pre-registered 8 Oct 2026, before any row was generated. Code on branch
`feat/explicit-defence-claims` (stacked on `feat/named-defenders`).

## Where this sits

`2026-10-08-named-defenders.md` failed (factual 4.51, confirmed errors 6 of 100) and was
declared final, with the training set to be game rows alone. Across the three judged
samples since, confirmed errors were 6, 6 and 6 of 100: 18 of 300 = 6.0% (95% Wilson
interval 3.8–9.3%). On 8 Oct the user decided to keep position rows anyway, as a stated
deviation from the 5% bar. Whether they go into training is to be settled by the student,
not the row error rate: a game-only vs mixed comparison on the held-out games, to be
pre-registered separately before it runs. This note covers only the last change to how
position rows are written, made before the rest of the corpus is generated.

## Why

Three of the six v4 errors still misstated what attacks or defends what, against facts
that name every attacker and defender. One of them, "Qd5 … where it defends your bishop on
g2" (#948, through a pawn on e4), escaped the QC check because its subject was "it". In
v4, 34% of attack or defence pairings had a pronoun or a bare move as subject, and 6% named
the piece with its square (baseline below).

## The change

1. **A prompt rule** (commit `3392184`), appended to the defence rule: "When you say it,
   name both pieces with their squares ("your queen on d5 defends your bishop on g2"),
   never "it" or a bare move like Qd5." Pronouns elsewhere are allowed.
2. **The QC check reads moves and pronouns** (commit `423fe41`). In
   `eval.claims.check_defence_claims`, a move names the piece on its destination square
   ("Qd5" is the queen on d5, on the board after that move), and "it" or "which" right
   before the verb stands for the nearest earlier piece or move that is not itself an
   object. So in "your queen … it defended your knight, it defended your pawn" both are
   the queen. It also skips "indirectly" (an x-ray) and a move "defending" an unsquared
   piece of its own type ("Ne2, which defended the knight": it saved itself).

   **How it was tuned, stated plainly.** Developed on the 1,042 v3, v3b and v4 position
   rows. A prototype added 10 flags, 6 true; the 4 false ones were the three patterns just
   listed, now skipped. The final check flags 13 claims in 13 rows, all false on the board
   when read. That covers 4 of the 18 confirmed errors of the last three spot-checks
   (#405, #828, #948, #1595), up from 2, and 9 rows never sampled. Its precision on new
   rows is measured below.

607 tests pass. The facts block, the clear-cut filter and everything else are as in v4.

## Compliance measure (fixed now)

`scripts/claim_subjects.py` counts active "defends / protects / guards / supports /
attacks" verbs whose object is a piece or a square, and are not hypothetical, negated or
passive, by their subject: a piece with its square, a piece without one, a pronoun, a bare
move, or other (mostly a subject further back). Baseline:

| | Pairings | Pronoun or bare move | Piece on square |
|---|---|---|---|
| v3 (146 games) | 140 | 48 (34%) | 5 (4%) |
| v3b (100 games) | 76 | 23 (30%) | 1 (1%) |
| v4 (100 games) | 119 | 40 (34%) | 7 (6%) |

The rule counts as followed if pronoun-or-bare-move subjects fall to 10% or less of
pairings in the new rows.

## Games and run

100 corpus games, none among the 354 used so far (`spotcheck146`, `pilot10`,
`clearcut100`, `named100`), drawn from the other 1,646 with seed 20261011 by the same code
as before, written to `data/games/explicit100.json`.

```
python -m training.distill --sources data/games/explicit100.json --teacher deepseek \
    --teacher-thinking disabled --workers 8 --retries 1 --positions-per-game 4 \
    --no-game-rows --resume --out data/distill/raw_deepseek_pos_v5.jsonl \
    --max-teacher-calls 1000
python -m training.qc data/distill/raw_deepseek_pos_v5.jsonl \
    --passed-out data/distill/deepseek_pos_v5_qc.jsonl
python -m training.clear_cut data/distill/deepseek_pos_v5_qc.jsonl \
    --out data/distill/deepseek_pos_v5_clear.jsonl
python scripts/claim_subjects.py data/distill/raw_deepseek_pos_v5.jsonl
python -m training.judge_rows data/distill/deepseek_pos_v5_clear.jsonl --n 100 \
    --seed 20261011 --out data/distill/deepseek_pos_v5_clear_judged.jsonl \
    --max-judge-calls 100
```

Generation, QC, the filter and the compliance count run now (about $0.50 of DeepSeek). The
judge waits for an Anthropic top-up (balance about $0.15; 100 calls cost about $1.35).

## Spot-check and reading (fixed now)

As before: 100 clear-cut QC-passed rows, `claude-opus-4-8`, rubric `eval/rubric.py`; every
row at factual 3 or lower checked on the board and marked a real error or a judge miss;
borderline counts as an error; the 95% Wilson interval is reported. Every
`invented_defence` flag in the run is read and marked true or false.

- **This prompt (v5) generates the rest of the corpus** if both hold: factual mean ≥ 4.5,
  and confirmed errors no more than v4's 6 of 100.
- **Otherwise the v4 prompt does**, unchanged.

Either way the result is reported with the compliance count and the check's precision.
Whether position rows enter training is not decided here (see "Where this sits").

## Interim result (8 Oct 2026): generation and compliance; judging waits for a top-up

**Generation.** 100 games, 296 rows (268 grounded), 364 calls, 0.47M input + 0.10M output
tokens, about $0.50 off-peak, 3.9 minutes, no failures.

**Compliance: the rule was not followed.**

| | Pairings | Pronoun or bare move | Piece on square |
|---|---|---|---|
| v4 (before) | 119 | 40 (34%) | 7 (6%) |
| v5 (with the rule) | 172 | 55 (32%) | 16 (9%) |

The bar was 10% or less. The teacher still writes "it defends …" about as often as before.

**`invented_defence` on new rows.** The check flagged 3 v5 rows, read on the board:

| Row | Claim | Verdict |
|---|---|---|
| #189 p14 | "Qf6 … it defends your knight on c6" | true: White's knight on d6 blocks the queen on f6 |
| #1523 p36 | "your queen on d7 was safe because it was defended by your rook on f8" | true: d7 had no defender on any board, and this is the row's central explanation |
| #749 p18 | "White had it defended with the pawn on b2" | false: "defended with" is the passive form, read backwards |

**Precision on rows it was not tuned on: 2 of 3.** Both true flags came through the pronoun
handling this change added. A fix after registration, before judging (commit `1aa1ddf`),
reads "defended with" like "defended by". On all 1,338 position rows the check now flags 15
claims, all true when read. QC then passes 257 of 296 (87%): 12 placement flags, 2
`invented_defence`, 1 invented castling. **155 of the 257 (60%) are clear-cut.**

The judged sample, and so the reading, waits for the Anthropic top-up.

**Since (9–10 Oct):** the tool-augmented teacher was piloted
(`2026-10-09-tool-augmented-teacher-pilot.md`). Its "Where to resume" section proposes
folding this judge into a paired tools vs no-tools comparison; until that is decided, the
judge above stays as registered.

## Change to the registration (10 Oct 2026, before any v5 row was judged)

**The judge above will not run.** The user decided on 10 Oct to fold it into one paired
comparison, pre-registered in `2026-10-10-tools-vs-no-tools-paired.md`. Reasons: the rule
this note tests was not followed (pronoun subjects 34% → 32%), so the v5 and v4 prompts
write nearly the same text and the v5-or-v4 choice above would be decided by noise. The
open question is now whether the teacher checks the board with tools. The v5 prompt is
the no-tools arm of that comparison, and the reading there replaces the one above. The v5
rows in `raw_deepseek_pos_v5.jsonl` stay unjudged. Their compliance count and the check's
precision (2 of 3, then the fix) are reported as above.
