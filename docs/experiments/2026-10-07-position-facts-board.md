# Position rows regenerated from a facts block that carries the board

**Status:** pre-registered 7 Oct 2026, before any row was generated. Code on branch
`feat/position-facts-board` (stacked on `feat/deepseek-training-rows`).

## Why

The judge spot-check of the kept DeepSeek rows
(`2026-10-07-deepseek-training-rows-and-placement-audit.md`) found game rows clean (factual
4.78) and position rows not (4.19; 8 of 150 false on the board, 5.3%). A position row's
facts block held the game header and one line ("20...Qxd2?? (blunder): the engine
preferred Be6; cost about 68% win probability"). The teacher was asked to explain *why*
with no board and no line, and every one of the 8 errors is something a board would have
settled: what a capture took, whether the queens were on, file vs diagonal.

**Deviation, stated plainly.** The spot-check's pre-registered reading was "under 5% →
fine-tune as is", and the overall figure was 4.0%. That reading is set aside for position
rows. The reasons: 4.0% is a lower bound (rows scored 4 were not hand-checked), its interval
reaches 7.7%, position rows alone are at 5.3%, and the error is systematic (all 27 low
judge rationales name invented specifics), which a student would learn. Game rows are
kept as generated.

## The change

`coach.prompts.format_position_facts` now adds, after the moment's line, from the cached
depth-18 report alone (no new engine run):

- every piece of both sides before the move, written "rook on f8", and material for each
  side (queen 9, rook 5, bishop 3, knight 3, pawn 1);
- each side's attacked pieces with attacker and defender counts, before the move, and the
  coached side's again after it;
- what the played move captured (or "nothing") and whether it gave check, and the same for
  the preferred move;
- the engine evaluation in pawns from the coached side's view, with the preferred move and
  after the move played;
- the engine's preferred line from the position (`pv`, up to 8 plies) and its best line
  after the move played (the next ply's `pv`), both in numbered notation, each capture
  marked with what it takes ("Bxe6 (takes your queen)"), and the material at the end of the
  line, noted when the line ends on a capture (a recapture may follow).

The board licenses no move citations: each square follows "on", which the grounding metric
reads as a location (tested). The two lines do license their moves, and
`POSITION_SYSTEM_PROMPT` now says so and tells the coach to describe the board only as
listed, to call pieces attacked or defended and say who wins material only as listed, and
to trust the evaluation over a line's material count. The whole-game facts block, the app and the held-out evaluation are unchanged:
position facts are used only for training rows.

## Run

Same settings as the 27 Sep run, position rows only. The positions are picked by the same
deterministic rule (worst coachable mistakes first, up to 4 per game), so they are the same
5,669 positions as before and old and new rows pair one to one.

```
python -m training.distill --sources data/games/manifest.json --teacher deepseek \
    --teacher-thinking disabled --workers 8 --retries 1 --positions-per-game 4 \
    --no-game-rows --resume --out data/distill/raw_deepseek_pos_v2.jsonl \
    --max-teacher-calls 16000
python -m training.qc data/distill/raw_deepseek_pos_v2.jsonl \
    --passed-out data/distill/deepseek_pos_v2_qc.jsonl
```

**Order of work, amended 8 Oct 2026 before any row was generated.** The DeepSeek balance
($6.80) does not cover the full run (about $8.40 off-peak; the 28 Sep run billed $8.19 for
7.48M tokens, within 2% of the published off-peak cache-miss rates). The run is therefore
done in two steps into the same `--out` file. First the 146 games that hold the 150
spot-check positions (`data/games/spotcheck146.json`: the entries of `manifest.json` whose
key appears among the position rows of `deepseek_qc_judged.jsonl`; sha256 `cff39bc1…`),
which are then QC'd and judged as below. If the reading passes, the account is topped up and
the same command with `--sources data/games/manifest.json --resume` does the other 1,854
games; `--resume` skips games by `corpus.pgn#index`, so the judged rows are the rows of the
final file. If it fails, the remaining games are not generated. Settings, rows and reading
are otherwise unchanged.

A 10-game pilot is read by hand before the full run; it checks only that the rows run and
read sensibly, and does not touch the reading below. The pilot rows are archived and the
full run regenerates all 2,000 games, so every row comes from the final facts block.

### Pilots (7 Oct 2026, the first 10 corpus games, 33 position rows each)

Read by hand against the board. None of these rows is used for training or in the
spot-check.

1. **Board, captures and lines only** (`data/distill/pilot_pos_v2a/`). 31/33 grounded, 30/33
   pass QC. The board fixed the old kind of error, but 2 of 7 rows read had a new one: the
   teacher misread the engine line ("your rook ends up winning the queen" in
   24...Rfc8 25.Bxe6 Rxc5, an even queen trade) or invented an attack ("your knight on b4 is
   hanging — it's attacked by White's c3 knight"; a knight on c3 cannot reach b4 and
   nothing attacked it). Added: capture marks in the lines, material at the end of each
   line, and attacked pieces with attacker and defender counts.
2. **Plus capture marks and attacked pieces** (`pilot_pos_v2b/`). 30/33 grounded, 29/33
   pass QC. Both earlier errors gone. Of 8 rows read, 1 had an arithmetic error ("down a
   queen for a rook and a knight" for a queen lost for a knight), and 1 line was cut by the
   8-ply limit right after 39.Qxg3 took Black's queen, before the rook on g5 could
   recapture, so its material count showed the losing side 7 points ahead. Added: the
   engine evaluation, and a note when a line ends on a capture.
3. **Final block, minus a wording change** (the note then read "the line stops
   mid-exchange", wrong for a line that ends on a completed trade; reworded afterwards).
   30/33 grounded, 27/33 pass QC (3 placement flags, all of the destination-of-the-preferred-
   move kind the 7 Oct audit found false). Both pilot-2 errors gone ("You won a knight
   (3 points) but lost your queen (9 points)"; "You lose the exchange"). One row still calls
   38.Rxg5 fxg5 winning material, a trade the facts show.

Across the three pilots QC pass rates (91%, 88%, 82%) are within noise at n = 33 and near
the old position rows' 94%.

## Spot-check

- Rows: the regenerated rows for the **same 150 positions** the 7 Oct spot-check judged
  (`--same-as data/distill/deepseek_qc_judged.jsonl --kind position`), taken from the
  QC-passed file. Positions whose new row fails QC are counted and reported, not judged.
- Judge: `claude-opus-4-8`, rubric `eval/rubric.py`, each row against its own (new) facts
  block. Caveat: the judge now sees the board, so it can verify more than before; a paired
  comparison is still the fairest one available.
- Reported: factual mean, counts below 5 and below 4 with a 95% Wilson interval, the paired
  change per position, QC pass rate, grounding rate and completion length against the old
  position rows.
- Every row scoring factual 3 or lower is checked against the board with python-chess and
  marked a real error or a judge miss, as before.

## Reading (fixed now)

- **Pass** if both hold: factual mean ≥ 4.5 (the N2 teacher gate; game rows score 4.78),
  and hand-confirmed real errors under 5% of the judged rows. Then the training set is the
  1,928 QC-passed game rows plus the QC-passed new position rows, and the old position rows
  are not used.
- **Fail:** the error kinds are reported and the next step is decided then; no fine-tuning
  starts until it is.

## Cost

About 6,400 DeepSeek calls (pilot 3: 37 calls for 33 rows), about 6h with 8 workers. Facts
blocks grow from 302 characters on average to about 1,700 (pilot 3: mean 1,680, max 2,082),
so input is about 1,070 tokens per call: roughly 6.8M input and 1.9M output tokens. 150
Opus judge calls.

## Result (8 Oct 2026): fail

**Generation.** The 146 spot-check games, run first as amended above: 487 position rows
(470 grounded), 558 calls, 0.60M input + 0.15M output tokens, about $0.70 off-peak, 7.5
minutes. QC passes 449 of 487 (92%; the old position rows 94%), median 1,244 characters.
All 150 spot-check positions were regenerated; **133 pass QC**. The 17 that fail: 11
placement flags (most name a piece on the square an engine line moves it to, the kind the
7 Oct audit found false), 5 ungrounded, 1 role inversion. The old 150 all passed QC by
construction (they were drawn from QC-passed rows).

**Judge** (`claude-opus-4-8`, 133 rows, `data/distill/deepseek_pos_v2_judged.jsonl`):

| | New rows | Old rows, same 133 positions |
|---|---|---|
| Factual mean | **4.38** | 4.18 |
| Factual counts (2/3/4/5) | 4 / 8 / 54 / 67 | 6 / 19 / 53 / 55 |
| Below 4 | 12 (9.0%) | 25 (18.8%) |
| Overall | 4.76 | |

Paired change per position (new minus old): −3: 1, −2: 4, −1: 26, 0: 51, +1: 42, +2: 5,
+3: 4. Better on 51, worse on 31.

**Board check of the 12 rows at 3 or lower:** 10 real errors, 2 judge misses.

| Row | Factual | Verdict | What is wrong |
|---|---|---|---|
| #84 p14 | 2 | real | "winning the queen for a pawn and a bishop" leaves out the knight cxb5 takes; "removes the pressure on your b5 knight" (it is captured). The judge's "mutual queen trade" is also wrong. |
| #397 p35 | 2 | real | "you were already better" at −3.1 |
| #590 p14 | 2 | real | the bishop that took on a3 came from d6, not a6; "slightly better position" at −1.7. The judge's reason (an even trade) is wrong: the row says bishop for a pawn. |
| #1599 p21 | 2 | judge miss | the knight on d7 did defend f8 (3 → 2 defenders is right). The causal story is weak (Bxf8 was possible before), but nothing stated is false. |
| #305 p18 | 3 | judge miss | "up material or holding a solid position": material is 31–30, so true as worded; the rest is interpretation. |
| #666 p28 | 3 | real | "clearly winning position for you" and "remain clearly better" at −5.5. (Qe7 does defend f6; the judge is wrong there.) |
| #987 p5 | 3 | real | "the queen on e7 blocks your f8-bishop": the bishop is on c5 |
| #1053 p14 | 3 | real | "attack the rook" (a bishop on f2 attacks no rook); "clearly better" at −2.1 |
| #1092 p16 | 3 | real | "the engine says that would have left you clearly better" at −1.2 |
| #1256 p10 | 3 | real (borderline) | "f5 supports your e5-pawn": a pawn on f5 does not defend e5 |
| #1677 p21 | 3 | real | "capture your d5 pawn with check" (22.Rxd5 is not check); "Kd7 removes the sting from any check on d5" (in that line Rxd5+ is check) |
| #1690 p31 | 3 | real | "your rook on g1 still pinned to the king" (nothing pins it); "you were down a pawn" at 28–27 |

**Confirmed errors: 10 of 133 = 7.5% (95% Wilson interval 4.1–13.3%)**, 6.8% without the
borderline row. Counting the 17 unjudged positions as clean gives 10 of 150 = 6.7%
(3.7–11.8%); the old rows were 8 of 150 = 5.3% (2.7–10.2%). As before, rows scored 4 were
not hand-checked, so these are lower bounds.

**Reading.** Both conditions fail: factual mean 4.38 < 4.5, and confirmed errors 7.5% ≥ 5%.
No further rows are generated and no fine-tuning starts until the next step is decided.

**What changed in the errors.** The board removed the old kind (what a capture took, which
piece stood where): only #987, #590 and #1690 misplace or misdescribe a piece, against all 8
before. The judge's low scores halved. The new dominant error is the **evaluation's sign**:
5 of the 10 (#397, #590, #666, #1053, #1092) tell a losing student they were better, though
the facts say "+ favours you" and give a negative number. That line was added in pilot 3 and
was not in the old facts. Two more (#84, #1677) misread an engine line.
