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
