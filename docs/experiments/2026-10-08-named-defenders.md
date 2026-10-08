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
