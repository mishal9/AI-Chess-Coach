# Clear-cut position rows, judged on new games

**Status:** pre-registered 8 Oct 2026, before any row was generated. Code on branch
`feat/clear-cut-position-rows` (stacked on `feat/position-facts-board`). Follows
`2026-10-08-position-facts-eval-words.md`, whose fresh sample failed (factual 4.44,
confirmed errors 6 of 100). This is option B of that note's open decision, chosen 8 Oct.

## Why

The ablation of 10 Aug found position rows raise grounding (game rows only 0.76, mixed
0.91), so dropping them has a cost. After the v3 result, the fresh 100 were split by
whether the facts show a clear-cut tactic: 49 such rows scored factual 4.49 with 1 real
error, the other 51 scored 4.39 with 5. That split was looked at after the result, on the
rows that produced it. This run tests it on rows that played no part in it.

## The filter

`training.clear_cut.is_clear_cut` reads the row's facts block, not its coaching. A row is
clear-cut if the facts show either:

- the opponent's best reply after the move captures at once: the first move of "Engine's
  best line after your move" is marked "(takes your …)", or
- the move played leaves one of the student's pieces attacked with no defender: "After
  your move, your pieces under attack:" lists a piece with "defenders 0".

Applied to the fresh 100 of the v3 run, it reproduces the post-hoc split exactly (49 rows,
factual 4.49). On all 451 QC-passed v3 rows, 234 (52%) are clear-cut: 192 by the reply
capture, 135 by an undefended piece.

The facts block, the prompt, the teacher settings and QC are those of the v3 run
unchanged. The only change since that run is commit `2828787` ("losing your rook" is
material), in QC, not generation. 596 tests pass.

## Games

100 corpus games, none among the 146 spot-check games or the 10 pilot games (154 games
between them), drawn from the other 1,846 in `data/games/manifest.json` with seed
20261009:

```python
import json, random
key = lambda g: (g["pgn"], g["game_index"])
m = json.load(open("data/games/manifest.json"))
used = {key(g) for f in ("spotcheck146.json", "pilot10.json")
        for g in json.load(open("data/games/" + f))}
pool = [g for g in m if key(g) not in used]
pick = sorted(random.Random(20261009).sample(range(len(pool)), 100))
json.dump([pool[i] for i in pick], open("data/games/clearcut100.json", "w"), indent=1)
```

None of these games has had a row generated, read or judged.

## Run

```
python -m training.distill --sources data/games/clearcut100.json --teacher deepseek \
    --teacher-thinking disabled --workers 8 --retries 1 --positions-per-game 4 \
    --no-game-rows --resume --out data/distill/raw_deepseek_pos_v3b.jsonl \
    --max-teacher-calls 1000
python -m training.qc data/distill/raw_deepseek_pos_v3b.jsonl \
    --passed-out data/distill/deepseek_pos_v3b_qc.jsonl
python -m training.clear_cut data/distill/deepseek_pos_v3b_qc.jsonl \
    --out data/distill/deepseek_pos_v3b_clear.jsonl
```

At v3 rates (552 calls and $0.71 for 146 games, 451 QC-passed rows) this is about 380
calls and $0.50 off-peak, giving about 310 QC-passed rows and about 160 clear-cut ones.

## Spot-check

```
python -m training.judge_rows data/distill/deepseek_pos_v3b_clear.jsonl --n 100 \
    --seed 20261009 --out data/distill/deepseek_pos_v3b_clear_judged.jsonl \
    --max-judge-calls 100
```

100 clear-cut rows, judged by `claude-opus-4-8` with rubric `eval/rubric.py`, each row
against its own facts block, as before. About $1.25 at about $0.0125 a call (Anthropic
balance about $2.75). If fewer than 100 rows are clear-cut, all of them are judged and the
count is reported; the rule below is unchanged.

Every row scoring factual 3 or lower is checked against the board with python-chess and
marked a real error or a judge miss, as before. Rows marked borderline count as errors.

Also reported, without judging: QC pass rate and violation kinds, the clear-cut share of
QC-passed rows, and how many clear-cut rows each condition admits.

## Reading (fixed now)

- **Pass** if both hold on the judged clear-cut rows: factual mean ≥ 4.5, and
  hand-confirmed real errors under 5%. Then the DeepSeek account is topped up and the rest
  of the corpus is generated into the same file with the same settings
  (`--sources data/games/manifest.json --resume`). The 146 spot-check games are generated
  again there, so every training position row comes from this one run. The training set is
  the 1,928 QC-passed game rows plus the QC-passed clear-cut rows of
  `raw_deepseek_pos_v3b.jsonl`.
- **Fail:** the training set is the 1,928 QC-passed game rows alone (option A). No further
  position-row variant is generated or judged for this paper. The error kinds are reported.

The interval at n = 100 is wide (4 errors would be 4.0%, 1.6–9.8%). The reading uses the
point estimate, as before, and the 95% Wilson interval is reported with it.

## What a pass buys

At v3 rates the corpus gives about 3.1 QC-passed position rows per game, so about 3,200
clear-cut rows from 2,000 games. At the 1 game : 2 position mix of `paper-protocol.md`
the largest arm is then about 1,600 game + 3,200 position rows, if the clear-cut share
holds on the full corpus.

## Cost

About $0.50 of DeepSeek (balance about $5.40) and about $1.25 of Opus judging. On a pass,
the remaining 1,900 games cost about $9.25 of DeepSeek, so the account needs a top-up of
about $5 first.

## Result (8 Oct 2026): fail

**Generation.** 100 games, 279 rows (267 grounded), 328 calls, 0.37M input + 0.09M output
tokens, about $0.45 off-peak, 3.7 minutes, no failures. QC passes 247 (89%), median 1,270
characters. Violations: 21 placement flags, 1 invented castling, 0 `eval_sign`. **143 of
the 247 (58%) are clear-cut.**

**Judged sample** (`claude-opus-4-8`, 100 of the 143 clear-cut rows,
`data/distill/deepseek_pos_v3b_clear_judged.jsonl`): **factual mean 4.55**, counts
2 / 3 / 4 / 5 = 2 / 4 / 31 / 63, 6 below 4, overall 4.84.

**Board check of the 6 rows at 3 or lower:** 6 real errors, 0 judge misses.

| Row | Factual | What is wrong |
|---|---|---|
| #43 p33 | 2 | "your rook on a1 was your only piece that could defend the back rank, and you moved it away": Re1 stays on the first rank and still covers f1. "Black attacks your queen" with Re3: the rook on e3 does not reach h4 |
| #828 p12 | 3 | "After e5, the knight on c6 no longer protects the queen": a knight on c6 never defends d5; its one defender was the e6 pawn (which the row also names) |
| #923 p22 | 2 | "it cost you a piece": the line ends 19–20, a pawn. "that one defender was also the piece protecting your knight": the queen's defender on d7 is Rd1, which does not defend f3 |
| #1763 p33 | 3 | "Once it left, your f4-pawn was left hanging with no defender": f4 had no defender before the move either; the knight defended e2, not f4 |
| #1980 p21 | 3 | "By moving it to c8, you left your knight on g6 with only two defenders": g6 is defended by f7 and h7 before and after; the rook never defended it |
| #1996 p9 | 3 | "you have time to develop with Nd7 and then Re1, f5, Nd2, Nf6": Re1 and Nd2 are White's moves. "blocked by your own pawns on e4 and e6": e6 is not on the g6 bishop's diagonals |

**Confirmed errors: 6 of 100 = 6.0% (95% Wilson interval 2.8–12.5%).**

**Reading.** Factual 4.55 ≥ 4.5 passes; confirmed errors 6.0% ≥ 5% fails. The rule needs
both, so the reading is **fail**. As fixed above, the training set is the 1,928 QC-passed
game rows alone, and no further position-row variant is generated or judged for this paper.

**What the errors are.** Four of the six (#828, #923, #1763, #1980) misstate what defends
what, as four of six did in the v3 fresh sample, though every one of these facts blocks
lists attacker and defender counts for the pieces involved. One (#1996) misreads whose move
is whose in an engine line, and one (#43) invents a back-rank story. The clear-cut filter
raised the factual mean (4.44 → 4.55) but did not lower the error rate (6.0% → 6.0%), on
different positions in each case.

**Across the four versions.**

| | Old rows (1-line facts) | 8 Oct (board) | v3 (evaluation in words) | v3, clear-cut, new games |
|---|---|---|---|---|
| Factual mean | 4.18 (same 133) | 4.38 (133) | 4.44 (fresh 100) | 4.55 (100) |
| Confirmed errors | 8 / 150 = 5.3% | 10 / 133 = 7.5% | 6 / 100 = 6.0% | 6 / 100 = 6.0% |
