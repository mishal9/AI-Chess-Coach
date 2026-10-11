# v5 position-row corpus: batch 1

**Status:** run 10 Oct 2026. The paired comparison (`2026-10-10-tools-vs-no-tools-paired.md`)
chose the plain v5 prompt without tools for the corpus. With $3.55 of DeepSeek credit, a
first batch of 500 games tests the run end to end before the rest is paid for.

## Games and run

500 of the 1,446 corpus games that have no rows yet (2,000 minus the 554 in `spotcheck146`,
`pilot10`, `clearcut100`, `named100`, `explicit100` and `paired100`), drawn with seed
20261013, written to `data/games/corpus_batch1_500.json`. A random draw keeps the batch's
mix of rating bands and time controls the same as the corpus in expectation; the manifest
order would not.

```
python -m training.distill --sources data/games/corpus_batch1_500.json --teacher deepseek \
    --teacher-thinking disabled --workers 8 --retries 1 --positions-per-game 4 \
    --no-game-rows --resume --out data/distill/raw_deepseek_pos_v5.jsonl \
    --max-teacher-calls 4000
python -m training.qc data/distill/raw_deepseek_pos_v5.jsonl \
    --passed-out data/distill/deepseek_pos_v5_qc.jsonl
python -m training.clear_cut data/distill/deepseek_pos_v5_qc.jsonl \
    --out data/distill/deepseek_pos_v5_clear.jsonl
```

The rows go into the v5 file, which already held the 100 `explicit100` games, so the rest of
the corpus resumes into the same file. The QC in force is the one on `master` at `43a512b`
(defence check with the negation fix).

## Result

| | |
|---|---|
| Games / rows / grounded | 500 / 1,373 / 1,266 |
| Teacher calls; tokens | 1,646; 2.09M input + 0.48M output |
| Time | 17 minutes, 8 workers, no failures |
| Cost | $1.46 (balance $3.55 → $2.09), **$0.0029 a game** |

QC and the clear-cut filter over all v5 rows so far (600 games):

| | |
|---|---|
| Rows | 1,669 |
| Pass QC | 1,438 (86%) |
| QC flags | 95 placement, 21 `invented_defence`, 1 castling, 1 role inversion, 1 chat preamble |
| Clear-cut among those passing | 793 (55%) |

**A trial dataset** (scratch only, not the registered one): the 1,928 QC-passed game rows
(`deepseek_qc.jsonl`, 28 Sep), the 793 clear-cut v5 rows above and the 132 clear-cut rows of
the paired run's plain arm (also the v5 prompt), split by game with `training.dataset
--ratios 0.9 0.1 0`. The result is 2,584 train rows (1,739 game, 845 position) and 269
validation rows, with no game in both splits.

## `invented_defence` flags on the new rows, read on the board

The 500 batch games produced 19 flagged rows (the other 2 of the 21 are in `explicit100`,
read before). **14 true, 5 false: precision 74%.**

| Row | Claim | Verdict |
|---|---|---|
| #278 p13 | Bf3 "defends your d5 pawn" | true: the e4 pawn blocks the diagonal |
| #315 p26 | queen and "knight on d4 … defending each other and the a5-pawn" | true (borderline): the knight does not defend a5 |
| #485 p70 | h4 "already defended by your pawn on g5" | false: g5 does defend h4; the check read the knight as the target |
| #565 p60 | g5 drags "Black's queen away from defending the pawn on d5" | true: d5 has no defender (facts) |
| #807 p17 | Rf6 "defending your pawn on e5 from the side" | true: a rook on f6 does not reach e5 |
| #816 p22 | after Nh4 "your knight on f3 no longer defends the pawn on e4" | true: it never did (e4's defenders: knight on c3, pawn on d3) |
| #824 p33 | "your rook on f1 … defended your pawn on g4" | true: g4 has no defender (facts) |
| #880 p14 | "Your rook on a1 was defended by your bishop on f7" | true: that diagonal ends on a2. (Also false: "the knight on c3" does not attack a1.) |
| #934 p12 | with Nbd7 "you keep your knight on f6 protecting the bishop" | true: the knight blocked the b2–g7 diagonal; it did not defend g7 |
| #949 p6 | Kd7 "defends your pawn on e5" | true: d7 is not next to e5 |
| #1045 p36 | "your f5-pawn protected by the king on g7" | true: g7 is not next to f5 |
| #1105 p18 | "your queen on g3 was the only thing protecting that knight" on e4 | true: e4 has no defender (facts); the knight defends the queen |
| #1272 p17 | "Your c-pawn stays on c2, where it supports the knight on d4" | true: c2 covers b3 and d3 |
| #1395 p73 | "your rook on c3 … protected your b2 pawn" | true |
| #1528 p23 | "stopped defending your pawn on c3 with your queen" | false: the queen did defend c3; "with your queen" names the defender |
| #1568 p17 | "it was defended by the queen on d2" (it = the bishop on f4) | false: true on the board; the check took the wrong pronoun referent |
| #1892 p21 | "you left g7 defended only by your king" | false: true on the board (a square as target). The row still has a real error: it swaps which knight shielded g7 |
| #1903 p39 | Rd7 "supports your queen" on f5 | true |
| #1987 p14 | Rd1 "supports your pawn on d4" | false: an x-ray behind the queen on d2, which is fair chess language |

The check is unchanged. Its false flags cost 5 sound rows out of 1,669. Tuning it on these
rows would need a fresh set to measure it again.

## What it means for the rest of the corpus

- **Cost.** At $0.0029 a game, the 946 games still without rows cost about $2.75. Redoing
  the 354 sample games written with older prompts would add about $1.
- **Size.** At 2.78 rows a game, 86% QC and 55% clear-cut, about 1.3 clear-cut rows come
  from each game. With the `paired100` plain rows (132):
  - without redoing the 354 older-prompt games (1,546 games in the v5 file): about 2,170
    clear-cut position rows, a mixed pool of about 4,100, and about 3,260 at the sweep's
    registered 1 game : 2 position mix;
  - redoing them (1,900 games): about 2,630, about 4,560, and about 3,950 at 1:2.

  Either way, the registered 5,000-row point cannot be built, and a game-only arm stops at
  1,928 rows (about 1,735 in the train split). See
  `2026-10-10-game-only-vs-mixed-student.md`.

## Batch 2 and the sweep datasets (10–11 Oct 2026)

**Batch 2:** the remaining 1,300 games in seeded random order (seed 20261014,
`data/games/corpus_batch2_rest.json`). That is the 946 games with no rows and the 354
older-prompt sample games rewritten with v5, as registered. The command is the same as
batch 1, with `--sources data/games/corpus_batch2_rest.json --max-teacher-calls 11000`.
The run took about 46 minutes. One game (#385) failed on a dropped connection, and a rerun
with `--resume` regenerated it. Batch 2 wrote 3,726 rows; 4,453 calls; 5.69M input + 1.28M
output tokens. The user topped up DeepSeek during the run, and the balance afterwards was
$2.75.

**The full v5 corpus** (`raw_deepseek_pos_v5.jsonl`, 1,900 games; the other 100, `paired100`,
are in the paired run's plain arm):

| | |
|---|---|
| Rows / grounded | 5,395 / 4,972 |
| Games with a row | 1,851 (49 had no mistake worth a position row) |
| Pass QC | 4,649 (86%): 282 placement, 103 `invented_defence`, 12 chat preamble, 4 castling, 3 eval sign, 1 role flags |
| Clear-cut | 2,558 (55% of those passing) |
| Duplicate rows | 0 |

With the paired run's 132 clear-cut plain rows, there are **2,690 clear-cut v5 position rows**
(projected: about 2,630).

**Sweep datasets** (`training.sweep`, split seed 0 and order seed 0, 90/10 by game; chat
format; the `.jsonl` files are git-ignored, and each set's `manifest.json` is committed):

```
python -m training.sweep --game data/distill/deepseek_qc.jsonl \
    --position data/distill/deepseek_pos_v5_clear.jsonl \
    --position data/distill/deepseek_pos_paired_plain_clear.jsonl \
    --arm G:400,1000,1700 --arm M:400,1000,1700,2500,all \
    --out-root training/datasets --prefix sweep-v5
```

| Set | Train rows (game + position) | Validation rows |
|---|---|---|
| G-400, G-1000, G-1700 | 400, 1,000, 1,700 game | 189 (game) |
| M-400 | 133 + 267 | 449 |
| M-1000 | 333 + 667 | 449 |
| M-1700 | 566 + 1,134 | 449 |
| M-2500 | 833 + 1,667 | 449 |
| M-all | 1,215 + 2,430 = 3,645 | 449 |

Every smaller set of an arm is a prefix of the larger ones, and no set has a game in both
train and validation (checked). The game rows are the 28 Sep QC-passed rows
(`deepseek_qc.jsonl`, kind `game` only). That file's older position rows are not used.
