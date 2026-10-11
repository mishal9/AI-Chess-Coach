# Tool-augmented teacher: pilot

**Status:** pilot, 9 Oct 2026. Judged since in a paired comparison
(`2026-10-10-tools-vs-no-tools-paired.md`): the tools did not reduce errors (8 vs 7 of
100), so the corpus is written without them. Code on branch `feat/tool-augmented-teacher`
(stacked on `feat/explicit-defence-claims`). Nothing here is a reading; it decides whether
a judged run is worth paying for.

## Why

Across three judged samples, about 6% of clear-cut position rows carry a confirmed false
claim, and the errors that remain are relations the facts block did not settle ("Qd5
defends your bishop on g2" through a pawn; "after Rxd6 you are left with a knight against a
rook"). Prompt rules did not move the teacher: "name both pieces" left pronoun subjects at
32% (v5). Published work points the same way. Kim et al. (NAACL 2025) found that feeding
engine signals and enumerated attacks cut static errors (non-existent pieces 46% → 20%) but
left reasoning errors unchanged. Hebbar et al., arXiv 2608.04240 (Aug 2026), let models call
17 board and Stockfish tools while writing chess commentary, and DeepSeek V4 Pro's incorrect
sub-claims fell from 36.7% to 14.4% (Table 2). Without tools, its models received "only the
board state as a FEN string and the move played" (Section 4.1): no engine evaluation, best
move, or attackers and defenders. So part of that gain our facts block already gives. (Read
in full 10 Oct; see `2026-10-10-tools-vs-no-tools-paired.md`, "Against the published
result".)

## What was built

- `training/board_tools.py` (commit `907b421`): four deterministic python-chess tools over
  the three positions the facts describe (before the move, after it, after the preferred
  move): `piece_at`, `attackers_and_defenders`, `reaches` (does one piece attack or defend
  another, and what blocks it), `play_line` (each move's capture and the material at the
  end, or the first illegal move). No engine.
- `training.teacher.deepseek_tool_backend`: the OpenAI-style tool loop. Tool calls and
  results stay in the conversation; only the final answer becomes the row. At most 8 tool
  rounds, then the tools are withdrawn.
- `training.distill --teacher-tools`: the position teacher gets the tools and a short
  "check before you write" layer in its system prompt. The student's prompt is unchanged;
  the student never sees tools. Rows record `teacher.tools = "board-v1"` and
  `quality.tool_calls`.

## Pilot

The first 20 games of the v5 run (`data/games/tools_pilot20.json`), same settings as v5
plus `--teacher-tools`, compared row for row with v5's rows for the same positions. Three
iterations:

| | v5, no tools | A | B | C |
|---|---|---|---|---|
| Change | — | tools | + no preamble, no bare squares | + first turn must call a tool |
| Rows | 55 | 55 | 55 | 55 |
| Tool calls per row (mean / rows with none) | 0 | 2.3 / 27 | 0.1 / 53 | 4.5 / 0 |
| Grounded | 51 | 46 | 52 | 50 |
| Chat preamble | 0 | 11 | 0 | 0 |
| Pass QC | 50 | 36 | 51 | 46 |
| Placement flags | 1 | 1 | 1 | 4 (all false alarms, below) |
| Attack/defence pairings | 44 | 23 | 24 | 31 |
| Pronoun or bare-move subject | 34% | 9% | 21% | 13% |
| Input / output tokens per row | 1.6k / 350 | 4.6k / 540 | 2.6k / 350 | 6.3k / 630 |

- **A:** after a tool exchange the teacher opened like a chat reply ("Here's what
  happened…", 11 rows), and copied the tools' bare squares ("f2 went from having two
  defenders"), which grounding reads as uncited pawn moves.
- **B:** fixing both in the prompt made the teacher stop using the tools: left optional at
  temperature 0, 53 of 55 rows made no call.
- **C:** `tool_choice: "required"` on the first turn. Every row checks the board (up to 16
  calls). Its 4 placement flags are all the placement checker's known blind spot: 3
  describe the board after the preferred move ("activating your bishop to g4" when the
  preferred move is Bg4) and 1 a knight that reaches c2 in the engine's line. The checker
  knows only the game's positions, so it reads these as invented. Discounting them, C
  passes QC on 50 of 55, as v5 does.

## Pilot D: tools veto only

Pilot C let the teacher write what the tools showed. But the student has no tools and sees
only the facts, so a relation the teacher verified and the facts do not state ("the e4
pawn blocks your queen's diagonal to g2") would teach the student to assert what it cannot
check. Pilot D (commit `7b49499`) keeps the tools but changes the instruction: use them to
catch mistakes, leave out anything they contradict, and state only what the facts state.

`scripts/claim_support.py` sorts each resolvable defence claim into **stated** (a facts
line names this defender for this target), **unstated** (true on the board, not in the
facts) or **false**:

| | v5, no tools | C | D (veto only) |
|---|---|---|---|
| Tool calls per row (mean / rows with none) | 0 | 4.5 / 0 | 3.5 / 0 |
| Grounded | 51 | 50 | 50 |
| Pass QC | 50 | 46 | 49 |
| Placement flags | 1 | 4 | 1 |
| Attack/defence pairings | 44 | 31 | 22 |
| Pronoun or bare-move subject | 34% | 13% | 18% |
| Defence claims: stated / unstated / false | 14 / 2 / 1 | 10 / 2 / 0 | 6 / 1 / 0 |
| Input / output tokens per row | 1.6k / 350 | 6.3k / 630 | 6.1k / 580 |

The counts of resolvable defence claims are small, so the support shares say little: C did
not measurably add unstated relations, and D makes fewer relation claims of every kind.
D's placement flags fell back to 1: it stopped describing the board after the preferred
move.

Read side by side, D drops v5's false "Qf6 … defends your knight on c6" (#189 p14: a knight
on d6 blocks the queen) and an unstated relation (#328 p21). **But it still writes false
causal claims the tools could have caught.** In #328 p22 it says Qe4 "let go of both jobs
at once", one of them defending the knight on d3; after Qe4 the queen still defends d3, and
the facts say so ("knight on d3 (… defenders 1: queen on e4)"). It made 6 tool calls on
that row and none checked this. The tools remove the errors the teacher thinks to check;
the judged rate is still the only measure of what is left.

## What the pilot shows and does not

- Tool use can be made reliable (C), at about 4× the input tokens and 1.8× the output per
  row. DeepSeek bills repeated prompt prefixes at its cache-hit rate, so the cost rise is
  smaller than the token rise; at worst about 3× v5's ≈ $0.0017 a row.
- Attack/defence claims get more explicit (pronoun subjects 34% → 13%) and fewer.
- **It does not show that rows are more accurate.** QC cannot see the causal errors this is
  meant to fix. Only a judged sample with a board check of low-scoring rows can, as before.

## Where to resume (state at 10 Oct 2026, late)

> **Superseded 11 Oct 2026.** Resume from "Where to resume" at the end of
> `2026-10-10-game-only-vs-mixed-student.md`. The section below is kept as it was.

Written so the next session can pick up from here. Steps 2–3 of the earlier list are done
(below); the steps listed below have not been run.

### Decisions taken

| Date | Decision | Where recorded |
|---|---|---|
| 8 Oct | Keep position rows despite ~6% confirmed errors, as a stated deviation from the 5% bar. Whether they enter training is decided by the student: a game-only vs mixed comparison on the held-out games, pre-registered before it runs. If the mixed student is less factual, the position rows come out. | `2026-10-08-explicit-defence-claims.md`, "Where this sits" |
| 8 Oct | Stay with DeepSeek as teacher. Its terms allow distillation ("training other models (such as model distillation)", 4.2(3)); Gemini's forbid using the service "to develop models that compete", and Gemini is one of our judges. | this note's history; status page |
| 9 Oct | Tools during generation, veto only (pilot D): the tools catch the teacher's mistakes, and it states only what the facts state, because the student has no tools. | this note, "Pilot D" |
| 10 Oct | Fold the pending v5 judge into one paired tools vs no-tools comparison. | `2026-10-08-explicit-defence-claims.md`, "Change to the registration" |
| 10 Oct | By the pre-registered rule, the plain (v5) prompt, without tools, writes the rest of the corpus: tools 8 confirmed errors vs 7, factual 4.59 vs 4.54. | `2026-10-10-tools-vs-no-tools-paired.md`, "Result" |

### Position rows so far

| Version | Change | Factual | Confirmed errors (board-checked) |
|---|---|---|---|
| Old rows | one-line facts | 4.18 (same 133) | 8 / 150 = 5.3% |
| 8 Oct | board in the facts | 4.38 (133) | 10 / 133 = 7.5% |
| v3 | evaluation in words | 4.44 (fresh 100) | 6 / 100 = 6.0% |
| v3, clear-cut | clear-cut filter, new games | 4.55 (100) | 6 / 100 = 6.0% |
| v4 | named attackers and defenders | 4.51 (100) | 6 / 100 = 6.0% |
| v5 | "name both pieces" rule | not judged | rule not followed (pronoun subjects 34% → 32%) |
| v5, paired | "name both pieces" rule, no tools | 4.54 (100) | 7 / 100 = 7.0% |
| D, paired | tools, veto only | 4.59 (same 100) | 8 / 100 = 8.0% |

Pooled over the last four no-tools samples (v3 fresh, v3 clear-cut, v4, v5 paired):
25 / 400 = 6.25% (95% Wilson 4.3–9.1%), a lower bound (only rows at factual 3 or lower are
board-checked).

### Next steps, in order

Done 10 Oct: the paired comparison was pre-registered (commits `894e333`, `48fd4e2`) and
run. Plain (v5 prompt) won by the rule. DeepSeek balance is now $3.78.

1. **Top up DeepSeek (user).** 200 games already have v5-prompt rows (`explicit100` in
   `raw_deepseek_pos_v5.jsonl`, `paired100` in `raw_deepseek_pos_paired_plain.jsonl`). 354
   sample games have rows from older prompts, and 1,446 have none. At about $0.005 per game
   without tools (v5: $0.50 for 100 games), the 1,446 cost about $7.20 and all 1,800 about
   $9. The balance of $3.78 covers neither.
2. **Generate the rest of the corpus** with the v5 prompt and no tools: `training.distill
   --sources data/games/manifest.json --teacher deepseek --teacher-thinking disabled
   --workers 8 --retries 1 --positions-per-game 4 --no-game-rows --resume --out
   data/distill/raw_deepseek_pos_v5.jsonl` (`--resume` skips the 100 games already in
   it). First decide whether the 354 older-prompt sample games are regenerated with v5 or
   left out, and add the `paired100` plain rows. Then QC and the clear-cut filter.
3. **Pre-register the game-only vs mixed student comparison** and amend `paper-protocol.md`
   (arm sizes and the 1:2 mix depend on its outcome).

### Still open from earlier

- Confirmed 10 Oct: keep the checker v2 placement filter, and split 90/10/0 by game
  (`--ratios 0.9 0.1 0`), recorded in the 7 Oct audit note.
- Done 10 Oct (branch `feat/defence-check-metric-v3`, stacked on this one): the defence check
  skips negations with a word before the verb (`b833e53`; removes the one false flag, #1419
  p6, of 2,593 rows). The held-out claim metric is now `METRIC_VERSION` 3 (`211d350`):
  defence claims in whole-game coaching are checked against every position of the game.
  It changes nothing for DeepSeek's 91 held-out games, which make no resolvable defence
  claim. It is a sensor for a mixed student carrying position-row defence claims into game
  coaching. `eval.recheck` cannot backfill reports scored with grounding v2: its alignment
  check uses the v1 move extractor and refuses them.
- `docs/concept-mindmap.md`, `docs/learning-build-schedule.md` and `docs/learning-notes.md`
  have uncommitted edits that are not part of this work; left as they are.

### Code and data

- Branch `feat/tool-augmented-teacher`, local only, stacked: `feat/explicit-defence-claims`
  → `feat/named-defenders` → `feat/clear-cut-position-rows` → `feat/position-facts-board`
  → `feat/deepseek-training-rows`. The remote copy of `feat/deepseek-training-rows` holds
  stale pre-rewrite history, so check before pushing any of these.
- Teacher: `training/board_tools.py`, `training.teacher.deepseek_tool_backend`
  (first turn `tool_choice: "required"`, at most 8 rounds), `training.distill
  --teacher-tools` (rows record `teacher.tools = "board-v1"` and `quality.tool_calls`).
- Checks and measures: `eval.claims.check_defence_claims` (QC kind `invented_defence`),
  `eval.claims.defence_claim_support`, `training.clear_cut`, `scripts/claim_subjects.py`,
  `scripts/claim_support.py`. 617 tests pass.
- Rows (git-ignored, `data/distill/`): `raw_deepseek_pos_v3*.jsonl`, `_v4`, `_v5` with their
  `_qc` and `_clear` files and judge verdicts; pilots in `data/distill/pilot_tools/`
  (`raw_tools_a`–`d`, and `v5_same20.jsonl`, the v5 rows for the same 20 games).
- Game samples (git-ignored, `data/games/`): `spotcheck146`, `pilot10`, `clearcut100`
  (seed 20261009), `named100` (20261010), `explicit100` (20261011), `tools_pilot20` (the
  first 20 of `explicit100`). Each is drawn from `manifest.json` minus the earlier ones, by
  the code in `2026-10-08-clear-cut-position-rows.md`.
