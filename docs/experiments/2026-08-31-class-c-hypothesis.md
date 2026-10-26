# Gate 4: the class-C hypothesis, tested. It does not hold.

Date: 2026-08-31. Cost: zero (Stockfish over the held-out set, no model, no API).
Closes the open item in `2026-08-30-paper-outline.md` §9.

## The hypothesis

From the project record, and echoed in the outline's future work:

> Students' invented board narrative may be inherited from pretraining rather than from the
> corpus, in which case more teacher data cannot fix it.

It was attractive because Chess-R1 (Hwang et al., arXiv:2507.00726) independently concluded
that the limit on chess RL "stems from a deficit in the pretrained models' internal
understanding of chess." If placement claims are a pretraining artifact, fine-tuning should
leave the rate roughly unchanged.

## Method

`eval.claims.check_board_state` counts *placement claims* — statements like "your rook on
b7" — and flags one as false when that piece and colour were never on that square at any
point in the game. Run over the same 29 held-out games for the prompted base and the
fine-tune, both at claims metric version 1.

`eval.recheck` backfilled the v2 report, which predates `eval/claims.py`. It **refused** the
control report, correctly: recheck verifies the positional join by reproducing each game's
stored hallucinated set under the *pre-#41* parser, and the control was scored after that
fix, so five games mismatch on bare squares (`h7`, `c6`, `d5`, `f7`, `c5`, `d4`). The control
already carries its own claims block, so no backfill was needed. Worth noting as a real
limitation of `recheck`: it cannot backfill any report scored with the corrected parser.

## Result

| model | placement claims | per game | false | total violations |
|---|---|---|---|---|
| prompted `qwen3:8b` (no fine-tune) | 30 | **1.03** | 1 | 1 |
| `qwen-coach-8b-v2` (QLoRA on teacher rows) | 67 | **2.31** | 1 | 2 |

Games in which any placement claim was made: 18/29 control, 23/29 fine-tune.

## Reading

**The hypothesis is not supported.** Fine-tuning did not leave the rate unchanged: it more
than doubled it, 1.03 → 2.31 claims per game. This is not pretrained behaviour surviving
distillation; it is behaviour distillation *amplified*, and it did so despite the teacher
making placement claims at only 0.04 per row. The student reaches for board narrative far
more than the teacher it was trained on.

**False claims, though, stayed flat at one each.** So v2 makes
roughly twice as many placement claims at the same absolute error count: more descriptive,
not less accurate. Earlier framing treated placement claims as a failure mode to suppress;
on this evidence they are mostly a *style* the fine-tune acquired, and the error rate did not
follow the volume.

## Consequences for the paper

- §9 changes from "untested, and Chess-R1 supports it" to "tested, and it does not hold for
  this failure mode." Chess-R1 remains citable for the RL result, but must no longer be
  presented as support for the class-C mechanism here.
- The earlier headline "students make placement claims 0.49/game vs the teacher's 0.04/row
  (~12×), and 14% of the students' are false" is from the v1/ablation era and measured
  differently. **The current numbers are 1.03 and 2.31 per game with 1 false claim each**;
  the paper should use these, or state explicitly which population each figure covers.
- Cheap follow-up, still free: run the same check on the v1 fine-tune to see whether the
  amplification tracks dataset size or is a step change at any fine-tuning at all.
