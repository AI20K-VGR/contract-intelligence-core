#!/usr/bin/env python3
"""iso_matrix_score.py — score an ISO/IEC 25010 coverage matrix against the SSOT.

`harness/data/iso-25010-matrix.yaml` declares two decidable rules — `risk_floors`
(how many of the 8 characteristics a task must cover at each risk level) and
`silent_na: reject` (an N/A with no written reason is a defect). Both were being
applied by eye from the `hs:scenario` prose. Counting eight cells per row and
comparing to a per-row threshold is arithmetic, and arithmetic a model does from
memory is a number nobody downstream can check. This module does the counting.

Input is one JSON array of rows:

    [{"task": "task-041", "risk": "high", "cells": {
        "functional_suitability": {"state": "covered", "layer": "unit"},
        "usability": {"state": "na", "reason": "internal migration, no UI"},
        "portability": {"state": "gap"}, ...}}]

Every defect is a sentence naming the task, the characteristic, and the numbers —
a verdict a reader can disagree with is worth more than a bare FAIL.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

_SSOT = _HERE.parent / "data" / "iso-25010-matrix.yaml"

# The test-layer vocabulary the reference maps covered cells onto. A covered cell
# whose layer is outside this set is unverifiable prose, so it is refused rather
# than counted — the same reason a covered cell with NO layer is refused.
LAYERS = ("unit", "integration", "contract", "e2e", "security",
          "load", "uat", "manual", "regression", "review")

STATES = ("covered", "na", "gap")


class IsoMatrixError(Exception):
    """The SSOT is unreadable or malformed — fail closed, never a default floor."""


def _load(path: Optional[Path] = None) -> dict:
    p = Path(path) if path else _SSOT
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise IsoMatrixError("cannot read the ISO matrix SSOT %s (%s)" % (p, exc))
    import yaml_io
    doc = yaml_io.yaml_load(text)
    if not isinstance(doc, dict):
        raise IsoMatrixError("the ISO matrix SSOT %s is not a mapping" % p)
    return doc


def characteristic_ids(path: Optional[Path] = None) -> List[str]:
    """The canonical characteristic ids, in SSOT order. Read, never re-hardcoded —
    the file's own header asks consumers not to copy the list."""
    chars = _load(path).get("characteristics") or []
    out = [str(c["id"]) for c in chars if isinstance(c, dict) and c.get("id")]
    if not out:
        raise IsoMatrixError("the ISO matrix SSOT declares no characteristics")
    return out


def risk_floors(path: Optional[Path] = None) -> Dict[str, int]:
    floors = _load(path).get("risk_floors") or {}
    if not isinstance(floors, dict) or not floors:
        raise IsoMatrixError("the ISO matrix SSOT declares no risk_floors")
    return {str(k): int(v) for k, v in floors.items()}


def rejects_silent_na(path: Optional[Path] = None) -> bool:
    """`silent_na: reject` is a knob, not decoration: a SSOT set to `allow` must
    actually stop rejecting, or the key is a comment with extra steps."""
    return str(_load(path).get("silent_na", "reject")).strip().lower() == "reject"


@dataclass
class RowScore:
    task: str
    risk: str
    covered: int
    floor: int
    defects: List[str] = field(default_factory=list)


@dataclass
class MatrixScore:
    verdict: str
    rows_scored: int
    rows: List[RowScore] = field(default_factory=list)
    defects: List[str] = field(default_factory=list)


def score_row(task: str, risk: str, cells: dict, path: Optional[Path] = None) -> RowScore:
    ids = characteristic_ids(path)
    floors = risk_floors(path)
    strict_na = rejects_silent_na(path)
    defects: List[str] = []

    floor = floors.get(str(risk).strip().lower())
    if floor is None:
        # NOT a default floor: an unrecognised risk means the row was never scored
        # against anything, and reporting a pass there is worse than reporting nothing.
        defects.append(
            "%s: risk %r is not one of %s — the row cannot be scored against a floor"
            % (task, risk, ", ".join(sorted(floors))))
        floor = max(floors.values())

    cells = cells if isinstance(cells, dict) else {}
    for name in cells:
        if name not in ids:
            defects.append(
                "%s: %r is not an ISO 25010 characteristic (expected one of: %s)"
                % (task, name, ", ".join(ids)))

    covered = 0
    for cid in ids:
        cell = cells.get(cid)
        if cell is None:
            defects.append("%s: %s is missing — every characteristic needs a "
                           "covered / N-A-with-reason / gap decision" % (task, cid))
            continue
        if not isinstance(cell, dict):
            defects.append("%s: %s is %r, expected a mapping with a `state`"
                           % (task, cid, cell))
            continue

        state = str(cell.get("state", "")).strip().lower()
        if state not in STATES:
            defects.append("%s: %s has state %r — expected one of %s"
                           % (task, cid, cell.get("state"), ", ".join(STATES)))
            continue

        if state == "covered":
            layer = str(cell.get("layer", "")).strip().lower()
            if not layer:
                # From the reference, verbatim: a covered cell without a named layer
                # is actually a gap. Without this the floor is satisfied by typing
                # the word "covered" eight times.
                defects.append("%s: %s is covered but names no test layer — a "
                               "covered cell without a layer is a gap" % (task, cid))
                continue
            if layer not in LAYERS:
                defects.append("%s: %s names layer %r, which is not a test layer "
                               "(expected one of: %s)"
                               % (task, cid, cell.get("layer"), ", ".join(LAYERS)))
                continue
            covered += 1
        elif state == "na" and strict_na and not str(cell.get("reason", "")).strip():
            defects.append("%s: %s is N/A with no reason — a silent N/A is a defect, "
                           "not coverage (one sentence is enough)" % (task, cid))

    if covered < floor:
        defects.append("%s: %d of 8 characteristics covered, below the %s floor of %d"
                       % (task, covered, risk, floor))

    return RowScore(task=task, risk=str(risk), covered=covered, floor=floor,
                    defects=defects)


def score_matrix(rows: list, path: Optional[Path] = None) -> MatrixScore:
    scored: List[RowScore] = []
    defects: List[str] = []
    for i, row in enumerate(rows or []):
        if not isinstance(row, dict):
            defects.append("row %d is %r, expected a mapping" % (i, row))
            continue
        r = score_row(str(row.get("task", "row-%d" % i)), row.get("risk", ""),
                      row.get("cells") or {}, path=path)
        scored.append(r)
        defects.extend(r.defects)

    if not scored:
        # Zero rows is the shape of a scorer that never ran. PASS here is exactly the
        # false green this module exists to prevent.
        return MatrixScore(verdict="EMPTY", rows_scored=0, rows=[],
                           defects=defects + ["no rows were scored — an empty matrix "
                                              "is not coverage"])
    return MatrixScore(verdict="FAIL" if defects else "PASS",
                       rows_scored=len(scored), rows=scored, defects=defects)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="iso_matrix_score",
        description="score an ISO 25010 coverage matrix against risk_floors + silent_na")
    ap.add_argument("matrix", help="path to the matrix JSON (an array of rows)")
    ap.add_argument("--config", help="alternate ISO matrix SSOT (default: shipped)")
    ap.add_argument("--json", action="store_true", help="emit the verdict as JSON")
    args = ap.parse_args(argv)

    try:
        rows = json.loads(Path(args.matrix).read_text(encoding="utf-8"))
    except OSError as exc:
        sys.stderr.write("cannot read %s (%s)\n" % (args.matrix, exc))
        return 2
    except ValueError as exc:
        sys.stderr.write("%s is not valid json: %s\n" % (args.matrix, exc))
        return 2
    if not isinstance(rows, list):
        sys.stderr.write("%s must hold a json array of rows\n" % args.matrix)
        return 2

    try:
        m = score_matrix(rows, path=Path(args.config) if args.config else None)
    except IsoMatrixError as exc:
        sys.stderr.write("%s\n" % exc)
        return 2

    if args.json:
        sys.stdout.write(json.dumps({
            "verdict": m.verdict,
            "rows_scored": m.rows_scored,
            "rows": [{"task": r.task, "risk": r.risk, "covered": r.covered,
                      "floor": r.floor, "defects": r.defects} for r in m.rows],
            "defects": m.defects,
        }, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write("%s — %d row(s) scored, %d defect(s)\n"
                         % (m.verdict, m.rows_scored, len(m.defects)))
        for r in m.rows:
            sys.stdout.write("  %-24s %s  %d/8 (floor %d)\n"
                             % (r.task, r.risk, r.covered, r.floor))
        for d in m.defects:
            sys.stdout.write("  - %s\n" % d)

    return 0 if m.verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
