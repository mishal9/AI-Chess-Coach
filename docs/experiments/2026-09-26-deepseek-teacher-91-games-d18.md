# DeepSeek-V4 Pro as coach on the 91-game held-out set, depth 18 (N2 teacher gate)

**Report:** `eval/reports/deepseek_v4_pro_d18_2026-09-26.json`
**Run:** `python -m training.n2_eval --max-judge-calls 91 --resume --out <report>`

Same settings as the 25 Sep 29-game run: `deepseek-v4-pro`, temperature 0, thinking off,
v2-era prompt, Opus judge (`claude-opus-4-8`). What changed: 91 games instead of 29,
Stockfish depth 18 instead of 15 (Stockfish 18), and depth-18 bucket labels.
Cost: 91 DeepSeek calls (49.7k input + 35.9k output tokens) and 91 Opus judge calls.

## Headline

| | All 91 | Label-stable 73 | Original 29 | New 62 |
|---|---|---|---|---|
| Factual correctness | **4.74** | 4.77 | 4.72 | 4.74 |
| Clarity | 5.00 | 5.00 | | |
| Actionability | 4.36 | 4.37 | | |
| Identifies key mistake | 4.97 | 4.97 | | |
| Overall | 4.77 | 4.78 | 4.74 | 4.78 |
| Grounding mean | 0.98 | 0.97 | | |
| Claims clean (checker) | 92% (84/91) | 94% | 28/29 | 56/62 |

Factual by depth-18 bucket: clean_draw 4.40 (5), slow_loss 4.50 (12), inaccuracies 4.89
(19), two_mistakes 4.78 (18), one_blunder 4.79 (19), multi_blunder 4.81 (16),
unsorted 4.00 (2).

The label-stable subset matches the full set, so bucket-label instability does not drive
these numbers.

## Every claim-checker flag, read by hand

Each flag was checked by replaying the game with python-chess.

| Game | Flagged text | Verdict | Judge factual |
|---|---|---|---|
| `slow_loss` #16 | "taking the bishop on c5" | **Real error.** c5 held a pawn. | 5 (missed) |
| `slow_loss` #14 | "keeping the bishop on f4" | **Real, minor.** The bishop went to h4 from g5; it never stood on f4. | 5 (missed) |
| `inaccuracies` #2 | "the queen on e2 would have been more harmonious" | False positive: hypothetical about the engine's move | 5 |
| `two_mistakes` #10 | "pointing the knight at f7 and h7" | False positive: squares targeted, not occupied | 4 |
| `two_mistakes` #13 | "getting the bishop to e7" | False positive: advice about a future move | 4 |
| `slow_loss` #12 | "After White played 7.Nxe4" | False positive: White played 7.Ngxe4; the checker matched it to Black's engine-preferred Nxe4 | 4 |
| `multi_blunder` #5 | "When your opponent has a pawn on d5 or e5" | False positive: general advice | 5 |

Checker precision on this run: **2 of 7 flags are real (29%)**. Every false positive comes
from hypothetical, advisory or general wording ("would be", "pointing at", "getting to",
"when your opponent has"), plus one SAN-disambiguation mix-up. The earlier 0/467 false
positives were measured on Opus teacher rows; DeepSeek's phrasing hits cases those rows
did not.

## Errors the checker missed and the judge caught

| Game | Error | Judge factual |
|---|---|---|
| `slow_loss` #1 | "traded a bishop for a pawn": 13.Bxf5 took a bishop and 14...gxf5 recaptured, so bishop for bishop | 2 |
| `clean_draw` #3 | Coached side won 1-0, but the coaching says they were "slowly bleeding position" and "defending a slightly worse position" | 2 |
| `one_blunder` #15 | Invented tactical narrative around the decisive 27.Rb7 (judge: "speculation not grounded in the provided facts") | 3 |

Both of the first two games scored factual 5 in the depth-15 run. At depth 18 the facts
differ slightly, DeepSeek wrote different text, and it contained the error.

## Reading

- **Factual gate (≥ ~4.5): passed**, 4.74 on 91 games and 4.77 on the stable 73.
- **Zero-claim-violation gate: failed as scored** (7 flagged games), but only 2 flags are
  real. Counting every confirmed factual error from either source, DeepSeek made **4 clear
  factual slips in 91 games** (slow_loss #1, #14, #16; clean_draw #3), plus one invented
  narrative (one_blunder #15).
- **The checker and the judge catch different errors.** The judge missed both real
  checker hits; the checker missed all three judge-caught errors. Neither is sufficient
  alone, which supports keeping both in `training/qc.py` and in the paper.
- **The original 29 games dropped from 5.00 (depth 15, 25 Sep) to 4.72 (depth 18).** The
  new 62 games score the same as the old 29, so the drop is not from harder games. It
  comes from different coaching text (the facts changed with depth) and possibly from
  judge drift between sessions. The planned drift check (re-judging the 25 Sep texts
  against their own depth-15 facts) separates the two.
- **Checker fix needed before its numbers go in the paper:** hypothetical and advisory
  phrasing should not count as a placement claim, and move matching should respect SAN
  disambiguation and the side to move.

## Decision needed

Whether DeepSeek passes N2 depends on how the zero-violation criterion is read. As
written it fails; on confirmed errors it has a ~4% slip rate that the row-level QC filter
(`training/qc.py`: grounding, claims, structure) would partly remove. See `PLAN.md` N2.
