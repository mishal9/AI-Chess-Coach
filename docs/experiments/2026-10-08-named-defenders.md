# Clear-cut position rows with named defenders

**Status:** pre-registered 8 Oct 2026, before any row was generated. Code on branch
`feat/named-defenders` (stacked on `feat/clear-cut-position-rows`).

**This is a deviation.** `2026-10-08-clear-cut-position-rows.md` fixed that a fail there
means training on game rows alone, with no further position-row variant for this paper. It
failed (factual 4.55, confirmed errors 6 of 100). The user chose on 8 Oct to try one more
variant aimed at the error it found. The paper reports all five position-row versions,
including this deviation, and this is the last: the Anthropic balance (about $1.50) pays
for one more judged sample.

## Why

Four of the six confirmed errors misstated what defends what, as four of six did in the
v3 fresh sample. The facts gave defender *counts* but not *names* ("queen on d5
(attackers 1, defenders 1)"), so the teacher guessed which piece was the defender, and
guessed wrong in #828 ("the knight on c6 no longer protects the queen": d5's one defender
was the e6 pawn) and #923. Two others (#1763, #1980) contradicted counts the facts
stated.

## The change

1. **Named attackers and defenders** (commit `5b4a3d5`). `coach.prompts._under_attack` now
   writes "queen on d5 (attackers 1: knight on c3; defenders 1: pawn on e6)". The counts
   stay; "defenders 0)" is unchanged, so the clear-cut filter reads the new format as
   before (tested). Every square still follows "on", so the names license no move
   citations (tested).
2. **One prompt rule** (commit `b21cf5d`): "Say one piece defends or attacks another only
   when the facts name it as that piece's defender or attacker; a move took a defender
   away only if the facts name it before the move and not after."
3. **A QC check for defence claims** (commit `5b4a3d5`). `eval.claims.check_defence_claims`
   rebuilds the boards a position row's facts describe (before the move, after it, after
   the preferred move) and flags "X defends / protects / guards / supports Y" when no piece
   matching X covers one matching Y on any of them. It skips hypotheticals, purposes,
   negations ("no longer" is kept), passives without "by", counts ("defended only once"),
   generic subjects ("an active rook"), relocations and kings as targets (shelter, not
   coverage). `training.qc` runs it on every row as violation kind `invented_defence`.
   Whole-game facts have no board and check nothing; the held-out claim metric is
   unchanged (`METRIC_VERSION` stays 2).

   **How it was tuned, stated plainly.** It was written against all 766 v3 and v3b rows.
   A first version that also checked "hanging" flagged 47 rows, mostly false: the coaching
   uses "hanging" loosely for a piece that loses an exchange, which direct counts cannot
   settle, so that half was dropped. The final check flags 7 rows, all false claims when
   read on the board: 2 of the 12 confirmed errors of the last two spot-checks (#405
   v3, #828 v3b) and 5 rows never sampled (#907, #1138, #1237, #1595 p24 v3; #1458 v3b).
   **Its recall on the confirmed errors is 2 of 12**: most defender errors are causal
   stories ("once it left, f4 was hanging", "the piece protecting your knight") that do not
   name both pieces. It is a backstop; the named facts are the main change. Its precision
   on new rows is measured below, not assumed.

The board, captures, lines, evaluation and the clear-cut filter are unchanged. 601 tests
pass.

## Games

100 corpus games, none among the 146 spot-check games, the 10 pilot games or the 100 games
of the last run (254 between them), drawn from the other 1,746 with seed 20261010, by the
same code as `2026-10-08-clear-cut-position-rows.md` with `clearcut100.json` added to the
excluded files. Written to `data/games/named100.json`.

## Run

```
python -m training.distill --sources data/games/named100.json --teacher deepseek \
    --teacher-thinking disabled --workers 8 --retries 1 --positions-per-game 4 \
    --no-game-rows --resume --out data/distill/raw_deepseek_pos_v4.jsonl \
    --max-teacher-calls 1000
python -m training.qc data/distill/raw_deepseek_pos_v4.jsonl \
    --passed-out data/distill/deepseek_pos_v4_qc.jsonl
python -m training.clear_cut data/distill/deepseek_pos_v4_qc.jsonl \
    --out data/distill/deepseek_pos_v4_clear.jsonl
python -m training.judge_rows data/distill/deepseek_pos_v4_clear.jsonl --n 100 \
    --seed 20261010 --out data/distill/deepseek_pos_v4_clear_judged.jsonl \
    --max-judge-calls 100
```

About 330 DeepSeek calls, about $0.50 off-peak. 100 Opus judge calls at about $0.0135 each
(facts about 15% longer), about $1.35. If the Anthropic balance runs out partway, the judge
is resumed with `--resume` after a top-up; nothing about the sample or the rule changes.

## Spot-check and reading (fixed now)

As before: 100 clear-cut QC-passed rows, `claude-opus-4-8`, rubric `eval/rubric.py`, each
row against its own facts; every row at factual 3 or lower checked on the board with
python-chess and marked a real error or a judge miss; borderline counts as an error; the
95% Wilson interval is reported. Every `invented_defence` flag in the run is read and
marked true or false.

- **Pass** if both hold: factual mean ≥ 4.5 and hand-confirmed real errors under 5%. Then
  the DeepSeek account is topped up and the rest of the corpus is generated into
  `raw_deepseek_pos_v4.jsonl` with the same settings (`--sources data/games/manifest.json
  --resume`), and the training set is the 1,928 QC-passed game rows plus the QC-passed
  clear-cut v4 rows.
- **Fail:** the training set is the 1,928 QC-passed game rows alone. This is final for the
  paper: no further position-row variant.

## Cost

About $0.50 of DeepSeek (balance about $4.95) and about $1.35 of Opus (balance about
$1.50). On a pass, the remaining 1,900 games cost about $9.50 of DeepSeek, so a top-up of
about $5 comes first.

## Result (8 Oct 2026): fail; the training set is game rows alone

**Generation.** 100 games, 276 rows (249 grounded), 340 calls, 0.43M input + 0.10M output
tokens, about $0.50 off-peak, 4.6 minutes, no failures. Median facts length 1,979
characters (about 1,700 before).

**A fix after registration, before judging.** The first QC pass flagged 11 rows
`invented_defence`; reading them, most were false. Named defenders made the teacher write
"your knight on c3 defended only by the b2 pawn", which the check read as the knight
defending the pawn. Commit `1890c74` reads "defended only by" as passive, skips pronoun
objects ("protecting it") and objects past a clause break, and skips a target that is
itself the agent of an earlier "by". On the 766 tuning rows it still flags the same 7. On
v4 it then flags 1 row, a true one (#100 p22: the f2 pawn "defending the knight on g3",
which it attacks). The fix changed which rows passed QC, so the clear-cut pool and the
sample were drawn after it; the judge had not run.

QC passes 244 of 276 (88%): 5 placement flags, 1 `invented_defence`. **138 of the 244
(57%) are clear-cut.**

**Judged sample** (`claude-opus-4-8`, 100 of the 138,
`data/distill/deepseek_pos_v4_clear_judged.jsonl`): **factual mean 4.51**, counts
2 / 3 / 4 / 5 = 1 / 6 / 34 / 59, 7 below 4, overall 4.81.

**Board check of the 7 rows at 3 or lower:** 6 real errors, 1 judge miss.

| Row | Factual | Verdict | What is wrong |
|---|---|---|---|
| #202 p48 | 3 | real | "After Rxd6, you were left with just a knight against a rook": the line takes White's rook too (material 4–4) |
| #430 p25 | 3 | real | Re1 is the a1 rook (the f2 rook cannot reach e1); "on e2 it keeps an eye on your a4-pawn": a rook on e2 does not cover a4, and "the rook on f2 … was the only thing holding your queenside together" when the a1 rook was |
| #704 p22 | 3 | judge miss | "your knight on a4 became a target" after Ba7 is an overstatement (nothing attacks a4), not a false statement of the facts |
| #767 p7 | 3 | real | the e4 pawn "was part of the pressure on Black's d4 pawn": e4 does not attack d4, and the facts name d4's attackers (queen on d1, knight on f3) |
| #948 p16 | 3 | real | "Qd5 … defends your bishop on g2": the e4 pawn blocks the diagonal. The QC check skipped it ("where it defends": a pronoun subject) |
| #1162 p13 | 3 | real | "Nd7 blocked your own bishop's defense of the queen": e7 keeps both defenders (king e8, bishop f8), as the facts name |
| #1794 p6 | 2 | real | "The knight on c2 was attacking both your rook on a1 and your queen on d1": it does not attack d1; "you'd have gotten a knight and a rook for it": Qxc2 Bxc2 wins only the knight. (The judge also called "out of check" false; the knight on c2 does give check.) |

**Confirmed errors: 6 of 100 = 6.0% (95% Wilson interval 2.8–12.5%).**

**Reading.** Factual 4.51 ≥ 4.5 passes; confirmed errors 6.0% ≥ 5% fails. **Fail.** As
fixed above, the training set is the 1,928 QC-passed game rows alone, and this is final for
the paper.

**What the errors are.** Three of the six (#767, #948, #1162) still misstate what attacks or
defends what, now against facts that name every attacker and defender. Two misread an
engine line's material (#202, #1794), and one confuses which rook moved (#430). Naming the
defenders removed the guess that #828 and #923 made, but the teacher still writes past
the facts at about the same rate.

**Across the five versions.**

| | Old rows (1-line facts) | 8 Oct (board) | v3 (eval in words) | v3 clear-cut, new games | v4 named defenders, clear-cut, new games |
|---|---|---|---|---|---|
| Factual mean | 4.18 (same 133) | 4.38 (133) | 4.44 (fresh 100) | 4.55 (100) | 4.51 (100) |
| Confirmed errors | 8 / 150 = 5.3% | 10 / 133 = 7.5% | 6 / 100 = 6.0% | 6 / 100 = 6.0% | 6 / 100 = 6.0% |

Each change removed the error it targeted (misplaced pieces, the evaluation's sign, the
guessed defender), and the rate stayed between 5% and 8%: new kinds of over-reach take
their place. The paper reports this as the finding about position rows: with this teacher
and prompt shape, richer facts raise the judged score but do not bring confirmed errors
under 5%. Game rows, which summarise a game rather than explain one position, met the bar
in their sample (factual 4.78, no confirmed errors in 50).

The `invented_defence` check stays in QC: its 8 flags on 1,042 position rows were all
true, and it costs nothing on game rows, whose facts have no board.
