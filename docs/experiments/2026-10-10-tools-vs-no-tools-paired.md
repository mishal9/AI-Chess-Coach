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

100 corpus games, none among the 454 used so far (`spotcheck146`, `pilot10`,
`clearcut100`, `named100`, `explicit100`: 456 entries, 2 games in two files;
`tools_pilot20` is part of `explicit100`), drawn from the other 1,546 with seed 20261012 by
the same code as before. (Corrected before generation: the first version said 474 and
1,526.)

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

## Result (10 Oct 2026): no difference; the plain (v5) prompt writes the corpus

**Generation.** 100 games (`data/games/paired100.json`), 274 rows in each arm, no failures.

| | Plain | Tools |
|---|---|---|
| Rows / grounded | 274 / 251 | 274 / 252 |
| Pass QC | 228 (83%) | 241 (88%) |
| QC flags: placement / `invented_defence` / chat preamble | 23 / 5 / 1 | 13 / 1 / 0 |
| Clear-cut and QC-passed | 132 | 146 |
| Teacher calls; input + output tokens | 332; 0.42M + 0.10M | 654; 1.55M + 0.15M |
| Tokens per row (input / output) | 1.5k / 350 | 5.7k / 550 |
| Tool calls per row (mean / rows with none / max) | — | 3.5 / 0 / 16 |

Both arms together cost $0.58 of DeepSeek (balance $4.36 → $3.78). Most of the tools arm's
repeated prompt prefixes were billed at the cache-hit rate. 159 positions are clear-cut in
both arms (the filter reads only the facts, which are the same). 126 of them pass QC in
both, 20 pass only with tools and 6 pass only without. So the tools arm loses fewer
positions to QC, and the paired sample leaves out more of its rows than of the plain
arm's.

**`invented_defence` flags, read on the board.** Plain: 3 of 5 true (#171 p33 "the king
stepped away from defending the rook on e1"; #1295 p34 "d5, supported by the pawn on e6",
which is backwards; #1850 p39 "your bishop on d2 … defended your d4-pawn"). 2 false: #906
p5 ("defended your d4 pawn with Be3" is right; the check took the wrong subject) and #780
p10 (wrong subject; the sentence still implies the f6 knight defended f7, which it did
not). Tools: 0 of 1 true. #1419 p6 is a negation ("couldn't actually defend") that the check
should skip. Its "it was blocked" states a relation that came from the tools, not the facts.
That is the kind of claim veto-only was meant to keep out. (Fixed after this result, commit on
`feat/defence-check-metric-v3`: a negation may now have one word before the verb. Across
all 2,593 position rows it removes this flag and changes no other. The result above was
computed with the old check, which dropped this row from the tools arm at QC.)

**Claim measures (all rows).**

| | Plain | Tools |
|---|---|---|
| Attack/defence pairings; pronoun or bare-move subject | 145; 40 (28%) | 145; 43 (30%) |
| Defence claims: stated / unstated / false | 60 / 2 / 5 | 80 / 6 / 1 |

**Judged sample** (`claude-opus-4-8`, the same 100 positions in both arms):

| | Plain | Tools |
|---|---|---|
| Factual mean | 4.54 | 4.59 |
| Factual 2 / 3 / 4 / 5 | 2 / 5 / 30 / 63 | 4 / 7 / 15 / 74 |
| Rows at 3 or lower | 7 | 11 |
| Overall | 4.83 | 4.85 |

Paired factual difference (tools − plain): mean +0.05; tools better on 22 positions, the
same on 62, worse on 16.

**Blind board check of the 18 rows at 3 or lower.** All 18 were pooled, shuffled and marked
before the arms were revealed: 15 real errors (4 borderline, counted as errors) and 3 judge
misses.

| Row | Arm | Factual | Verdict | What is wrong |
|---|---|---|---|---|
| #926 p45 | plain | 3 | real | "your rook on c1 was … pinning White's rook on e1 against the rook on e2": no such pin |
| #1423 p30 | plain | 2 | real | Qf4 "pulled your queen away" from f6, which it still defends (facts); Ne3 "accepts the knight is lost", but it moves the knight |
| #1355 p3 | plain | 2 | real (borderline) | after b5, "the a6 pawn itself is still under attack": the facts list no attacker |
| #1873 p11 | plain | 3 | real | Nc3 "brings a piece to a square where it defends your knight on d5": Nc3 *is* that knight |
| #1161 p12 | plain | 3 | real | Rxb4 moved the rook "off the b-file" and "didn't add a defender to b5": it stays on the b-file and does defend b5 (facts) |
| #456 p54 | plain | 3 | real | Kd4 "instead of trying to defend the bishop": the king on d4 does defend c4, and the line keeps the bishop |
| #80 p38 | plain | 3 | real (borderline) | "your queen was the only piece that could have come to [the e8 knight's] rescue": neither queen square defends e8; the knight saves itself with Nc7 |
| #906 p11 | tools | 3 | real (borderline) | the queen on d4 "was holding your advanced pawn on c6 together": c6 had no defender (facts) |
| #24 p39 | tools | 3 | judge miss | a bishop attacked once and defended once called "hanging"; the line does win it |
| #248 p23 | tools | 2 | real (borderline) | "Your knight on g3 … was the only thing keeping your queen on g4 connected to your rook on d1": it wasn't. The rest (Ne2 blocks the g4–d1 diagonal) is right, and the judge's objection to it is wrong |
| #1927 p30 | tools | 2 | real | Ree8 "moved your rook off the e-file": it stays on it; "down a queen for a rook and bishop" (the bishops were traded) |
| #1510 p16 | tools | 3 | real | f4 "was about giving your king an escape square": f4 blocks the c7–h2 diagonal behind the queen |
| #613 p28 | tools | 3 | real | after Nxf8+, "you left your queen on c4 with no defender": the b3 pawn still defends it (facts) |
| #926 p45 | tools | 2 | real | Rxe1+ Rxe1 "let White's rook take your rook for free, leaving you down a rook": it is a rook trade |
| #191 p58 | tools | 2 | real | the bishop on d4 "wasn't going anywhere … you could have collected it whenever you wanted": in the line it is never taken; and after Kxd4 the d2 pawn is not taken next |
| #1161 p12 | tools | 3 | judge miss | the b5 bishop "left hanging" after Rxb4 while defended twice; axb5 does win it |
| #1873 p11 | tools | 3 | real | Nc3 brings "a knight to guard the d5 knight": the same error as the plain row |
| #1096 p19 | tools | 3 | judge miss | "immediately lost" for a bishop taken one move later; nothing false |

| | Plain | Tools |
|---|---|---|
| Confirmed errors | **7 / 100 = 7.0%** (95% Wilson 3.4–13.7%) | **8 / 100 = 8.0%** (4.1–15.0%) |
| Both arms wrong on the same position | 2 (#926 p45, #1873 p11) | |
| Wrong in this arm only | 5 | 6 |

Exact McNemar p = 1.0 (5 vs 6 discordant positions).

**Reading.** The tools arm has more confirmed errors (8 against 7), so under the rule fixed
above **the plain (v5) prompt writes the rest of the corpus**. Its factual mean is higher
(4.59 against 4.54), but the rule needs both conditions. Neither arm is under the 5% bar.
Pooled with the last three judged samples, the no-tools teacher's confirmed errors are 25
of 400 = 6.25% (95% Wilson 4.3–9.1%).

**What this says.** Checking the board while writing did not reduce errors. The tools arm
wrote more rows the judge scored 5 (74 against 63), more rows at 3 or lower (11 against 7),
and it fails QC less often. Its errors are the same kind as before: causal stories about
which piece did what ("Kd4 instead of defending", "f4 gives an escape square", "left you
down a rook"). The tools could have checked every one of them, but the teacher did not
call them on those claims. The 3.5 calls per row went to relations the teacher was already
checking. This matches pilot D's #328 p22, and Kim et al.'s finding that adding information
cuts static errors but not reasoning errors.

## Against the published result (read 10 Oct 2026, after the result above)

Hebbar, Sheng, Oh and Viswanath, "Hallucinations on the Board: Tool-Augmented Evaluation of
LLM Chess Commentary", arXiv 2608.04240v1 (4 Aug 2026), is the result that motivated the
tools pilot. Read in full, it does not contradict ours. It tests a different contrast:

- **Their baseline was nearly bare.** Without tools, models get "only the board state as a
  FEN string and the move played" and "rely entirely on internal chess knowledge"
  (Section 4.1). With tools, they may call 17 tools before writing (Table 4, Appendix B.1):
  position queries (`get_piece_at`, `get_material`, …), attack and defence
  (`count_attackers_defenders`, `is_pinned`, …), geometry, `try_variation`, and Stockfish
  (`get_engine_eval`, `get_top_moves`, `compare_moves`). Our facts block already states most
  of what those tools return: the board, named attackers and defenders, capture-marked
  engine lines and the evaluation.
- **There is no middle condition.** No condition gives the model structured facts in the
  prompt without tools. Their gain (DeepSeek V4 Pro 36.7% → 14.4% incorrect sub-claims,
  Table 2) therefore mixes two effects: having board and engine information at all, and
  using tools to get it. This run measures the step they do not. Given that information in
  the prompt, tools added nothing we could detect (7 vs 8 confirmed errors in 100 paired
  rows).
- **Their error types agree with ours.** Tools "shift the distribution rather than
  uniformly shrinking it" (Section 6.1): legality checks and board-state queries "largely
  eliminate low-level hallucinations", and errors concentrate in tactical reasoning. That
  is the residue in our rows. Their per-category numbers are in a figure we did not read.
- **Gains shrink as the baseline improves** (Table 2, without → with tools): DeepSeek V4 Pro
  36.7% → 14.4%, GPT-5.4 22.0% → 9.2%, Claude Opus 4.7 20.8% → 13.4%, Gemini 3.1 Pro
  10.8% → 7.5%.
- **Their judge shares the generator's tools.** Sub-claims are judged by GPT-5.4 "equipped
  with the full tool suite" (Stockfish 14.1, depth 18). A writer with tools may favour the
  claims tools can verify, which could flatter the with-tools condition. Human agreement
  with the judge is modest: 69–83% per annotator, Fleiss' κ 0.285 on 50 claims.

The numbers are not comparable across the two studies: different metric (their sub-claim
error rate vs our judge score plus a board check of low scorers), positions, prompts and
judge. What the paper can say, as worded for it: "In 2608.04240 the no-tool baseline
received only a FEN and the move. With structured board and engine facts in the prompt,
adding tools gave no detectable gain (7 vs 8 confirmed errors in 100 paired rows; one
teacher; a sample that detects only large effects).
