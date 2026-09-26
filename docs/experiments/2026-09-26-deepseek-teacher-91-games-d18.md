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

## Claim checker v2 (same day)

The audit above found five false-positive patterns. `eval/claims.py` METRIC_VERSION 2 fixes
them, each with a regression test in `tests/test_eval_claims.py`:

- a role claim naming the opponent ("After White played 7.Nxe4") is not checked against
  the coached side's roles, which a SAN collision can otherwise match;
- placement claims followed by a modal ("the queen on e2 **would** have been…") are
  hypothetical;
- a piece pointed **at** a square is a target, not a placement ("pointing the knight at f7");
- conditional general advice ("**When** your opponent has a pawn on d5…") is skipped;
- -ing advice verbs count as advice ("**getting** the bishop to e7"). "keeping" is
  deliberately excluded: "the engine preferred keeping the bishop on f4" asserts the
  bishop was on f4, and that is one of the two real errors.

**Before and after, on every stored report** (v1 and v2 run on the same coaching text and
the same analysis):

| Report | v1 flags | v2 flags |
|---|---|---|
| deepseek_v4_pro_d18_2026-09-26 | 7 | **2** |
| baseline_29g_2026-07-10 | 6 | 5 |
| abl_pos_only_2026-08-10 | 3 | 2 |
| 8b_v1, 8b_v2 (both judges) | 2 each | 2 each |
| deepseek_v4_pro_2026-09-25, prompted_8b (both judges) | 1 each | 1 each |
| **Total** | **25** | **18** |

- **7 flags removed, all false positives:** the 5 DeepSeek ones above, plus two older
  hypotheticals ("the queen on d7, which would have been more advantageous", where Qd7 was
  the engine's move; "A rook on e1 would have been much more active").
- **0 flags added.** Every change only skips a pattern, so v2 cannot flag anything v1
  did not.
- **Both real DeepSeek errors are still caught** (`slow_loss` #14 and #16).
- **Opus teacher rows (604, v1 + v2 datasets): 0 role flags under v1 and v2.**

On the DeepSeek report, precision on the hand-audited flags goes from 2 of 7 to **2 of 2**.
The report was re-scored in place with checker v2 (`metric_versions.claims` = 2): claims
clean 92% → **97.8%** (89/91), label-stable subset 98.6% (72/73). Rubric scores are
unchanged.

`eval.recheck`'s CLI refuses this report: its alignment check replays grounding with the
pre-#41 parser, so it only accepts reports written before #41. The re-score used
`recheck.recheck_report` directly, after checking that every game joins to its manifest
entry by file, index and side.

Recall is unchanged and still low. The three judge-caught errors (`slow_loss` #1,
`clean_draw` #3, `one_blunder` #15) are a wrong capture, a wrong game outcome and an
invented narrative, none of which the checker models.

## Decision (2026-09-26)

**DeepSeek-V4 Pro passes the N2 teacher gate** under this reading: factual ≥ 4.5 (4.74 on
91, 4.77 on the stable 73), and every **confirmed** claim violation audited. The
"zero claim violations" criterion was written when the checker had shown no false
positives on teacher text (0/467 on Opus rows); on DeepSeek text v1 did not hold that.
With v2, 2 of 91 games are flagged and both are real. Rows the checker flags are dropped by
`training/qc.py` during data generation, and checker v2 stops that filter from discarding
correct rows for hypothetical wording.
