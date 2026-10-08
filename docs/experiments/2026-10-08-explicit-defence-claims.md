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
