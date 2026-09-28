#!/usr/bin/env python3
"""effort_map — BA effort estimation for hs:shape: size->range mapping + sum.

Two effort sources ever reach a milestone rollup: the PO story's own
`size: S|M|L` (read-only, mapped through the table below into a day range) and
a BA task's own explicit `estimate` string, authored directly on the task
record by `task_model.py`. An explicit task estimate always wins over a
size-derived range — a BA who wrote "2d" on a task meant 2 days, not
whatever the linked story's `size` would map to.

The size->range table is data, not scattered literals: `default_size_range_table()`
loads it from an embedded YAML block (human-editable shape, matching every other
config-vs-code split in this codebase) rather than an if/elif ladder repeated at
each call site. A caller may point at an override YAML file via `load_size_range_table(path)`;
a missing or malformed override file falls back to the default rather than raising —
the same fail-open posture the sibling `poc_gate.py` uses for a missing verdict artifact.

Every function here is pure and forgiving: an unparsable estimate string, an
unknown size letter, or an empty task record returns `None` / an empty rollup
rather than raising. There is nothing here that can crash a roadmap build over
one bad estimate string typed by a human — see `roadmap_rollup.py`, which is the
only caller that turns a `None`/empty result into an omission.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

# yaml_io (the shared YAML reader/writer, harness/scripts/) is not on sys.path
# by default from a skill's scripts/ dir -- add it before importing. APPEND
# (never insert at 0) so a same-named sibling module in THIS skill's own
# scripts/ dir keeps winning over a harness/scripts copy.
_HARNESS_SCRIPTS = str(Path(__file__).resolve().parents[5] / "scripts")
if _HARNESS_SCRIPTS not in sys.path:
    sys.path.append(_HARNESS_SCRIPTS)
import yaml_io

RootLike = Any  # str | Path, kept untyped to avoid a PEP-604 union annotation

# Default BA size->range table, kept as one YAML block (config, not code) so a
# project can override it wholesale via `load_size_range_table(path)` instead
# of patching call sites scattered through this module.
_DEFAULT_SIZE_RANGE_YAML = """
S: "1-2d"
M: "3-5d"
L: "1-2w"
"""

# A calendar week -> working-day conversion, needed only to make a week-unit
# estimate summable alongside day-unit ones. Documented here as the single
# place this assumption is made (references/roadmap-effort.md restates it).
WORK_DAYS_PER_WEEK = 5

_ESTIMATE_RE = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*(?:-\s*(\d+(?:\.\d+)?)\s*)?([dw])\s*$", re.IGNORECASE
)


def default_size_range_table() -> Dict[str, str]:
    """The built-in `S|M|L -> range` table, parsed fresh each call (cheap,
    keeps callers from accidentally mutating a shared dict)."""
    return dict(yaml_io.safe_load(_DEFAULT_SIZE_RANGE_YAML))


def load_size_range_table(path: Optional[RootLike] = None) -> Dict[str, str]:
    """Load a size->range table from `path`, or the default when `path` is
    falsy. A missing file, unreadable YAML, or a non-mapping result all fall
    back to the default silently -- an override file is optional config, not
    a hard dependency a malformed edit should be able to break."""
    if not path:
        return default_size_range_table()
    p = Path(path)
    if not p.is_file():
        return default_size_range_table()
    try:
        data = yaml_io.safe_load(p.read_text(encoding="utf-8"))
    except Exception:
        # PyYAML raises a wider family than (yaml_io.YAMLError, ValueError) on
        # malformed input -- e.g. a bare AttributeError from
        # construct_yaml_timestamp on an explicit-tag `bad: !!timestamp 'not
        # a ts'` -- plus OSError/UnicodeDecodeError from the read itself.
        # This override table is optional config; nothing here should be
        # able to crash a build over one malformed value.
        return default_size_range_table()
    if not isinstance(data, dict):
        return default_size_range_table()
    return data


def map_size_to_range(size: Optional[str], table: Optional[Dict[str, str]] = None) -> Optional[str]:
    """`S|M|L` (case-insensitive) -> a day-range string, or `None` for
    anything not in the table (an unknown size is a soft miss, not an
    error -- the caller decides what to do with an unmapped task)."""
    if not isinstance(size, str) or not size.strip():
        return None
    table = table if table is not None else default_size_range_table()
    return table.get(size.strip().upper())


# ---------------------------------------------------------------------------
# Estimate string parsing / summation
# ---------------------------------------------------------------------------

def parse_estimate_days(estimate: Optional[str]) -> Optional[Tuple[float, float]]:
    """Parse `"2d"` / `"3-5d"` / `"1-2w"` into a `(min_days, max_days)` pair.
    Returns `None` for anything that does not match OR an inverted range
    (`lo > hi`, e.g. a `"5-2d"` fat-finger) -- never raises, so one hand-typed
    bad estimate cannot take down a whole rollup. Rejecting the inverted range
    (rather than silently keeping `(5, 2)`) routes it through the caller's
    existing `dropped_estimates` surfacing, instead of persisting a nonsensical
    min > max `effort_rollup` with no warning."""
    if not isinstance(estimate, str):
        return None
    m = _ESTIMATE_RE.match(estimate)
    if not m:
        return None
    lo = float(m.group(1))
    hi = float(m.group(2)) if m.group(2) else lo
    if lo > hi:
        return None
    if m.group(3).lower() == "w":
        lo *= WORK_DAYS_PER_WEEK
        hi *= WORK_DAYS_PER_WEEK
    return (lo, hi)


def _fmt_num(x: float) -> str:
    return "%g" % x


def format_days_range(lo: float, hi: float) -> str:
    if lo == hi:
        return "%sd" % _fmt_num(lo)
    return "%s-%sd" % (_fmt_num(lo), _fmt_num(hi))


def sum_estimates(estimates: Sequence[Optional[str]]) -> str:
    """Sum a batch of estimate strings into one range string. An unparsable
    entry is skipped (fail-open, matching `parse_estimate_days`); an all-empty
    or all-unparsable batch sums to `"0d"` rather than raising -- a milestone
    with no estimated tasks yet is a valid, common state, not an error."""
    lo_total = 0.0
    hi_total = 0.0
    any_valid = False
    for e in estimates:
        parsed = parse_estimate_days(e)
        if parsed is None:
            continue
        lo, hi = parsed
        lo_total += lo
        hi_total += hi
        any_valid = True
    if not any_valid:
        return "0d"
    return format_days_range(lo_total, hi_total)


def estimate_for_task(
    task: Optional[Dict[str, Any]],
    story_size: Optional[str] = None,
    table: Optional[Dict[str, str]] = None,
) -> str:
    """The effective effort figure for one task record: its own explicit
    `estimate` field wins outright over anything size-derived; only when that
    field is blank does a linked story's `size` (if the caller supplies one)
    get mapped through the table. Neither source available -> `""` (the
    caller/`sum_estimates` treats a blank the same as any other unparsable
    entry, not a crash).

    A truthy but UNPARSABLE explicit string ("-2d" -- a negative not matched
    by `_ESTIMATE_RE`, "3", "~3d") used to be returned as-is on the theory
    that an explicit BA figure always wins -- but "wins" only makes sense for
    a figure `sum_estimates` can actually add up. Returned as-is, it rode
    silently into the caller's `estimates` list and was only dropped once
    `sum_estimates` failed to parse it, folding in a silent `0d` even though
    a linked story's size could have supplied a real range. Treated the same
    as a blank/non-string estimate instead: fall through to the size-derived
    range so effort still folds in."""
    explicit = (task or {}).get("estimate")
    if isinstance(explicit, str) and explicit.strip():
        stripped = explicit.strip()
        if parse_estimate_days(stripped) is not None:
            return stripped
    mapped = map_size_to_range(story_size, table=table)
    return mapped or ""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="effort_map.py",
        description="Map a PO story size to a BA day range, or sum a batch of "
        "BA estimate strings into one rollup figure.",
    )
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--map-size", default=None, help="S|M|L to map to a day range")
    mode.add_argument("--sum", default=None, help="comma-separated estimate strings to sum")
    p.add_argument("--table", default=None, help="path to an override size->range YAML table")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_argparser().parse_args(argv)
    table = load_size_range_table(args.table)
    if args.map_size is not None:
        mapped = map_size_to_range(args.map_size, table=table)
        if mapped is None:
            print("error: unknown size %r (known: %s)" % (args.map_size, sorted(table)), file=sys.stderr)
            return 1
        print(mapped)
        return 0
    if args.sum is not None:
        estimates = [e.strip() for e in args.sum.split(",") if e.strip()]
        print(sum_estimates(estimates))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
