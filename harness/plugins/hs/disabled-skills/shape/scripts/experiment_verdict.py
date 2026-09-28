#!/usr/bin/env python3
"""experiment_verdict — apply an experiment's own decision_rule to a PO-supplied
metric result (the second clamp of the verification-tiering rule).

This module NEVER fetches or measures anything itself: `apply_verdict` takes
``actual`` as a plain number the caller (a human PO, or a script reading a
number off an analytics export) already has in hand. It reads the spec's
``decision_rule`` (written by ``experiment_spec.author``), computes a
deterministic 3-tier verdict off it, and writes the result back onto the SAME
EXP-<n>.md file (status -> "concluded"). The RUN itself — soliciting real
customers, collecting the metric — is market territory the PO owns outside the
harness; multi-run unattended orchestration is tầng-2 (`orchestrator/`), never
imported here.

Verdict math models the same 3-tier ratio-floor computation as
``outcome_verdict.py`` (see the "Verdict math" paragraph in
frontmatter-and-id-spec.md's Outcome records section) — reimplemented locally
rather than imported, since that module lives in the superseded standalone
product-spec tree, not something this skill can depend on.
"""

from __future__ import annotations

import argparse
import datetime
import fcntl
import math
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

RootLike = Any  # str | Path, kept untyped to avoid a PEP-604 union annotation

# Sibling import (same pattern as dec_ledger.py -> id_grammar.py): insert this
# file's own directory and import by bare name. Import machinery checks
# sys.modules FIRST, so under the isolated test loader (which pre-registers
# "experiment_spec" in sys.modules before exec'ing this file) this resolves
# to that exact loaded copy instead of re-reading the file from disk.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import experiment_spec as _experiment_spec  # noqa: E402

ExperimentError = _experiment_spec.ExperimentError
SidecarError = _experiment_spec.SidecarError


class VerdictError(ExperimentError):
    """Raised on a malformed verdict input (unknown experiment, non-numeric
    actual, malformed/missing decision_rule) -- a clear error, never a raw
    parser/KeyError traceback."""


VERDICTS = ("hit", "partial", "miss")


def _num(value) -> Optional[float]:
    """float(value) if it parses as a FINITE number, else None."""
    if value is None or isinstance(value, bool):
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def compute_verdict(direction: str, target: float, actual: float,
                    hit_floor: float, partial_floor: float) -> str:
    """Deterministic 3-tier verdict (pure function, no I/O).

    ``lower`` with actual <= 0 is the best possible outcome -> hit: 0 avoids
    the div-by-zero, and a NEGATIVE actual (an ordinary value for a "lower is
    better" delta metric -- e.g. a churn delta of -3% means churn FELL, better
    than 0) would otherwise sign-flip ``target/actual`` negative and cliff the
    verdict straight to "miss", misclassifying an excellent result as the
    worst. Model assumption: ``target`` must be strictly positive -- the ratio
    this function computes (``actual/target`` for "higher", ``target/actual``
    for "lower") sign-flips on a negative target, e.g. direction="higher",
    target=-5, actual=-10 gives ratio = -10/-5 = 2.0 >= hit_floor -> "hit",
    even though -10 is a WORSE outcome than -5. Caller guarantees target > 0
    (validate_decision_rule enforces this at author/verdict time, before this
    function ever runs).
    """
    if direction == "lower":
        ratio = float("inf") if actual <= 0 else target / actual
    else:
        ratio = actual / target
    if ratio >= hit_floor:
        return "hit"
    if ratio >= partial_floor:
        return "partial"
    return "miss"


def _now_iso_date() -> str:
    return datetime.datetime.now(datetime.timezone.utc).date().isoformat()


def apply_verdict(
    root: RootLike,
    exp_id: str,
    actual: Any,
    measured_on: Optional[str] = None,
    actor: Optional[str] = None,
) -> Dict[str, Any]:
    """Read EXP-<n>.md's decision_rule, apply it to ``actual``, write the
    verdict back (status -> concluded). Raises VerdictError on any malformed
    input instead of crashing.

    The read-modify-write below runs under an exclusive flock on the SAME
    ``.experiments.lock`` sidecar `experiment_spec.author()` already takes
    (mirroring that sibling idiom) -- without it, two concurrent verdict
    applications (or a verdict racing an allocation) could each read a stale
    frontmatter dict and clobber one another's write.
    """
    actual_num = _num(actual)
    if actual_num is None:
        raise VerdictError(
            "actual metric result is not a finite number for %s: %r" % (exp_id, actual)
        )

    d = _experiment_spec.experiments_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    lock_path = d / ".experiments.lock"
    with open(lock_path, "a+") as lock_fd:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
        try:
            try:
                fm, body = _experiment_spec.read_experiment(root, exp_id)
            except ExperimentError as exc:
                raise VerdictError(str(exc))

            decision_rule = fm.get("decision_rule")
            try:
                _experiment_spec.validate_decision_rule(decision_rule)
            except ExperimentError as exc:
                raise VerdictError("malformed decision_rule on %s: %s" % (exp_id, exc))

            direction = decision_rule["direction"]
            target = float(decision_rule["target"])
            hit_floor = float(decision_rule["hit_floor"])
            partial_floor = float(decision_rule["partial_floor"])
            verdict = compute_verdict(direction, target, actual_num, hit_floor, partial_floor)

            updated = dict(fm)
            updated["status"] = "concluded"
            updated["verdict"] = verdict
            updated["actual"] = actual_num
            updated["measured_on"] = measured_on or _now_iso_date()
            # Always stamp the CURRENT actor: `dict(fm)` copied a stale
            # `verdict_actor` from a prior verdict, and gating only on truthy
            # `actor` left that stale attribution on a re-gate run with no actor.
            # Mirror experiment_spec's `actor or _default_actor()` resolution.
            updated["verdict_actor"] = actor or _experiment_spec._default_actor()

            _experiment_spec.write_experiment(root, exp_id, updated, body)
        finally:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)

    return {
        "id": exp_id,
        "status": updated["status"],
        "verdict": verdict,
        "actual": actual_num,
        "measured_on": updated["measured_on"],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="experiment_verdict.py",
        description="Apply an EXP-<n>'s own decision_rule to a PO-supplied "
        "metric result (second clamp of the verification-tiering rule). Never runs/fetches anything.",
    )
    p.add_argument("--root", required=True, help="workspace root (holds docs/product/)")
    p.add_argument("--id", required=True, help="EXP-<n> id")
    p.add_argument("--actual", required=True, help="the PO-supplied metric result")
    p.add_argument("--measured-on", default=None, help="ISO date; defaults to today (UTC)")
    p.add_argument("--actor", default=None)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_argparser().parse_args(argv)
    try:
        result = apply_verdict(
            args.root, args.id, args.actual,
            measured_on=args.measured_on, actor=args.actor,
        )
    except (VerdictError, SidecarError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    print("%s\t%s\t%s" % (result["id"], result["verdict"], result["status"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
