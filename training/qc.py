"""Quality control for distilled rows: every check we have, run on what is stored.

``training.distill`` gates a row on one thing, its grounding score. That leaves the claim
checkers (``eval.claims``: role inversion, invented castling, invented piece placement),
which the paper reports on held-out coaching, unrun on training targets. This module runs
all of them over a raw distillation file, with no teacher, no judge and no engine, so a new
teacher's rows can be held to the same bar as the Opus rows they would replace.

A row is checked on four things:

* **grounding** — every move it cites is in the facts block it was given (recomputed from
  the stored facts, not trusted from the stored ``quality`` block);
* **claims** — replaying the source game, it asserts no role, castle or piece placement the
  game never had. The board-state and castling checks read only each move's side, SAN and
  ``fen_before``, so the report is rebuilt by replaying the PGN — no Stockfish;
* **structure** — non-empty, a plausible length, no reasoning trace or chat preamble;
* **integrity** — the source game is not in the held-out set, the row's facts sit inside its
  prompt, and no completion appears twice.

``--baseline`` prints the same numbers for a second file over the source rows both share,
so two teachers are compared on identical positions.

Usage:
    python -m training.qc data/distill/raw_deepseek.jsonl
    python -m training.qc data/distill/raw_deepseek.jsonl --baseline data/distill/raw_v2.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

import chess

from coach import prompts
from engine.pgn import load_game
from eval import claims, grounding
from training import corpus
from training.schema import DistillRecord

DEFAULT_CORPUS_DIR = Path("data/games")

# Bounds taken from the Opus v2 rows (whole-game 1311–2356 chars, position 909–1590), then
# widened, so a row that is empty, a stub or a runaway fails but ordinary style does not.
MIN_CHARS = 400
MAX_CHARS = 4000

_REASONING_RE = re.compile(r"</?think>", re.IGNORECASE)
_PREAMBLE_RE = re.compile(
    r"^\s*(sure|certainly|of course|here(?:'s| is| are)|as an ai|i(?:'m| am) (?:sorry|unable))",
    re.IGNORECASE,
)


def replay_report(pgn_path: Path, game_index: int) -> dict:
    """The slice of a report the claim checkers read, rebuilt from the PGN alone.

    ``check_castling`` needs each move's side and SAN; ``check_board_state`` needs each
    move's ``fen_before``. Neither depends on an engine evaluation, so this is exact.
    """
    game = load_game(pgn_path, game_index)
    if game is None:
        raise SystemExit(f"No game at index {game_index} in {pgn_path}")
    board = game.board()
    moves = []
    for move in game.mainline_moves():
        moves.append({
            "side": "white" if board.turn == chess.WHITE else "black",
            "san": board.san(move),
            "fen_before": board.fen(),
        })
        board.push(move)
    return {"moves": moves}


def structure_problems(text: str) -> list[str]:
    """Ways a completion is malformed as a training target, independent of the chess."""
    problems = []
    if not text.strip():
        return ["empty"]
    if len(text) < MIN_CHARS:
        problems.append("too_short")
    if len(text) > MAX_CHARS:
        problems.append("too_long")
    if _REASONING_RE.search(text):
        problems.append("reasoning_trace")
    if _PREAMBLE_RE.match(text):
        problems.append("chat_preamble")
    return problems


def check_row(record: DistillRecord, report: dict, heldout: set[str]) -> dict:
    """Run every check on one record; returns a flat, JSON-able result."""
    text = record.completion
    g = grounding.score_grounding(text, record.facts)
    side = record.coached_side
    c = claims._merge(
        claims.check_roles(text, record.facts),
        claims.check_castling(text, report, side),
        claims.check_board_state(text, report, side),
    )
    structure = structure_problems(text)

    system = prompts.SYSTEM_PROMPT if record.kind == "game" else prompts.POSITION_SYSTEM_PROMPT
    integrity = []
    if record.facts not in record.prompt[-1]["content"]:
        integrity.append("facts_not_in_prompt")
    if record.source_key() in heldout:
        integrity.append("heldout_game")

    return {
        "kind": record.kind,
        "key": row_key(record),
        "grounded": g.grounded,
        "hallucinated": sorted(g.hallucinated),
        "claims_ok": not c.violations,
        "violations": [v.kind for v in c.violations],
        "excerpts": [v.excerpt for v in c.violations],
        "structure": structure,
        "integrity": integrity,
        "chars": len(text),
        # Informational, not a failure: the system prompt gained a PLAYER HISTORY section
        # after v2 was built, so older rows legitimately differ from the current one.
        "current_prompt": record.prompt[0]["content"] == system,
        "passed": g.grounded and not c.violations and not structure and not integrity,
    }


def row_key(record: DistillRecord) -> str:
    """Identity of a row across teachers: the source game, granularity and move."""
    s = record.source
    return f"{record.source_key()}|{record.kind}|{s.get('move_number', '')}"


def heldout_game_keys(corpus_dir: Path) -> set[str]:
    """``pgn#index`` keys of corpus games that collide with a held-out game.

    ``training.corpus`` already drops these when it builds the corpus, so a non-empty result
    means the corpus was assembled some other way.
    """
    prints = corpus.heldout_fingerprints()
    corpus_pgn = corpus_dir / "corpus.pgn"
    if not corpus_pgn.exists():
        return set()
    bad = set()
    for i, text in enumerate(corpus.split_pgn(corpus_pgn.read_text(encoding="utf-8"))):
        if corpus.game_key(text) in prints or f"moves:{corpus.movetext_hash(text)}" in prints:
            bad.add(f"corpus.pgn#{i}")
    return bad


def run_qc(records: list[DistillRecord], corpus_dir: Path) -> list[dict]:
    heldout = heldout_game_keys(corpus_dir)
    reports: dict[tuple[str, int], dict] = {}
    results = []
    seen = Counter(r.completion for r in records)
    for rec in records:
        ident = (rec.source["pgn"], rec.source["game_index"])
        if ident not in reports:
            reports[ident] = replay_report(corpus_dir / ident[0], ident[1])
        result = check_row(rec, reports[ident], heldout)
        if seen[rec.completion] > 1:
            result["integrity"].append("duplicate_completion")
            result["passed"] = False
        results.append(result)
    return results


def summarize(results: list[dict]) -> dict:
    """Pass rates, violation counts and length stats, overall and per row kind."""
    def block(rows: list[dict]) -> dict:
        n = len(rows)
        if not n:
            return {"n": 0}
        chars = sorted(r["chars"] for r in rows)
        return {
            "n": n,
            "passed": sum(r["passed"] for r in rows),
            "grounded": sum(r["grounded"] for r in rows),
            "claims_ok": sum(r["claims_ok"] for r in rows),
            "structure_ok": sum(not r["structure"] for r in rows),
            "integrity_ok": sum(not r["integrity"] for r in rows),
            "current_prompt": sum(r["current_prompt"] for r in rows),
            "violations": dict(Counter(v for r in rows for v in r["violations"])),
            "structure_problems": dict(Counter(p for r in rows for p in r["structure"])),
            "chars_median": statistics.median(chars),
            "chars_p95": chars[int(0.95 * (n - 1))],
        }

    out = {"all": block(results)}
    for kind in ("game", "position"):
        out[kind] = block([r for r in results if r["kind"] == kind])
    return out


def format_summary(name: str, summary: dict) -> str:
    lines = [f"{name}"]
    for scope in ("all", "game", "position"):
        b = summary[scope]
        if not b["n"]:
            continue
        n = b["n"]
        lines.append(
            f"  {scope:<9}n={n:<4} pass {b['passed']}/{n} ({b['passed'] / n:.0%})  "
            f"grounded {b['grounded']}/{n}  claims-ok {b['claims_ok']}/{n}  "
            f"structure-ok {b['structure_ok']}/{n}  integrity-ok {b['integrity_ok']}/{n}  "
            f"chars med {b['chars_median']:.0f} p95 {b['chars_p95']}"
        )
        if b["violations"]:
            lines.append(f"            claim violations: {b['violations']}")
        if b["structure_problems"]:
            lines.append(f"            structure problems: {b['structure_problems']}")
    return "\n".join(lines)


def load_records(path: Path) -> list[DistillRecord]:
    with path.open(encoding="utf-8") as fh:
        return [DistillRecord.from_dict(json.loads(line)) for line in fh if line.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Quality-control distilled rows.")
    parser.add_argument("rows", type=Path, help="raw record JSONL from training.distill")
    parser.add_argument("--baseline", type=Path, default=None,
                        help="a second raw JSONL; compared on the source rows both contain")
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR,
                        help="directory holding the corpus.pgn the rows came from")
    parser.add_argument("--out", type=Path, default=None,
                        help="write per-row results and the summary as JSON here")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    records = load_records(args.rows)
    results = run_qc(records, args.corpus_dir)
    summary = summarize(results)
    print(format_summary(args.rows.name, summary))

    payload = {"file": str(args.rows), "summary": summary, "rows": results}
    if args.baseline:
        base_results = run_qc(load_records(args.baseline), args.corpus_dir)
        by_key = {r["key"]: r for r in base_results}
        shared = [r["key"] for r in results if r["key"] in by_key]
        mine = {r["key"]: r for r in results}
        print(f"\nPaired on {len(shared)} shared source rows "
              f"(of {len(results)} here, {len(base_results)} in the baseline):")
        for label, table in ((args.rows.name, mine), (args.baseline.name, by_key)):
            print(format_summary(label, summarize([table[k] for k in shared])))
        payload["baseline"] = {"file": str(args.baseline), "shared": len(shared),
                               "summary": summarize(base_results)}

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"\nWrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
