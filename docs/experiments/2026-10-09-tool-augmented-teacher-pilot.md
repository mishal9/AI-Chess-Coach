# Tool-augmented teacher: pilot

**Status:** pilot, 9 Oct 2026, not judged. Code on branch `feat/tool-augmented-teacher`
(stacked on `feat/explicit-defence-claims`). Nothing here is a reading; it decides whether
a judged run is worth paying for.

## Why

Across three judged samples, about 6% of clear-cut position rows carry a confirmed false
claim, and the errors that remain are relations the facts block did not settle ("Qd5
defends your bishop on g2" through a pawn; "after Rxd6 you are left with a knight against a
rook"). Prompt rules did not move the teacher: "name both pieces" left pronoun subjects at
32% (v5). Published work points the same way. Kim et al. (NAACL 2025) found that feeding
engine signals and enumerated attacks cut static errors (non-existent pieces 46% → 20%) but
left reasoning errors unchanged. arXiv 2608.04240 (Aug 2026) let models call board and
engine tools while writing chess commentary, and DeepSeek V4 Pro's incorrect sub-claims fell
from 36.7% to 14.4% (its baseline saw only a FEN, so part of that gain our facts block
already gives).

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

## What the pilot shows and does not

- Tool use can be made reliable (C), at about 4× the input tokens and 1.8× the output per
  row. DeepSeek bills repeated prompt prefixes at its cache-hit rate, so the cost rise is
  smaller than the token rise; at worst about 3× v5's ≈ $0.0017 a row.
- Attack/defence claims get more explicit (pronoun subjects 34% → 13%) and fewer.
- **It does not show that rows are more accurate.** QC cannot see the causal errors this is
  meant to fix. Only a judged sample with a board check of low-scoring rows can, as before.

## Next

Before judging C, the placement checker should accept a placement that holds on the board
after the preferred move, and placements in the engine lines, or QC will drop correct rows
from the tool teacher. Then a pre-registered judged run on 100 fresh games, compared with v5
(judging pending the Anthropic top-up).
