# Position teacher with and without board tools: a paired comparison

**Status:** pre-registered 10 Oct 2026, before any row was generated. Code on branch
`feat/tool-augmented-teacher`. This replaces the v5 judge registered in
`2026-10-08-explicit-defence-claims.md` (see the change recorded there).

## Question

Does checking the board with tools while writing (pilot D, veto only:
`2026-10-09-tool-augmented-teacher-pilot.md`) make the position teacher's rows more
accurate than the current prompt without tools? QC cannot answer this. The errors left are
causal relations ("Qe4 let go of both jobs") that only a judge and a board check see. The
answer decides which teacher writes the rest of the corpus.

## Arms

Both arms use the same games, facts, prompt and settings as v5 (commit `3392184` prompt,
DeepSeek V4 Pro, thinking disabled, temperature 0 with one grounding retry at 0.7, 4
positions per game, no game rows). They differ only in `--teacher-tools`:

- **Plain**: no tools. The v5 prompt as it stands.
- **Tools**: `--teacher-tools` as in pilot D (commit `7b49499`). The first turn must call a
  tool, there are at most 8 tool rounds, and the system prompt says to use the tools to
  catch mistakes and to state only what the facts state.

The student's prompt and the facts block are the same in both. Clear-cut is decided from
the facts alone (`training.clear_cut`), so both arms have the same clear-cut positions.

## Games

100 corpus games, none among the 474 used so far (`spotcheck146`, `pilot10`,
`clearcut100`, `named100`, `explicit100`; `tools_pilot20` is part of `explicit100`), drawn
from the other 1,526 with seed 20261012 by the same code as before:

```python
import json, random
key = lambda g: (g["pgn"], g["game_index"])
m = json.load(open("data/games/manifest.json"))
used = {key(g) for f in ("spotcheck146.json", "pilot10.json", "clearcut100.json",
                         "named100.json", "explicit100.json")
        for g in json.load(open("data/games/" + f))}
pool = [g for g in m if key(g) not in used]
pick = sorted(random.Random(20261012).sample(range(len(pool)), 100))
json.dump([pool[i] for i in pick], open("data/games/paired100.json", "w"), indent=1)
```

## Run

```
for arm in plain tools; do
  python -m training.distill --sources data/games/paired100.json --teacher deepseek \
      --teacher-thinking disabled --workers 8 --retries 1 --positions-per-game 4 \
      --no-game-rows --resume --out data/distill/raw_deepseek_pos_paired_$arm.jsonl \
      --max-teacher-calls 1000 $( [ $arm = tools ] && echo --teacher-tools )
  python -m training.qc data/distill/raw_deepseek_pos_paired_$arm.jsonl \
      --passed-out data/distill/deepseek_pos_paired_${arm}_qc.jsonl
  python -m training.clear_cut data/distill/deepseek_pos_paired_${arm}_qc.jsonl \
      --out data/distill/deepseek_pos_paired_${arm}_clear.jsonl
done
```

**The paired sample.** Only positions that are clear-cut and pass QC in *both* arms can be
judged in both. The plain arm's rows for those positions are written to
`deepseek_pos_paired_plain_both.jsonl` (keys by `training.qc.row_key`). 100 are drawn from
them with seed 20261012 and judged, then the tools arm is judged on the same keys:

```
python -m training.judge_rows data/distill/deepseek_pos_paired_plain_both.jsonl --n 100 \
    --seed 20261012 --out data/distill/deepseek_pos_paired_plain_judged.jsonl \
    --max-judge-calls 100
python -m training.judge_rows data/distill/deepseek_pos_paired_tools_clear.jsonl \
    --same-as data/distill/deepseek_pos_paired_plain_judged.jsonl \
    --out data/distill/deepseek_pos_paired_tools_judged.jsonl --max-judge-calls 100
```

If fewer than 100 positions are in both arms, all of them are judged. The positions that
are clear-cut in both arms but pass QC in only one are counted and reported by arm, since
dropping them could favour the arm that fails QC on hard positions.

## Spot-check and reading (fixed now)

As before: `claude-opus-4-8`, rubric `eval/rubric.py`, each row against its own facts. The
judge sees only the facts and the coaching, not the arm. Every row at factual 3 or lower in
either arm is checked on the board with python-chess and marked a real error or a judge
miss. Borderline counts as an error. **The board check is blind.** The low-scoring rows of
both arms are pooled, shuffled with seed 20261012 and given neutral ids, and they are
marked before the arm is revealed. Wilson 95% intervals are reported.

- **The tools teacher writes the rest of the corpus** if both hold: it has fewer confirmed
  errors than the plain arm on the same positions, and its factual mean is not lower.
- **Otherwise the plain (v5) prompt does**, at about a third of the cost.

This picks a teacher. It does not claim a significant difference: at about 6 errors in 100,
a paired sample this size cannot separate 6% from 3%. As descriptives, the following are
reported alongside:

- the paired factual difference (mean and the counts of positions better, same and worse);
- discordant error pairs, with an exact McNemar p-value;
- QC pass, clear-cut and grounding counts per arm;
- `scripts/claim_subjects.py` and `scripts/claim_support.py` per arm;
- every `invented_defence` flag, read by hand and marked true or false;
- tool calls, tokens and cost per row.

Each arm is also reported against the 5% bar, from which keeping position rows is already a
stated deviation (`2026-10-08-explicit-defence-claims.md`, "Where this sits"). Whether
position rows enter training is decided later by the game-only vs mixed student
comparison, not here.

## Cost

DeepSeek: plain about $0.50, tools up to about $1.50 (balance $4.36). Opus: up to 200
judge calls at about $0.0135, about $2.70.
