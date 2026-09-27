"""Assemble a distillation *training corpus* — CC0 games disjoint from the held-out set.

Phase 3 needs source games to distill coaching from. They must be **strictly disjoint**
from ``eval/heldout/`` — any overlap leaks the scoreboard and makes the Phase-4 win
meaningless. This module is the guard: it fetches public CC0 games (Lichess), splits the
multi-game PGN into individual games, and drops every game that collides with a held-out
game — matched by both its Lichess ``GameId`` *and* a normalized-movetext hash, so a game
with stripped tags can't sneak through. What survives is written to ``data/games/`` as a
single ``corpus.pgn`` plus a ``manifest.json`` that ``training.distill`` consumes directly.

The fetch is injectable and every filtering step is a pure function, so disjointness, the
dedup, and the length filter are unit-tested with no network.

Usage:
    # fetch from Lichess (CC0 game exports), dedup against held-out, write the corpus
    python -m training.corpus --user DrNykterstein --user Sharkfang --max 40

    # or assemble from PGN files you already have
    python -m training.corpus --input data/raw/sample.pgn --input more.pgn
"""

from __future__ import annotations

import argparse
import datetime
import io
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Callable, Iterable, Iterator

import requests

from engine import fetch_data
from engine.pgn import game_key, movetext_hash, split_pgn
from engine.pgn import normalized_movetext as _normalized_movetext

# Lichess's own guidance is "only run 1 request at a time" — this is the gap between
# sequential per-user fetches in a multi-user loop (here, and in eval.expand_heldout,
# which fetches the same way). A burst of back-to-back calls with no gap is exactly what
# earns a 429, and repeated 429s into an active block have been observed to extend it far
# past the base ~1-minute cooldown, rather than reset it. Tests monkeypatch this to 0 so
# an injected fake fetcher doesn't slow the suite down.
FETCH_PACING_SECONDS = 3.0


def _paced(users: list[str]):
    """Yield ``users``, sleeping ``FETCH_PACING_SECONDS`` before every one after the first."""
    for i, user in enumerate(users):
        if i > 0:
            time.sleep(FETCH_PACING_SECONDS)
        yield user

_TAG_RE = re.compile(r'^\[(\w+) "(.*)"\]$', re.MULTILINE)


def _tags(pgn: str) -> dict[str, str]:
    return dict(_TAG_RE.findall(pgn))


HELDOUT_DIR = Path(__file__).resolve().parent.parent / "eval" / "heldout"
DEFAULT_OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "games"

# A roster spanning the rating ladder, so the coach distills from mistakes at every level
# rather than near-clean GM play. The Maia bots play calibrated *human-like* moves at a fixed
# Elo, so their games carry the instructive errors a coaching model most needs to explain.
DEFAULT_USERS = [
    "maia1",          # ~1100 Elo bot (Maia) — beginner blunders, the richest coaching signal
    "maia5",          # ~1500 Elo bot — club level
    "maia9",          # ~1900 Elo bot — strong club
    "EricRosen",      # IM — instructive, human, well-annotated attacking games
    "DrNykterstein",  # Magnus Carlsen (super-GM) — near-clean reference games
]

# A fetcher takes (user, max_games) and returns the raw multi-game PGN text.
FetchFn = Callable[[str, int], str]


def heldout_fingerprints(heldout_dir: Path = HELDOUT_DIR) -> set[str]:
    """Every identity a held-out game can be recognized by: its id *and* its movetext hash.

    Returning both means a corpus game collides if it shares *either* with any held-out
    game — so a re-export that dropped the ``GameId`` tag is still caught by its moves.
    """
    prints: set[str] = set()
    for pgn_file in sorted(heldout_dir.glob("*.pgn")):
        for game in split_pgn(pgn_file.read_text(encoding="utf-8")):
            prints.add(game_key(game))
            prints.add(f"moves:{movetext_hash(game)}")
    return prints


def heldout_players(heldout_dir: Path = HELDOUT_DIR) -> set[str]:
    """Lowercased names of everyone who plays in a held-out game.

    The database sampler leaves out every game these players play, so no held-out player's
    games (and so none of their habits) are in the training data.
    """
    names: set[str] = set()
    for pgn_file in sorted(heldout_dir.glob("*.pgn")):
        for game in split_pgn(pgn_file.read_text(encoding="utf-8")):
            tags = _tags(game)
            names.update(tags[c].lower() for c in ("White", "Black") if c in tags)
    return names


def _ply_count(pgn: str) -> int:
    """Rough number of half-moves: count SAN-ish tokens in the (comment-stripped) movetext."""
    moves = _normalized_movetext(pgn)
    moves = re.sub(r"\d+\.(\.\.)?", " ", moves)          # drop move numbers "12." / "12..."
    moves = re.sub(r"\b(1-0|0-1|1/2-1/2|\*)\b", " ", moves)  # drop the result token
    return len([t for t in moves.split() if any(c.isalpha() for c in t)])


def assemble(
    games: list[str],
    heldout: set[str],
    *,
    min_plies: int = 10,
) -> list[str]:
    """Dedup ``games`` against the held-out set and each other, dropping games too short.

    Order is preserved; the first occurrence of a duplicate wins. A game is excluded when
    its :func:`game_key` *or* its movetext hash matches any held-out fingerprint.
    """
    kept: list[str] = []
    seen: set[str] = set(heldout)
    for game in games:
        key = game_key(game)
        move_key = f"moves:{movetext_hash(game)}"
        if key in seen or move_key in seen:
            continue
        if _ply_count(game) < min_plies:
            continue
        seen.add(key)
        seen.add(move_key)
        kept.append(game)
    return kept


def canonical_order(games: list[str], seed: int = 0) -> list[str]:
    """Order ``games`` by a stable hash of each game's own identity, not fetch order.

    ``assemble`` orders games however the fetcher happened to return them — for Lichess,
    newest-first on the day of the call, which drifts as a player keeps playing. A data-scale
    sweep needs its sizes **nested** (the 1,000-row tier is a superset of the 400-row tier)
    and **reproducible** months later against a corpus that has moved on. Sorting by
    :func:`training.dataset.bucket_value` of each game's :func:`~engine.pgn.game_key` gives
    an order that depends only on each game's own identity, so row-count prefixes of a raw
    JSONL distilled in this order are the same games every time, regardless of when the
    corpus was fetched or reassembled. See ``docs/experiments/paper-protocol.md``.
    """
    from training.dataset import bucket_value

    return sorted(games, key=lambda pgn: bucket_value(game_key(pgn), seed))


def write_corpus(games: list[str], out_dir: Path) -> Path:
    """Write ``games`` to ``out_dir/corpus.pgn`` + a distill-ready ``manifest.json``.

    The manifest points every entry at the single ``corpus.pgn`` by ``game_index`` and
    leaves ``coached_side`` null, so ``training.distill`` auto-picks the worse-playing
    side per game. Returns the manifest path.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    corpus_path = out_dir / "corpus.pgn"
    corpus_path.write_text("\n\n".join(games) + "\n", encoding="utf-8")

    manifest = [
        {"pgn": "corpus.pgn", "game_index": i, "coached_side": None}
        for i in range(len(games))
    ]
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


# --- Sampling by rating band from a Lichess monthly database export -----------------------
#
# A roster of named players gives as many skill levels as there are players on it. The
# monthly export (database.lichess.org, CC0) holds every rated game played on Lichess that
# month, at every level. It is ~30 GB compressed, but it is written as a series of
# independently compressed zstd frames of a few MB each, so any part of it can be read with
# an HTTP range request that starts at the next frame. The sampler reads the same number of
# small slices, spaced evenly through the file, from every month in a range, so the games
# span every month, day and hour rather than one stretch of time. A multi-year range also
# evens out seasons (summer and school holidays change who plays), opening fashions and
# rating drift. The slice offsets depend only on the file sizes, so the same command gives
# the same games.
#
# Games are sorted into cells of (rating band, time control). Every band gets the same
# number of games, and inside a band the time controls share it equally. A time control
# with too few games (classical above 2000 barely exists on Lichess) gives its unused share
# to the others equally, so no one time control dominates a band.

DB_URL = "https://database.lichess.org/standard/lichess_db_standard_rated_{month}.pgn.zst"

# Rating bands by the mean of the two players' ratings: (label, lowest mean rating). A band
# runs up to the next band's lowest rating.
RATING_BANDS = [
    ("<1200", 0),
    ("1200-1599", 1200),
    ("1600-1999", 1600),
    ("2000-2399", 2000),
    ("2400+", 2400),
]

# Lichess's time-control categories by estimated duration, base + 40 x increment seconds:
# (label, lowest estimate). Bullet (under 180 s) is decided by the clock more than by the
# moves, so it is not sampled.
SPEEDS = [
    ("blitz", 180),
    ("rapid", 480),
    ("classical", 1500),
]
MIN_ESTIMATED_SECONDS = SPEEDS[0][1]
# Both players must be near the same level, so a game belongs to one band.
MAX_RATING_GAP = 200
_BAD_TERMINATIONS = {"Abandoned", "Rules infraction", "Unterminated"}
# Games shorter than this have too little play to coach (quick resignations, early draws).
DB_MIN_PLIES = 20
DB_SLICES = 432   # in total, shared equally across the months
DB_SLICE_BYTES = 6_000_000
_ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"
Cell = tuple[str, str]   # (rating band, speed)


def db_cell(pgn: str, reasons: Counter | None = None) -> Cell | None:
    """The (rating band, speed) of a game worth sampling, or ``None`` if it is skipped.

    Skips unrated, bot, variant or custom-start, abandoned, correspondence and bullet games,
    and games between players more than ``MAX_RATING_GAP`` apart. The reason for each skip is
    counted in ``reasons`` when given.
    """
    def skip(reason: str) -> None:
        if reasons is not None:
            reasons[reason] += 1

    tags = _tags(pgn)
    if not tags.get("Event", "").startswith("Rated"):
        return skip("unrated")
    if "BOT" in (tags.get("WhiteTitle"), tags.get("BlackTitle")):
        return skip("bot")
    if "FEN" in tags or tags.get("Variant", "Standard") != "Standard":
        return skip("variant_or_custom_start")
    if tags.get("Termination") in _BAD_TERMINATIONS:
        return skip("abandoned_or_rules_infraction")
    try:
        base, inc = (int(x) for x in tags["TimeControl"].split("+"))
        white, black = int(tags["WhiteElo"]), int(tags["BlackElo"])
    except (KeyError, ValueError):   # "-" time control (correspondence) or "?" rating
        return skip("correspondence_or_unknown_rating")
    seconds = base + 40 * inc
    if seconds < MIN_ESTIMATED_SECONDS:
        return skip("bullet")
    if abs(white - black) > MAX_RATING_GAP:
        return skip("rating_gap")
    mean = (white + black) / 2
    band = [label for label, lo in RATING_BANDS if mean >= lo][-1]
    speed = [label for label, lo in SPEEDS if seconds >= lo][-1]
    return band, speed


def collect_cells(
    slices: Iterable[list[str]],
    per_slice: int,
    cap: int,
    heldout: set[str],
    *,
    min_plies: int = 10,
    excluded_players: set[str] = frozenset(),
    reasons: Counter | None = None,
    population: Counter | None = None,
    when: Counter | None = None,
    progress: Callable[[int, dict[Cell, list[str]]], None] | None = None,
) -> dict[Cell, list[str]]:
    """Candidates for every cell: at most ``per_slice`` from each slice, ``cap`` in all.

    The per-slice limit keeps each cell spread across the sampled time. Held-out games,
    duplicates, games by ``excluded_players`` and games shorter than ``min_plies`` are
    skipped. When given, ``reasons`` counts every game read and why each skipped game was
    skipped, ``population`` counts every eligible game per cell before any quota, and
    ``when`` counts them by UTC hour and weekday; these are what the balanced corpus is
    compared against.
    """
    cells: dict[Cell, list[str]] = {
        (band, speed): [] for band, _ in RATING_BANDS for speed, _ in SPEEDS
    }
    reasons = Counter() if reasons is None else reasons
    population = Counter() if population is None else population
    when = Counter() if when is None else when
    seen = set(heldout)
    for k, games in enumerate(slices, 1):
        taken: Counter = Counter()
        for game in games:
            reasons["read"] += 1
            cell = db_cell(game, reasons)
            if cell is None:
                continue
            tags = _tags(game)
            if {tags.get("White", "").lower(), tags.get("Black", "").lower()} & excluded_players:
                reasons["heldout_player"] += 1
                continue
            if _ply_count(game) < min_plies:
                reasons["too_short"] += 1
                continue
            population[cell] += 1
            when.update(_when(tags))
            if taken[cell] >= per_slice or len(cells[cell]) >= cap:
                continue
            key, move_key = game_key(game), f"moves:{movetext_hash(game)}"
            if key in seen or move_key in seen:
                reasons["heldout_or_duplicate_game"] += 1
                continue
            seen.update((key, move_key))
            cells[cell].append(game)
            taken[cell] += 1
        if progress:
            progress(k, cells)
    return cells


def _when(tags: dict[str, str]) -> list[str]:
    """``["hour:HH", "weekday:N"]`` (UTC; Monday is 0) for a game, or ``[]`` if undated."""
    try:
        day = datetime.date(*map(int, tags["UTCDate"].split(".")))
        return [f"hour:{int(tags['UTCTime'][:2]):02d}", f"weekday:{day.weekday()}"]
    except (KeyError, ValueError):
        return []


def allocate(available: dict[str, int], total: int) -> dict[str, int]:
    """Split ``total`` as equally as ``available`` allows (water-filling).

    A key with fewer than its equal share gets all it has; the rest is shared equally by
    the others. E.g. ``{"a": 1000, "b": 1000, "c": 10}`` with 300 gives c 10, a 145, b 145.
    """
    alloc: dict[str, int] = {}
    remaining = total
    ordered = sorted(available, key=available.get)
    for i, key in enumerate(ordered):
        alloc[key] = min(available[key], remaining // (len(ordered) - i))
        remaining -= alloc[key]
    # Rounding can leave a few games; give them to keys with room, largest first.
    for key in reversed(ordered):
        extra = min(remaining, available[key] - alloc[key])
        alloc[key] += extra
        remaining -= extra
    return alloc


def _spread(items: list[str], k: int) -> list[str]:
    """``k`` items evenly spaced through ``items`` (all of them if ``k`` is enough)."""
    if k >= len(items):
        return list(items)
    return [items[i * len(items) // k] for i in range(k)]


def select_balanced(cells: dict[Cell, list[str]], per_band: int) -> dict[Cell, list[str]]:
    """``per_band`` games per band, shared across its speeds by :func:`allocate`.

    Candidates are in slice order, so picks spaced evenly through a cell's list stay spread
    across the month.
    """
    chosen: dict[Cell, list[str]] = {}
    for band, _ in RATING_BANDS:
        alloc = allocate({speed: len(cells[band, speed]) for speed, _ in SPEEDS}, per_band)
        for speed, n in alloc.items():
            chosen[band, speed] = _spread(cells[band, speed], n)
    return chosen


def split_decoded_slice(text: str) -> list[str]:
    """Whole games in a slice of decoded export text.

    A slice starts and ends mid-game, so the text before the first ``[Event`` tag and the
    last game (which may be cut short) are both dropped.
    """
    start = text.find("\n[Event ")
    if start < 0:
        return []
    return split_pgn(text[start + 1:])[:-1]


def _decode_slice(data: bytes) -> str:
    """Decode ``data`` from its first zstd frame onward, up to where the bytes run out."""
    import zstandard

    for start in _frame_starts(data):
        reader = zstandard.ZstdDecompressor().stream_reader(
            io.BytesIO(data[start:]), read_across_frames=True)
        out = bytearray()
        try:
            while chunk := reader.read(1 << 20):
                out += chunk
        except zstandard.ZstdError:
            pass   # the slice ends mid-frame; keep what decoded
        if out:
            return out.decode("utf-8", errors="replace")
    return ""


def _frame_starts(data: bytes) -> Iterator[int]:
    """Offsets in ``data`` that look like a zstd frame start (the magic can occur by chance,
    so callers try each in turn)."""
    i = data.find(_ZSTD_MAGIC)
    while i >= 0:
        yield i
        i = data.find(_ZSTD_MAGIC, i + 1)


def month_range(spec: str) -> list[str]:
    """``"2026-08"`` -> that month; ``"2023-09:2026-08"`` -> every month from first to last."""
    first, _, last = spec.partition(":")
    last = last or first
    (y, m), (y_end, m_end) = (map(int, first.split("-")), map(int, last.split("-")))
    months = []
    while (y, m) <= (y_end, m_end):
        months.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    if not months:
        raise ValueError(f"empty month range: {spec}")
    return months


# Each month's slices are shifted by a different fraction of the gap between them, so over
# many months the slices land at every point of the day instead of the same few hours
# (hour of day changes which regions are playing). Successive multiples of the golden
# ratio's fractional part spread as evenly over [0, 1) as any fixed sequence can.
_GOLDEN = 0.6180339887498949


def month_phase(month_index: int) -> float:
    """Where in the gap between slices month ``month_index``'s slices start, in [0, 1)."""
    return (month_index * _GOLDEN) % 1.0


def slice_starts(size: int, slices: int, phase: float = 0.0) -> list[int]:
    """Byte offsets of ``slices`` evenly spaced slices, all shifted by ``phase`` of a gap."""
    step = size // slices
    return [int((k + phase) * step) for k in range(slices)]


def fetch_db_slices(url: str, slices: int = DB_SLICES,
                    slice_bytes: int = DB_SLICE_BYTES,
                    files: dict | None = None, phase: float = 0.0) -> Iterator[list[str]]:
    """Yield the whole games in each of ``slices`` evenly spaced slices of the export.

    ``files``, when given, records the file's size, Last-Modified date and slice phase under
    its URL, so a rebuild can confirm it read the same file at the same offsets.
    """
    headers = {"User-Agent": fetch_data._USER_AGENT}
    head = requests.head(url, headers=headers, timeout=60)
    head.raise_for_status()
    size = int(head.headers["Content-Length"])
    if files is not None:
        files[url] = {"bytes": size, "last_modified": head.headers.get("Last-Modified"),
                      "phase": round(phase, 6)}
    for start in slice_starts(size, slices, phase):
        end = min(start + slice_bytes, size) - 1
        resp = requests.get(url, timeout=120,
                            headers={**headers, "Range": f"bytes={start}-{end}"})
        resp.raise_for_status()
        yield split_decoded_slice(_decode_slice(resp.content))


def _lichess_fetch(user: str, max_games: int) -> str:
    """Default fetcher: pull a user's games as PGN via Lichess."""
    return fetch_data.fetch_lichess_games(user, max_games)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Assemble a distillation corpus disjoint from the held-out set."
    )
    parser.add_argument("--user", action="append", default=[],
                        help="Lichess username to fetch (repeatable); "
                             "defaults to a rating-spanning roster if omitted")
    parser.add_argument("--input", type=Path, action="append", default=[],
                        help="use an existing .pgn file instead of fetching (repeatable)")
    parser.add_argument("--max", type=int, default=20,
                        help="max games to fetch per --user (default: 20)")
    parser.add_argument("--min-plies", type=int, default=None,
                        help="drop games shorter than this many half-moves "
                             f"(default: 10, or {DB_MIN_PLIES} with --from-db)")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR,
                        help="write corpus.pgn + manifest.json here (default: data/games/)")
    parser.add_argument(
        "--canonical-seed", type=int, default=None,
        help="order games by a stable hash of game identity (see canonical_order) instead "
        "of fetch order, seeded by this value — for a reproducible data-scale sweep, "
        "where row-count prefixes of the resulting raw JSONL must stay the same games "
        "across re-fetches. Default: keep fetch order (unset).",
    )
    parser.add_argument(
        "--from-db", metavar="YYYY-MM[:YYYY-MM]",
        help="sample by rating band and time control from the Lichess database export for "
        "this month, or every month in this range, instead of fetching players",
    )
    parser.add_argument("--per-band", type=int, default=400,
                        help="games per rating band with --from-db, shared across time controls "
                             "(default: 400)")
    parser.add_argument("--slices", type=int, default=DB_SLICES,
                        help="slices to read with --from-db, shared equally across the "
                             f"months and rounded up to a multiple of them (default: {DB_SLICES})")
    return parser


def _write_db_source(out_dir: Path, args, *, files: dict, cells: dict[Cell, list[str]],
                     chosen: dict[Cell, list[str]], reasons: Counter,
                     population: Counter, when: Counter) -> None:
    """Record where a --from-db corpus came from and what it holds, to rebuild it exactly
    and to compare it with the population it was drawn from."""
    table = lambda count: {band: {speed: count(band, speed) for speed, _ in SPEEDS}
                           for band, _ in RATING_BANDS}
    eligible = sum(population.values())
    months = Counter(_tags(g).get("UTCDate", "?")[:7].replace(".", "-")
                     for games in chosen.values() for g in games)
    source = {
        "months": args.from_db,
        "files": files,
        "per_band": args.per_band,
        "min_plies": args.min_plies,
        "slices_per_month": args.slices // max(len(files), 1),
        "slice_bytes": DB_SLICE_BYTES,
        "canonical_seed": args.canonical_seed,
        "games": table(lambda b, s: len(chosen[b, s])),
        "games_per_month": dict(sorted(months.items())),
        # Every eligible game read, before any quota: the population the balanced corpus
        # over- and under-samples. Shares are of all eligible games.
        "population": table(lambda b, s: population[b, s]),
        "population_share": table(lambda b, s: round(population[b, s] / eligible, 5)
                                  if eligible else 0),
        "candidates": table(lambda b, s: len(cells[b, s])),
        # UTC hour and weekday (Monday is 0) of the corpus games next to every eligible game.
        "when": {
            "games": dict(sorted(Counter(k for games in chosen.values() for g in games
                                         for k in _when(_tags(g))).items())),
            "population": dict(sorted(when.items())),
        },
        "skipped": dict(reasons.most_common()),
        "filters": {
            "rated_only": True,
            "standard_start_only": True,
            "bots_excluded": True,
            "heldout_players_excluded": True,
            "min_estimated_seconds": MIN_ESTIMATED_SECONDS,
            "max_rating_gap": MAX_RATING_GAP,
            "skipped_terminations": sorted(_BAD_TERMINATIONS),
        },
    }
    (out_dir / "source.json").write_text(json.dumps(source, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None, fetch_fn: FetchFn = _lichess_fetch) -> int:
    args = build_parser().parse_args(argv)
    if args.from_db:
        return _main_from_db(args)
    if args.min_plies is None:
        args.min_plies = 10
    users = list(args.user)
    if not users and not args.input:
        users = list(DEFAULT_USERS)
        print(f"No --user/--input given; using the default rating-spanning roster: "
              f"{', '.join(users)}.", file=sys.stderr)

    raw: list[str] = []
    for path in args.input:
        raw.extend(split_pgn(path.read_text(encoding="utf-8")))
    for user in _paced(users):
        print(f"Fetching up to {args.max} games for '{user}'...", file=sys.stderr)
        raw.extend(split_pgn(fetch_fn(user, args.max)))

    heldout = heldout_fingerprints()
    games = assemble(raw, heldout, min_plies=args.min_plies)
    if not games:
        print(f"No games survived assembly ({len(raw)} fetched).", file=sys.stderr)
        return 1
    if args.canonical_seed is not None:
        games = canonical_order(games, args.canonical_seed)

    dropped = len(raw) - len(games)
    manifest_path = write_corpus(games, args.out_dir)
    print(
        f"Wrote {len(games)} games to {args.out_dir / 'corpus.pgn'} "
        f"({dropped} dropped as held-out/duplicate/too-short).\n"
        f"Manifest: {manifest_path}  —  distill with "
        f"`python -m training.distill --sources {manifest_path}`.",
        file=sys.stderr,
    )
    return 0


def _main_from_db(args, fetch_fn: Callable[..., Iterable[list[str]]] = fetch_db_slices) -> int:
    urls = [DB_URL.format(month=m) for m in month_range(args.from_db)]
    per_month = -(-args.slices // len(urls))
    args.slices = per_month * len(urls)
    if args.min_plies is None:
        args.min_plies = DB_MIN_PLIES
    print(f"Reading {per_month} slices from each of {len(urls)} monthly exports "
          f"({args.from_db})\nfor {args.per_band} games in each of {len(RATING_BANDS)} "
          f"rating bands, shared across {len(SPEEDS)} time controls...", file=sys.stderr)

    def progress(k: int, cells: dict[Cell, list[str]]) -> None:
        if k % per_month == 0:
            print(f"  {k // per_month}/{len(urls)} months: "
                  f"{sum(map(len, cells.values()))} candidates", file=sys.stderr)

    # Every slice may add the same number of games to a cell and no cell is cut off early,
    # so each month contributes equally; any one cell can still fill a whole band.
    per_slice = -(-args.per_band // args.slices)
    files: dict = {}
    reasons: Counter = Counter()
    population: Counter = Counter()
    when: Counter = Counter()
    slices = (s for i, url in enumerate(urls)
              for s in fetch_fn(url, per_month, files=files, phase=month_phase(i)))
    cells = collect_cells(slices, per_slice, per_slice * args.slices,
                          heldout_fingerprints(), min_plies=args.min_plies,
                          excluded_players=heldout_players(), reasons=reasons,
                          population=population, when=when, progress=progress)
    chosen = select_balanced(cells, args.per_band)
    games = [g for cell_games in chosen.values() for g in cell_games]
    if not games:
        print("No games sampled.", file=sys.stderr)
        return 1
    if args.canonical_seed is not None:
        games = canonical_order(games, args.canonical_seed)

    manifest_path = write_corpus(games, args.out_dir)
    _write_db_source(args.out_dir, args, files=files, cells=cells, chosen=chosen,
                     reasons=reasons, population=population, when=when)
    print(f"{'band':<10}" + "".join(f"{speed:>10}" for speed, _ in SPEEDS), file=sys.stderr)
    short = []
    for band, _ in RATING_BANDS:
        counts = [len(chosen[band, speed]) for speed, _ in SPEEDS]
        print(f"{band:<10}" + "".join(f"{n:>10}" for n in counts), file=sys.stderr)
        if sum(counts) < args.per_band:
            short.append(band)
    if short:
        print(f"WARNING: bands short of {args.per_band}: {', '.join(short)}. "
              f"Use more --slices.", file=sys.stderr)
    print(f"Wrote {len(games)} games to {args.out_dir / 'corpus.pgn'}.\n"
          f"Manifest: {manifest_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
