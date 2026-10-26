# Audit: what the grounding metric cannot see, and what it wrongly sees

**Date:** 2026-08-11 · **Status:** steps 1–2 done (#41 §9, #43 §10); step 3 = board-state checker (§3c) · **Cost:** $0 (offline re-analysis and re-scoring of stored reports, no engine, model or judge)

For two fine-tune iterations, `eval/grounding.py` has been the cheap, deterministic instrument
steering this project: it gates the training data, it justified the v2 dataset design, and it
is one of the two release gates. This audit reads it against the paid judge on the same 29
games and finds **it is wrong in both directions at once**: it is blind to the dominant factual
failure mode, and ~90% of what it does flag is a parser false positive.

**Neither error was visible in the aggregate numbers.** Both surfaced only from reading the
judge's per-game rationales, which had been stored in every report since PR #9 and never read.

---

## 1 · How this surfaced

The v2 result was internally strange: **grounding 0.91 (gate 0.85 ✅) but factual 3.72 (gate
4.0 ✗)**. The recorded interpretation was that the remaining gap was *concentrated* in two
buckets, `one_blunder` (factual 3.20) and `inaccuracies` (3.40), so iteration 3 was scoped
to buy more teacher-written position rows for those two profiles.

Before spending, I read the `rationale` field the judge writes for every game. That field
explains *why* a score was given. It had never been inspected; only the numeric scores were
aggregated.

The rationales do not support the plan they were used to justify.

## 2 · The two metrics are only weakly related

Across the 29 held-out games of the v2 run:

| statistic | value |
|---|---|
| Pearson *r* (grounding, factual) | **+0.390** |
| Spearman ρ | **+0.453** |
| variance in factual explained by grounding | **~15%** |
| games at perfect grounding (1.00) | **18 / 29 (62%)** |
| factual scores *among those* perfectly-grounded games | 2, 2, 4×12, 5×4 (**range 2–5**) |

Two games score **grounding 1.00 and factual 2**. The metric that gates the dataset and one of
the two release gates explains about a seventh of the variance in the quality it is proxying,
and 62% of games now sit at its ceiling, so it has almost no headroom left to discriminate. That
is the mechanical reason grounding cleared its gate while factual stalled: **it saturated.**

## 3 · Blind spot: grounding checks vocabulary, not claims

`score_grounding` extracts the set of moves a coaching text mentions and checks membership
against the facts block. It never checks *what is asserted about* those moves. Every failure
below uses only legitimate, in-facts moves, so grounding sees nothing wrong.

Seven games scored factual ≤ 3. Their rationales fall into three classes, all invisible to
grounding.

### 3a · Role inversion: played move ↔ engine-preferred move swapped

| bucket | factual | grounding | judge's finding |
|---|---|---|---|
| one_blunder | 2 | **1.00** | *"claims '13.Qd2 instead you castled'"* — Qd2 **is** the played move |
| one_blunder | 2 | 0.86 | *"fabricates 'When you played Nf3 or g3 instead'"* — g3 was the **engine's** preference |
| inaccuracies | 2 | 0.71 | *"says the player 'chose a passive rook move (Rc8)'"* — player played Bc6; **Rc8 was the engine's** |
| multi_blunder | 2 | **1.00** | *"the 12.Bc4 vs Bxc6 advice is inverted: Bxc6 was preferred"* |

The facts block gives the model two moves per flagged mistake (what you played, what the
engine wanted), and it loses track of which is which. Grounding scores this 1.00 because both
moves are on the sheet.

### 3b · Move-type misreading: the model misreads what a move *is*

| bucket | factual | grounding | judge's finding |
|---|---|---|---|
| multi_blunder | 2 | **1.00** | *"29.Kh1 is 'King h1', not castling — the coach repeatedly describes moves as 'castling king-side'"* |
| two_mistakes | 2 | 0.67 | *"invents 'you castled on the kingside early'"*; *"Kg7 vs Kh8 is a king move, not a castling"* |

This is a chess-semantics failure, not bookkeeping: the model sees a king move to the h-file
or g-file and pattern-matches it to castling, because in its pretraining text those co-occur.
`Kh1` is a real move, present in the facts, so grounding is satisfied.

### 3c · Invented board state and narrative

| bucket | factual | grounding | judge's finding |
|---|---|---|---|
| slow_loss | 3 | 0.80 | *"calls Qxe4 a 'queen trade' and Nxd5 a 'pawn grab,' and invents positional narratives"* |
| inaccuracies | 3 | 0.67 | *"describes Qd2 as 'passive giving up initiative'… says White got 'the result' when White actually lost (0-1)"* |

The facts block contains moves, qualities, centipawn losses and win probabilities. It contains
no piece placement, no plans, no motivations, and the model invents them. It also contradicted
the game **result**, a field it was given.

## 4 · Over-fire: the bare-square false positive

Chess notation names a move as piece letter + destination (`Nf3`), **except pawn moves, which
are the bare square** (`e4`). So `_SAN_RE` must accept a bare square as a move candidate:

```python
r"|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?)"   # piece letter optional
```

Consequently ordinary English (*"your rook on b7"*, *"control of the e5 square"*) parses as a
claimed pawn move and, being absent from the facts, is scored as a hallucination.

| report | flagged "hallucinations" | of which bare squares |
|---|---|---|
| baseline_29g_2026-07-10 | 32 | 27 (**84%**) |
| 8b_v1_2026-08-08 | 49 | 46 (**94%**) |
| 8b_v2_2026-08-10 | 17 | 16 (**94%**) |

The same parser gates the training data, where it is costlier:

> **64 of the 64 rows dropped by the v2 distillation gate failed on bare squares alone**
> (56 position rows, 8 whole-game rows). Not one was dropped for inventing a move.

Those are paid Claude Opus generations, discarded for using the word "b7". It also plausibly
explains the gate-rate gap by move type, since positional coaching names squares more often:

| position row type | gate pass rate |
|---|---|
| blunder | 59/65 = **91%** |
| mistake | 58/69 = **84%** |
| inaccuracy | 157/196 = **80%** |

## 5 · One sentence containing both failures

From the v2 coaching on the game flagged for `b7`/`b8`:

> *"The most costly moment came on **12...Rb8**. You moved your rook from b7 to b8, but the
> engine preferred **Bc6**…"*

The model wrote correct notation (`Rb8`) and then restated it in plain English for the reader.
Parsing that sentence:

- **`Rb8`**: correct, on the facts sheet. Counted correctly.
- **`b8`**: the destination, restated in prose. Counted a **second time** as a phantom *pawn*
  move to b8, absent from the facts → flagged. `Rb8` and `b8` are different moves in notation,
  so the checker cannot know they are one event. **Pure false positive.**
- **`b7`**: flagged as a phantom pawn move. Also a false positive *as notation*, but the
  claim itself is ungrounded. The facts say *"you played Rb8"*; they never say where
  the rook stood beforehand. The model invented it, and the judge caught it independently:
  *"invents piece placement (rook from b7 to b8) not given in facts."*

So the checker flagged `b7` **for entirely the wrong reason and still landed on a real defect.**
This is the sharpest lesson in the audit: fixing the parser (§7 step 1) will make this game look
clean unless the claim-checker (step 2) is built to catch the invention that the parser was
accidentally catching.

## 6 · What this revises

**The "concentrated weakness" reading was noise.** The 7 low-factual games are spread across
**five of six buckets**, not the two the bucket means implied: one_blunder (2), inaccuracies (2),
multi_blunder (1), two_mistakes (1), slow_loss (1). With n=5 per bucket and an integer
1–5 scale, **a single factual=2 game moves a bucket mean by 0.4**, which is the entire apparent
spread between "failing" and "passing" buckets. The per-bucket table was under-powered and
should not have been read as a targeting signal.

**The recorded iteration-3 direction was therefore wrong twice**: wrong mechanism (buying
coverage cannot fix role-binding) and wrong targeting (the buckets were not actually distinct).
It would have spent ~$4 of the binding constraint on the wrong thing.

**Part of the v1→v2 grounding gain is metric artifact.** Bare-square flags fell 46 → 16 between
v1 and v2. Some of the 0.79 → 0.91 improvement is the model learning to *stop naming squares*
(a stylistic suppression of the penalized token pattern) rather than improved citation
discipline. Direction of the gain is not in doubt; magnitude is. (§9 measures it: the corrected
v1→v2 gain is +0.075, against +0.120 under the biased parser.)

### What this does *not* invalidate

- **The judged rubric results stand.** factual 2.90 → 3.45 → 3.72 across baseline/v1/v2 comes
  from the judge, which reads the facts block directly and never touches `extract_moves`.
- **The shape-vs-volume ablation stands *as a controlled comparison*.** All four arms were
  scored by the same biased instrument, so the *ranking* (shape beats volume; mixture beats
  both pure arms) holds even though the absolute levels are inflated.
- **The clean_draw fix is real** but its magnitude (0.38 → 1.00) is the most metric-sensitive
  number in the record, since clean games have the fewest legitimate moves to cite and the
  highest prose-to-notation ratio. Re-score before quoting it.

## 7 · Scoped fixes

| step | work | cost |
|---|---|---|
| **1** ✅ | Context-aware bare-square handling in `extract_moves`; re-score all three stored reports offline — the coaching text is saved, so no model and no judge is needed; re-run the gate over `raw_v2.jsonl` to recover the wrongly-dropped rows. **Done — PR #41, results in §9.** | **$0** |
| **2** ◑ | A deterministic **claim checker**: (a) role binding — verify a move described as played is the played move and one described as preferred is the engine's; (b) move-type — verify king/rook/pawn language matches the actual piece; (c) board state — replaying the PGN gives the true position at every ply for free, so "rook on b7" and "you castled early" are both checkable without a model. Add to the eval **and** to the distillation gate, where `--retries` (86% observed recovery) can re-roll the teacher's own swaps. **(a) and (b) done — PR #43, results in §10. (c) not done, and §10 shows it is where the residual gap lives.** | **$0** |
| **3** | Retrain on the recovered dataset; grounding-only eval first (free), then the judged pass (~29 calls). Capture cell-6 `eval_loss` — still never captured, so 3-epoch overfit remains unruled-out. | ~$0.40 GPU |
| **4** | Targeted teacher spend — **only if step 3 shows the claim checker still failing**, which would be genuine evidence the data lacks role-contrast examples. | ~$1.50–4 |

## 8 · Threats to validity

- **Single judge, single seed.** Every rationale here is claude-opus-4-8's opinion. The judge
  could itself be wrong about specific chess claims; I verified the role-inversion cases against
  the facts blocks by hand, but not the positional characterizations in §3c.
- **n=29, and the sub-classes are small.** Four role inversions and two move-type misreadings
  are enough to establish the classes exist and are invisible to grounding; they do not
  establish their relative frequency.
- **The §4 counts are of *flagged* tokens, not of true hallucinations.** A bare square can be a
  genuine invented pawn move; the 84–94% figures are an upper bound on the false-positive rate,
  and step 1 must not simply discard bare squares.
- **"Recover ~64 rows" is an estimate** until the corrected parser is actually run over them.

## 9 · Step 1 result (PR #41, merged 2026-08-12)

### The rule that shipped is not the rule that was scoped

§7 proposed an allowlist: count a bare square as a move only in a recognised move context
(move number, annotation, or an adjacent cue verb like "preferred"). **Built first, and
rejected** — it dropped 47 genuine citations across the 29 v2 games, because coaching cites
moves in far more shapes than an allowlist can hold: *"g4 preserved the initiative"*, *"d3 is
passive"*, *"why did g6 fall short?"*.

Locational phrasing, by contrast, is a short and stable list. So the default inverted: a bare
square **is** a move unless the adjacent words make it a location — a location preposition
before it, a noun it qualifies after it, or coordination inheriting a preposition ("on f3 and
f6"). Notation is tested first, so `"came on 12...e5?!"` survives the "on".

Every remaining dropped occurrence was inspected by hand: 14 of 15 were unambiguous locations,
and the one false negative — *"the key idea **behind** e5"*, where the preposition is
metaphorical — was fixed by removing `behind` from the list.

### Corrected scoreboard

Exact, not estimated: facts-side extraction is provably unchanged (**0 of 1367** allowed-move
tokens differ across the v2 distillation set), so the allowed set is stable and the diff can be
recomputed from each committed report.

| report | old | **corrected** | Δ | grounded games |
|---|---|---|---|---|
| baseline_29g (prompted 3B) | 0.812 | **0.861** | +0.049 | 16/29 → 20/29 |
| 8b_v1 | 0.787 | **0.890** | +0.103 | 12/29 → 20/29 |
| 8b_v2 | 0.907 | **0.965** | +0.058 | 18/29 → 25/29 |

Two conclusions in the existing records are overturned:

- **v1 never regressed grounding.** The biased parser placed v1 (0.787) *below* the prompted
  baseline (0.812) — recorded at the time as a puzzle, and part of the motivation for the v2
  dataset. Corrected, v1 is **above** it (0.890 vs 0.861). The regression was an artifact of
  v1 naming squares more often (46 bare-square flags vs the baseline's 27).
- **The 0.85 grounding gate was already met by the prompted baseline** (0.861). It was
  calibrated against a biased instrument, and every "gate met / not met" judgement made against
  it needs re-deriving. Note the saturation this implies: 25 of 29 games now sit at 1.00, so
  grounding has even less headroom to discriminate than §2 measured.

### Recovered training data

Re-running the strict gate over `raw_v2.jsonl` recovers **52 of the 64 dropped rows** — 403 →
455 gated (+12.7%) at **zero teacher cost**. The 12 that still fail split two ways, and only
one way is error:

- **Genuine out-of-facts citations** the metric *should* catch — the model reaching for opening
  theory that was never in the facts block: *"in the Scotch, when White plays d4…"*.
- **A residual false-positive class**: illustrative squares in constructions the rule does not
  cover, e.g. *"a more advanced square (like d6)"*, *"knights to c6/f6-type squares"*.
  Documented rather than chased — tightening further risks over-fitting the rule to this corpus.

### Infrastructure closed off

The re-score above needed the allowed set reconstructed by hand, because reports stored only
`score`/`grounded`/`hallucinated`. Two changes so this is never hand-work again:

- `eval.run` now persists `cited` and `allowed`, making any future metric change re-scorable
  from a committed report alone.
- `eval/rescore.py` re-scores committed reports offline. Its `--verify` pass (default on)
  re-derives each stored score from the stored fields and **refuses to run** if any disagrees,
  so a report written under a different metric cannot be silently mis-scored.

## 10 · Step 2 result (PR #43, merged 2026-08-13)

`eval/claims.py` checks the assertions grounding is blind to: **role inversion** (§3a) and
**invented castling** (§3b). Board state and narrative (§3c) are not covered — see below.

### Precision cost three drafts, and the teacher caught two of them

The checker gates training data, so a false positive is worse than a miss. Each draft was
killed by data rather than by reasoning:

| draft | rule | killed by |
|---|---|---|
| 1 | cue immediately adjacent to the move | missed *"you chose a passive rook move (Rc8)"* — a real §3a failure |
| 2 | nearest cue in a window, stopping at an intervening citation | flagged **8.4% of the teacher's own rows** |
| 3 | **shipped** — see below | — |

Draft 2's number is the useful one. Claude Opus does not invert roles in 8% of its output,
so the failures had to be the checker's: *"the engine wanted you **to play** Bxc3"*, *"by
**not playing** f5"*, *"the chance **to play** b5"* are recommendations and negations, not
claims about what happened. **Running a candidate metric against known-good output is what
made that visible** — the same move that would have caught the bare-square bug two
iterations earlier.

The shipped rule: a cue asserts a role only when its **agent is named beside it** ("you
played", "the engine preferred"), only in the **past tense** (the present is generic advice
— *"when you play 3...exd4, you win a pawn"* describes a line, not this game), never across
a clause boundary, and never past another citation — which is what stops *"the engine
preferred Nh5 instead of Re8"* from reading Re8 as engine-preferred. Castling likewise
requires an assertion ("you castled"), not a mention: *"you played d4 instead of castling"*
and *"work on castling first"* are correct English about a player who never castled, and
draft 2 flagged both — on a **factual=5** game.

### Precise, and honestly partial

| set | flagged | |
|---|---|---|
| teacher rows (claude-opus-4-8) | **0 / 467** | precision check |
| 8b_v2 | 1 | `role_inversion:g3`, on a factual=2 game |
| 8b_v1 | 0 | |
| prompted 3B baseline | 2 | on factual=1 and factual=2 games |

Every violation lands on a game the judge scored 1–2, with no false positives anywhere.

**But recall is low: the judge faults 7 games and this flags 1.** The two checks cover the
structurally explicit errors; the remainder is §3c — invented board state and narrative
(*"your rook on b7"*, *"a pawn grab"*, *"you castled early"* where the player did castle but
at another moment). That is where the residual factual gap actually lives, and it needs
position replay from `fen_before`.

So the claim checker is a **precise partial instrument**: sound enough to gate distillation
with (0/467 on teacher output), and a useful regression signal, but **not** a replacement
for the judge. Anyone reading `claims_ok_rate` should read it as a floor on assertion
errors, never as an estimate of factual quality.

### Two persistence gaps, both found by trying to validate

Validation needs to join stored coaching back to the game it scored, and could not:

- **`eval.run` never recorded `game_index`.** Bucket files hold ~5 games each, so `pgn`
  alone never identified a game. The first validation pass silently joined every game to
  index 0 and reported zero recall; the real numbers above came from re-joining on exact
  reproduction of each stored grounding score (24 of 29 join unambiguously).
- **`load_partial` keyed on `(pgn, coached_side)`** — so one finished game marked its
  file-mates done and **`--resume` silently skipped them**. A live correctness bug in the
  resume added in #35, not a test artifact.

Both are the same defect as the missing `cited`/`allowed` in §9: the report did not record
enough to check the work later.

## 11 · Transferable lessons

1. **A cheap proxy metric earns trust only where it has been checked against the expensive one.**
   Grounding was never validated against the judge on a per-game basis; it was assumed to be a
   conservative lower bound on quality. It was neither conservative nor a bound: *r* = 0.39.
2. **Set-membership is not entailment.** Checking that the tokens are real is a much weaker
   claim than checking that the sentences are true, and the gap between them is exactly where a
   model trained against the metric will settle.
3. **Optimizing against a saturating metric buys style, not substance.** Once 62% of games sit
   at 1.00, further "gains" come from suppressing whatever surface pattern the metric penalizes.
   The model learned to avoid the word "b7."
4. **Per-group means over n=5 with an integer scale are decoration.** One game moved a bucket
   mean by 0.4 and nearly redirected ~$4 of a hard-constrained budget.
5. **The qualitative field was in the artifact the whole time.** Every rationale had been
   written, stored and committed since PR #9. Two iterations of aggregate-only reading missed a
   metric bug that a single afternoon of reading the free-text found.
6. **Free diagnostic work should precede paid corrective work.** Here the free work may
   turn out to have been the whole fix.

## 12 · Reproduction

All offline: no engine, no model, no judge. Requires only the committed reports and
`data/distill/raw_v2.jsonl`.

```bash
# corrected scoreboard (§9)
python -m eval.rescore eval/reports/baseline_29g_2026-07-10.json \
                       eval/reports/8b_v1_2026-08-08.json \
                       eval/reports/8b_v2_2026-08-10.json
```

The numbers behind §2, §4 and §6 come from the committed reports directly:

| claim | where it comes from |
|---|---|
| decoupling, *r* = +0.39 (§2) | correlate `games[].grounding.score` with `games[].rubric.scores.factual_correctness` |
| per-bucket spread (§6) | join `games[].pgn` to `bucket` in `eval/heldout/manifest.json` |
| bare-square share, 84–94% (§4) | filter `games[].grounding.hallucinated` with `^[a-h][1-8]$` |
| gate cost, 64/64 (§4) | rows in `raw_v2.jsonl` with `quality.grounding < 1.0` whose every `quality.hallucinated` entry matches `^[a-h][1-8]$` |
| rows recovered, 52 (§9) | re-run `eval.grounding.extract_moves` over those rows' `completion` |

The failure classes in §3 are read from `games[].rubric.rationale`, present in every
`eval/reports/*.json`.
