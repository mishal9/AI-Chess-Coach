# Phase 5 — Memory layer (CLI milestone)

**Decided 2026-08-20.** Park the eval work; build the thing that makes this feel like a coach.

## Why we're pivoting

`eval/` is 2221 LOC against `coach/`'s 417. The measurement apparatus outgrew the product.
The prompted-8B control (2026-08-14) showed the fine-tune matches its own base model on judged
quality — a real result, and a good place to stop rather than spend the remaining ~$3.73 on a v3
that would likely land at factual 3.72 again.

Nothing here is thrown away. `eval/` stays green and stays runnable. We return to it when there's
a product worth evaluating.

## End state of this milestone

```
python -m coach.coach --user mishal9 --last 30
```

Fetches the user's recent games, analyzes any not seen before, stores structured mistakes, and
coaches the newest game **with reference to their actual recurring patterns** —
"this is the 4th time in 30 games you've hung a piece right after castling."

No web UI, no API. CLI only. Phase 6 comes after.

## Design decision: structured store, not a vector DB

The queries this product needs are aggregations, and vector similarity cannot serve them:

| Question | Mechanism |
|---|---|
| What's my most common mistake? | `GROUP BY motif ORDER BY SUM(win_prob_loss) DESC` |
| Am I improving? | time-series over a column |
| "4th time you've done this" | exact match on a structured tag |

Embedding coaching prose would retrieve *textually* similar games, which correlates weakly with
*chess-conceptually* similar ones. So: **SQLite + a motif taxonomy.**

Vectors get added later for the one job they genuinely win — "find past positions that resemble
this one" — which needs **position** embeddings, not text embeddings. That's a real problem worth
doing properly, on its own merits, once the structured layer is carrying the product.

## PR1 — `memory/motifs.py`: motif tagging **on the engine's own analysis** — DONE

Original sketch had us hand-rolling static exchange evaluation to decide whether material was
really lost. **Scrapped after review.** We run Stockfish at depth 15 on every position and were
discarding its principal variation — `analyzer.py` kept only `pv[0]`. Re-deriving tactics in
Python beside an engine that already computes them is the reinvention the project's own
architecture ("Stockfish does objective analysis") was written to avoid.

So `analyzer.py` now stores the PV (`MAX_PV_PLIES = 8`, SAN, via `pv_to_san`), and motif tagging
reads the answer off it: replay the line, count material. ~90 lines of exchange simulation never
shipped. What remains is bookkeeping.

Taxonomy — deliberately small, biased to **false negatives over false positives**:

- `hangs_material` — the engine's refutation line opens with a capture and nets ≥ a minor piece.
  Corroborated by `cp_loss ≥ 200`, so a truncated PV can't invent a loss on its own.
- `missed_capture` — the engine's own line opened with a material-winning capture the student passed.
- `allows_fork` — best reply attacks 2+ targets that are undefended or outvalue the attacker.
- `back_rank` — heavy piece lands on a back rank whose king has no flight square.
- `phase` — opening/middlegame/endgame by material and ply (a dimension, not a motif).

Every tag quotes the engine line that produced it, so a bad rule is visible rather than silently
poisoning the profile.

**Validation lesson worth keeping:** first run scored 0/8 on `eval/heldout/`, which looked like a
broken tagger and was not. Those are DrNykterstein (Magnus) games — a "blunder" there is a
positional subtlety, not a hung piece. Re-run against the 1100–1900 Elo corpus and all four
motifs fire correctly. **The held-out set is the wrong fixture for amateur-mistake tooling.**

A promotion at the end of a PV inflated one hang to 1130cp (really 330 — a bishop);
`exchange_window()` now cuts the line before any promotion. 25 tests, 254 total.

## PR2 — `memory/store.py` + `memory/profile.py` — DONE

Stdlib `sqlite3`, no ORM, no migration tool, no pandas: three tables and `GROUP BY`.

Two corrections the build surfaced:

- **`choose_coached_side` was the wrong default.** It picks the *worse-playing* side, so
  ingesting your own games would have silently folded your opponents' mistakes into your
  profile whenever you outplayed them. `resolve_side()` now matches the PGN's player names
  against the username first and only falls back to worse-side for third-party PGNs.
- **Summed win-probability reads as a bug.** Ranking by total damage is right, but printing
  it gave "costing about 125% win probability". The total still ranks; the *average per
  occurrence* is what gets rendered.

`training.corpus.movetext_hash()` extracted (it was inlined three times) and reused as the
dedup key. Deliberately not `game_key()` — that prefers a Lichess id, so the same game
re-exported without the tag would count twice, and this is the number the coach says out loud.

Verified on 14 real maia1 games: 33 mistakes, 11 motif tags, and a re-run stored 0 / skipped 14.

```sql
games(id, source, source_game_id, pgn_hash UNIQUE, white, black, result, eco, opening,
      played_at, user_side, user_name, acpl, blunders, mistakes, inaccuracies,
      analyzed_at, depth)
mistakes(id, game_id, ply, move_number, side, san, best_san, quality,
         cp_loss, win_prob_loss, phase, fen_before)
motifs(mistake_id, motif)
```

Ingest is **idempotent on `pgn_hash`** — re-running weekly must not double-count, or every
frequency number the coach cites becomes a lie.

`profile.py` aggregates to:
- top motifs ranked by **total win-probability lost**, not raw count (damage, not tally)
- per-phase leak breakdown
- trend: motif rate over the window's first half vs second half
- worst openings by ECO

## PR3 — profile injection into the coach prompt

`format_player_profile()` emits a block that joins the existing facts block, and the system
prompt gets a PROFILE section under the **same strict grounding discipline** as the move facts:
only patterns the profile states, only the counts given.

Putting the profile *inside* the facts block matters — `eval/grounding.py` rebuilds the facts to
decide what the model was allowed to cite, so the grounding metric keeps working unchanged.

## Known consequence, recorded now

Profile-injected coaching is **a different prompt**, so the 2026-08-14 reports are not comparable
to anything produced after PR3. That's the PR #49 lesson in a new costume. The metric-version
stamping already in `eval.run` handles it: when we come back to eval, re-baseline first and let
`eval.compare` refuse the stale diff.

## Explicitly not in this milestone

FastAPI, web UI, position embeddings, v3 dataset, any teacher/judge API spend.
