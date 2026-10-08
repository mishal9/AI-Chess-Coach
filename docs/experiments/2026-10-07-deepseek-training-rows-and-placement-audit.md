# DeepSeek training rows, QC, and a hand audit of the placement flags

**Status:** rows generated 27–28 Sep 2026; QC and audit 7 Oct 2026. The filter decision is
open (see the end).

## The run

- Source: the 2,000-game training corpus (`data/games/manifest.json`, built by
  `training.corpus --from-db 2023-09:2026-08 --canonical-seed 0`). No held-out games.
- Teacher: `deepseek-v4-pro` via DeepSeek's API, thinking disabled. First attempt at
  temperature 0, the setting the N2 gate scored
  (`2026-09-26-deepseek-teacher-91-games-d18.md`). A row that fails strict grounding is
  re-rolled once at 0.7. Each row records `teacher.temperature` and `quality.attempt`.
- Stockfish 18 at depth 18, analysis cached. One whole-game row plus up to 4 position rows
  (worst mistakes first) per game.
- Command (a 10-game pilot first, then the rest with `--resume`):

```
python -m training.distill --sources data/games/manifest.json --teacher deepseek \
    --teacher-thinking disabled --workers 8 --retries 1 --positions-per-game 4 \
    --resume --out data/distill/raw_deepseek.jsonl --max-teacher-calls 20000
```

| | |
|---|---|
| Games | 2,000, no failures |
| Rows | 7,669 (2,000 game, 5,669 position) |
| From the first attempt (temperature 0) | 7,263 |
| From a retry (temperature 0.7) | 406 |
| Grounded | 7,556 |
| DeepSeek calls (main run, pilot excluded) | 8,096 |
| Tokens (main run) | 4.89M input, 2.21M output, 0 reasoning |
| Model reported by the API | `deepseek-v4-pro` on every call |
| Wall time | 6h08m with 8 workers (pilot 5m) |

## QC

`python -m training.qc data/distill/raw_deepseek.jsonl --passed-out data/distill/deepseek_qc.jsonl`

| | Pass | |
|---|---|---|
| All | 7,234 / 7,669 | 94% |
| Game rows | 1,928 / 2,000 | 96% |
| Position rows | 5,306 / 5,669 | 94% |

Reasons a row failed (a row can fail more than one check): invented placement 286 flags in
273 rows, ungrounded 113, chat preamble 50, role inversion 5, invented castling 2. Integrity
failures 0 (no held-out game, no duplicate completion, facts always inside the prompt).

The 50 "chat preamble" rows open with "Here's what happened…" or "Here's the moment…",
which the structure check's `here's` pattern matches. They read as ordinary coaching
openers. They are dropped and not audited further.

## Audit of the placement flags

The placement rate (273 of 7,669 rows, 3.6%) is far above what the checker found on
DeepSeek's held-out coaching (2 flags in 91 games after checker v2). So a random 50 of the
273 flagged rows were read by hand (seed 20261007; keys in the table).

A flag was counted **real** when the text asserts that a piece stood on a square in the
game and it never did. It was counted **false** when the text describes where a piece
*would* go: in every false case, the square is the destination of the engine-preferred move
being explained ("Qd3, by contrast, develops… The queen on d3 often eyes…").

**Result: 14 of 50 real (28%; 95% Wilson interval 18–42%), 36 false.** Scaled to all 273
flagged rows, roughly 76 hold a real misplacement and roughly 197 are sound rows.

The 14 real errors are of four kinds:

- **Wrong piece on a capture square** (5): the engine prefers a capture and the text
  names the wrong captured piece. "Black's most dangerous piece — the bishop on f3.
  Capturing it with Bxf3" (#15); "grabbing the pawn on b4 with your queen" (#47); "your
  opponent had just pushed a pawn to g4" (#35); also #1, #20.
- **Wrong owner** (2): "you left your bishop on e2 alone" when the bishop on e2 was
  White's (#48, #50).
- **Recommended square read as the current one** (4): "the engine preferred keeping the
  queen on g2" when the queen had never been on g2 (#9, #14); "the rook on e1 was the
  piece crying out for action" (#11); "The queen on f8 is that piece" (#25).
- **Invented piece** (3): a rook on d8, a knight on d3 and a pawn on b5 that never existed
  (#18, #10, #29).

### Would a narrower checker do better?

One candidate fix: skip a placement claim when its piece and square are the destination of
a non-capture engine-preferred move in the facts. Measured, not adopted:

- On the 50: 14 still flagged, of which 10 are real (precision 71%). The 4 real errors of
  the "recommended square read as the current one" kind (#9, #11, #14, #25) are let
  through, and 4 false flags on capture moves (#6, #23, #27, #28) remain.
- On all 273: 84 still flagged, so about 189 rows return to the set, including an
  estimated 20–25 rows with a real error.

### Per-row verdicts

| # | Row | Claim | Verdict |
|---|---|---|---|
| 1 | corpus.pgn#907 game | a bishop on f3 | real: wrong piece on capture square |
| 2 | corpus.pgn#1303 pos 33 | a queen on a6 | false: preferred Qa6 |
| 3 | corpus.pgn#363 pos 8 | a queen on d3 | false: preferred Qd3 |
| 4 | corpus.pgn#1098 pos 33 | your pawn to h5 | false: preferred h5 |
| 5 | corpus.pgn#442 pos 13 | a queen on b4 | false: preferred Qb4 |
| 6 | corpus.pgn#1062 pos 8 | a queen on e4 | false: preferred Qxe4 |
| 7 | corpus.pgn#506 pos 18 | a queen on d7 | false: preferred Qd7 |
| 8 | corpus.pgn#1844 pos 41 | your pawn on b7 | false: preferred b7 |
| 9 | corpus.pgn#405 pos 37 | the queen on g2 | real: "keeping the queen on g2" |
| 10 | corpus.pgn#1917 game | a knight on d3 | real: invented piece |
| 11 | corpus.pgn#1769 pos 30 | a rook on e1 | real: recommended square as current |
| 12 | corpus.pgn#16 pos 19 | a bishop on f5 | false: preferred Bf5 |
| 13 | corpus.pgn#768 pos 15 | a bishop on f4 | false: preferred Bf4 |
| 14 | corpus.pgn#486 pos 33 | the queen on h3 | real: "keeping the queen on h3" |
| 15 | corpus.pgn#693 pos 38 | the bishop on f3 | real: wrong piece on capture square |
| 16 | corpus.pgn#712 pos 45 | your king to d4 | false: preferred Kd4 |
| 17 | corpus.pgn#454 pos 10 | the bishop on e4 | false: preferred Be4 |
| 18 | corpus.pgn#1222 pos 26 | your rook on d8 | real: invented piece |
| 19 | corpus.pgn#1289 pos 64 | a pawn on g6 | false: preferred g6 |
| 20 | corpus.pgn#428 pos 26 | a pawn to e4 | real: wrong piece on capture square |
| 21 | corpus.pgn#1811 pos 33 | a king on a7 | false: preferred Ka7 |
| 22 | corpus.pgn#740 pos 22 | the pawn on g5 | false: preferred g5 |
| 23 | corpus.pgn#1142 pos 11 | the knight on d7 | false: preferred Nxd7 |
| 24 | corpus.pgn#951 game | a knight on d3 | false: preferred Nd3+ |
| 25 | corpus.pgn#1676 game | the queen on f8 | real: recommended square as current |
| 26 | corpus.pgn#486 pos 34 | a queen on h3 | false: preferred Qh3 |
| 27 | corpus.pgn#5 pos 29 | a queen on d5 | false: preferred Qxd5+ |
| 28 | corpus.pgn#1070 pos 29 | the queen on d4 | false: preferred Qxd4 |
| 29 | corpus.pgn#700 pos 21 | the pawn on b5 | real: invented piece (the knight on c7 claim is false: preferred Nc7) |
| 30 | corpus.pgn#511 game | the queen on c8 | false: preferred Qc8 |
| 31 | corpus.pgn#1353 pos 32 | a rook on f3 | false: preferred Rf3 |
| 32 | corpus.pgn#1051 pos 22 | a knight on h3 | false: preferred Nh3 |
| 33 | corpus.pgn#1263 pos 17 | the queen on f8 | false: preferred Qf8 |
| 34 | corpus.pgn#117 pos 29 | a queen on g2 | false: preferred Qg2 |
| 35 | corpus.pgn#446 pos 15 | a pawn to g4 | real: wrong piece on capture square |
| 36 | corpus.pgn#1766 game | your queen on b7 | false: preferred Qb7 |
| 37 | corpus.pgn#133 pos 19 | a rook on d3 | false: preferred Rd3 |
| 38 | corpus.pgn#1759 game | a bishop on e5 | false: preferred Be5 |
| 39 | corpus.pgn#1325 pos 44 | a bishop on e4 | false: preferred Be4 |
| 40 | corpus.pgn#192 game | a queen on e4 | false: preferred Qe4 |
| 41 | corpus.pgn#74 pos 16 | the queen on d7 | false: preferred Qd7 |
| 42 | corpus.pgn#35 pos 28 | a pawn on b6 | false: preferred b6 |
| 43 | corpus.pgn#94 pos 13 | a knight on d6 | false: preferred Nd6 |
| 44 | corpus.pgn#1002 game | the bishop to b8 | false: preferred Bb8 |
| 45 | corpus.pgn#59 pos 19 | the queen on c5 | false: preferred Qc5 |
| 46 | corpus.pgn#1990 pos 17 | a rook on e1 | false: preferred Re1 |
| 47 | corpus.pgn#258 pos 17 | the pawn on b4 | real: wrong piece on capture square |
| 48 | corpus.pgn#1223 pos 10 | your bishop on e2 | real: wrong owner |
| 49 | corpus.pgn#1572 pos 23 | the queen on b3 | false: preferred Qb3 |
| 50 | corpus.pgn#602 pos 12 | your bishop on e2 | real: wrong owner |

## What this means

- The checker's placement precision on training rows is about 28%, much lower than on
  held-out coaching. Position rows explain one preferred move at length, which is where
  the "a queen on d3 would…" phrasing comes from (247 of the 286 flags are on position
  rows).
- Dropping every flagged row is safe for accuracy and costs about 197 sound rows. The
  filtered set (7,234) is still larger than the biggest sweep arm (5,000 rows).
- Dropping them removes some rows that explain the recommended move's destination square.
  The same phrasing would be flagged in a student's output by the same checker, so
  training and evaluation stay consistent either way.
- A narrower checker would also change the held-out claim numbers for every coach, so any
  change belongs in `eval/claims.py` with a re-check of every report, not in training QC
  alone.

## Decision

Open. Options: keep the checker v2 filter as is (7,234 rows), or exempt non-capture
destination squares (about 7,400 rows, with an estimated 20–25 real errors let in).

## Judge spot-check of the kept rows

**Pre-registered 7 Oct 2026, before any row was judged.**

QC cannot check chess reasoning. On the held-out set the Opus judge caught 3 DeepSeek
errors the checker missed, so the kept rows are sampled and judged before fine-tuning.

- Rows: a random 200 of the 7,234 QC-passed rows (`data/distill/deepseek_qc.jsonl`),
  seed 20261007, drawn by `training.judge_rows` without regard to kind.
- Judge: `claude-opus-4-8` with the rubric in `eval/rubric.py`, the same judge and prompt
  as the held-out evaluation. Each row is judged against the facts block it was written
  from (game or position facts).
- Reported: factual-correctness mean, and the counts below 5 and below 4, overall and per
  row kind, with a 95% Wilson interval on the share below 4.
- Every row scoring factual 3 or lower is read by hand and marked a real error or a judge
  miss, as in the held-out audit.
- Reading: if the share of rows with a hand-confirmed real error is under 5%, the QC-filtered
  set goes to fine-tuning as is and the paper reports the estimate. If it is 5% or more, the
  error kinds found decide the next step (a judge filter over all rows, or a QC change), and
  no fine-tuning starts until that is settled.
- Cost: 200 Opus judge calls. One run.
