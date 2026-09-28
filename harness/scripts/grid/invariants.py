"""Grid invariants — 8 deterministic, 0-token checks a grid must pass before
a review verdict trusts it or the expansion loop keeps going. Each check is
independent and pure; ``run_invariants`` runs all 8 in a fixed order and
buckets the results.

Token is telemetry-only at tầng-1 (the harness cannot measure it — the model
self-reports ``tokens_used``, see ``expander.py``), so no invariant here
gates on it (the token-honesty check that used to live here was removed). Its
principled-asymmetry twin ``ITERATION_HONEST`` stays, because iteration count
is a quantity the harness itself measures.

Severity ladder: ``blocking`` fails the gate outright, ``critical`` is
reserved for the same bucket at a higher urgency (no check currently emits
it, kept for parity with the TS union type), ``advisory`` surfaces but never
flips ``all_blocking_passed`` to False. COVERAGE_FLOOR's severity is
REAL-CELL-based (Option 3 FIX-E), not density-based: advisory when the grid
has 0 real (HIGH/LOW) cells and every non-SKELETON cell is honestly attested
(an all-STUB/N/A gap, still in progress), blocking once >=1 real cell exists
and depth is still below floor (a real gap, not an honest in-progress state).
NA_RATIO_ADVISORY is the anti-gaming companion — always advisory, fires when
too many cells are labeled N/A regardless of whether any of them are
credited, so mass N/A-labeling to shrink the effective denominator never goes
unnoticed even though Option 3 no longer lets it inflate the ratio.
"""
import re
from dataclasses import dataclass, field
from itertools import combinations, product as iproduct
from typing import Dict, List, Optional

from . import axes
from .density import DensityConfig, density_policy
from .stopping import compute_coverage_ratio
from .types import (
    EVIDENCE_PREFIX_ENV,
    evidence_pattern,
    RESOLUTIONS_REQUIRING_ATTESTATION,
    RESOLUTIONS_REQUIRING_EVIDENCE,
    CellResolution,
    Grid,
    GridCell,
)

_ITERATION_EXHAUSTION_PATTERN = re.compile(r"budget|iteration|cap|exhausted", re.I)

# CA (covering-array) strength floor for _check_ca_coverage — an int
# minimum-t, NOT a coverage-floor ratio, so it never collides with the
# coverage_floor SSOT (harness/data/grid-density-tier.yaml) or its
# float-literal guard. Any grid with real strength >=2 covers this floor's
# 2-tuples as a strict superset, so checking at t=2 never under-verifies a
# richer grid; exact-t verification lives in ca.py's own tests.
DEFAULT_CA_STRENGTH_T = 2

# Defensive fallback ONLY — the real SSOT is grid-strength.yaml's
# na_ratio_bell, read via _resolve_na_threshold()/axes.strength_config().
# 0.30 is not one of this tầng-1 file's own coverage-floor literals
# {0.60, 0.85, 0.95} (the LOW/MID/HIGH values in grid-density-tier.yaml — NOT
# the tầng-2 orchestrator's floor set, a different SSOT), so it never trips
# the floor-literal-guard test that flags a hardcoded copy of the
# coverage_floor SSOT (grid-density-tier.yaml).
NA_RATIO_ADVISORY_DEFAULT = 0.30


@dataclass
class InvariantResult:
    name: str
    passed: bool
    severity: str  # "advisory" | "blocking" | "critical"
    details: Optional[str] = None
    cell_coordinates: Optional[Dict[str, str]] = None


@dataclass
class InvariantReport:
    passed: List[InvariantResult] = field(default_factory=list)
    failed: List[InvariantResult] = field(default_factory=list)
    all_blocking_passed: bool = True
    blocking_failures: int = 0
    critical_failures: int = 0
    advisory_failures: int = 0


def _resolve_na_threshold() -> float:
    """Read the na_ratio_bell threshold from its real SSOT
    (grid-strength.yaml, key ``na_ratio_bell``) via
    ``axes.strength_config()`` — falls back to
    ``NA_RATIO_ADVISORY_DEFAULT`` only if that read raises (missing/malformed
    SSOT), never as the everyday path (OQ3: honor the shipped SSOT, don't
    leave it dead)."""
    try:
        return axes.strength_config()["na_ratio_bell"]
    except Exception:
        return NA_RATIO_ADVISORY_DEFAULT


def run_invariants(
    grid: Grid,
    policy: Optional[DensityConfig] = None,
    na_ratio_advisory: Optional[float] = None,
    frozen_rules=None,
) -> InvariantReport:
    """Run all 8 checks in a fixed order and bucket pass/fail. ``policy``
    defaults to the grid's own density_tier policy — pass an explicit one to check a
    grid against a different density_tier's floor/budget. ``na_ratio_advisory``
    overrides the NA_RATIO_ADVISORY threshold (default resolves from the
    grid-strength.yaml SSOT); ``frozen_rules`` threads through to
    COVERAGE_FLOOR's depth numerator (default None -> fail-closed, no N/A
    credited)."""
    if policy is None:
        policy = density_policy(grid.density_tier)
    thr = na_ratio_advisory if na_ratio_advisory is not None else _resolve_na_threshold()

    results = [
        _check_ca_coverage(grid),
        _check_no_orphan_cell(grid),
        _check_coverage_floor(grid, policy, frozen_rules),
        _check_stub_reason_required(grid),
        _check_high_needs_evidence(grid),
        _check_phantom_evidence(grid),
        _check_iteration_honest(grid),
        _check_na_ratio_advisory(grid, thr),
    ]
    passed = [r for r in results if r.passed]
    failed = [r for r in results if not r.passed]
    return InvariantReport(
        passed=passed,
        failed=failed,
        all_blocking_passed=all(r.severity == "advisory" for r in failed),
        blocking_failures=sum(1 for r in failed if r.severity == "blocking"),
        critical_failures=sum(1 for r in failed if r.severity == "critical"),
        advisory_failures=sum(1 for r in failed if r.severity == "advisory"),
    )


def _check_ca_coverage(grid: Grid) -> InvariantResult:
    """0-missing t-tuple: every combination of t axis-values must appear in
    >=1 cell (generalizes the old count==product full-Cartesian check; when
    t>=len(axes) this reduces to the full-Cartesian identity)."""
    axes = grid.axes
    t = min(DEFAULT_CA_STRENGTH_T, len(axes))
    missing = []
    for axis_combo in combinations(axes, t):
        for value_combo in iproduct(*[a.values for a in axis_combo]):
            target = {axis_combo[i].id: value_combo[i] for i in range(t)}
            covered = any(
                all(cell.coordinates.get(k) == v for k, v in target.items())
                for cell in grid.cells
            )
            if not covered:
                missing.append(target)
    passed = not missing
    details = None if passed else f"missing {len(missing)} {t}-tuple(s): {missing[:3]}"
    return InvariantResult(name="CA_COVERAGE", passed=passed, severity="blocking", details=details)


def _check_no_orphan_cell(grid: Grid) -> InvariantResult:
    axis_ids = {a.id for a in grid.axes}
    for cell in grid.cells:
        if len(cell.coordinates) != len(axis_ids):
            return InvariantResult(
                name="NO_ORPHAN_CELL",
                passed=False,
                severity="blocking",
                details=f"coordinate count {len(cell.coordinates)} != axis count {len(axis_ids)}",
                cell_coordinates=cell.coordinates,
            )
        for key in cell.coordinates:
            if key not in axis_ids:
                return InvariantResult(
                    name="NO_ORPHAN_CELL",
                    passed=False,
                    severity="blocking",
                    details=f"unknown coordinate key '{key}'",
                    cell_coordinates=cell.coordinates,
                )
    return InvariantResult(name="NO_ORPHAN_CELL", passed=True, severity="blocking")


def _check_coverage_floor(grid: Grid, policy: DensityConfig, frozen_rules=None) -> InvariantResult:
    if not grid.cells:
        return InvariantResult(name="COVERAGE_FLOOR", passed=False, severity="blocking", details="no cells")
    ratio = compute_coverage_ratio(grid, frozen_rules)  # DEPTH measure, frozen_rules threaded (None -> fail-closed)
    # FIX-E — severity by REAL CONTENT, never by density (breadth). Fork M
    # (user-locked): an all-STUB/N/A honest gap is advisory; >=1 real cell
    # still below floor is a real gap and blocks.
    real_cells = [c for c in grid.cells if c.resolution in (CellResolution.HIGH, CellResolution.LOW)]
    non_skeleton = [c for c in grid.cells if c.resolution != CellResolution.SKELETON]
    all_attested = all(
        c.attestation for c in non_skeleton if c.resolution in RESOLUTIONS_REQUIRING_ATTESTATION
    )
    if not real_cells and all_attested:
        severity = "advisory"  # all-STUB/N/A honestly attested — STUB_REASON_REQUIRED covers the gap itself
    else:
        severity = "blocking"  # >=1 real cell (or an unattested non-skeleton cell) below floor
    passed = ratio >= policy.coverage_floor
    details = None if passed else f"coverage={ratio:.4f} floor={policy.coverage_floor}"
    return InvariantResult(name="COVERAGE_FLOOR", passed=passed, severity=severity, details=details)


def _check_na_ratio_advisory(grid: Grid, threshold: float) -> InvariantResult:
    """Anti-gaming bell (Option 3): fires whenever too large a share of the
    grid is labeled N/A, independent of whether any of it was credited into
    the COVERAGE_FLOOR numerator — a wall of rule-pointing N/A cells still
    rings this even under a fail-closed (frozen_rules=None) run, so mass
    N/A-labeling never goes unnoticed even when it earns 0 credit."""
    total = len(grid.cells) or 1
    na = sum(1 for c in grid.cells if c.resolution == CellResolution.NA)
    na_ratio = na / total
    passed = na_ratio <= threshold
    details = None if passed else f"na_ratio={na_ratio:.4f} advisory_threshold={threshold}"
    return InvariantResult(name="NA_RATIO_ADVISORY", passed=passed, severity="advisory", details=details)


def _check_stub_reason_required(grid: Grid) -> InvariantResult:
    for cell in grid.cells:
        if cell.resolution in RESOLUTIONS_REQUIRING_ATTESTATION and not cell.attestation:
            return InvariantResult(
                name="STUB_REASON_REQUIRED",
                passed=False,
                severity="blocking",
                details=f"{cell.resolution.value} cell missing attestation",
                cell_coordinates=cell.coordinates,
            )
    return InvariantResult(name="STUB_REASON_REQUIRED", passed=True, severity="blocking")


def _check_high_needs_evidence(grid: Grid) -> InvariantResult:
    for cell in grid.cells:
        if cell.resolution in RESOLUTIONS_REQUIRING_EVIDENCE and not cell.evidence:
            return InvariantResult(
                name="HIGH_NEEDS_EVIDENCE",
                passed=False,
                severity="blocking",
                details="HIGH cell missing evidence",
                cell_coordinates=cell.coordinates,
            )
    return InvariantResult(name="HIGH_NEEDS_EVIDENCE", passed=True, severity="blocking")


def _check_phantom_evidence(grid: Grid) -> InvariantResult:
    # Gathers every offender across every cell (no short-circuit) — unlike
    # the "first offender wins" checks above, this one needs the full list so
    # a caller can see the scope of the anti-confab problem, not just one hit.
    # Resolved once per check: the effective pattern includes any
    # per-project prefixes, and recompiling it per entry would be waste.
    _pattern = evidence_pattern()
    offending: List[str] = []
    for cell in grid.cells:
        for entry in cell.evidence or []:
            if not _pattern.match(entry):
                offending.append(entry)
    passed = not offending
    details = None if passed else _phantom_details(offending)
    return InvariantResult(name="PHANTOM_EVIDENCE", passed=passed, severity="advisory", details=details)


def _phantom_details(offending: List[str]) -> str:
    """Offenders, plus the one hint that makes the finding actionable.

    "phantom evidence" reads as "you made this up", and an author who did NOT
    make it up has no way to tell the difference — the honest reading is often
    "this project's source dir is not in the anchor set". Naming the seam turns
    a dead end into a fix; without it the only escape is to stop citing code."""
    head = ", ".join(offending[:3])
    dirs = sorted({e.split("/", 1)[0] + "/" for e in offending if "/" in e})
    if not dirs:
        return head
    return ("%s — if %s %s a real dir in this project, add it to %s "
            "(comma-separated) rather than dropping the citation"
            % (head, ", ".join(dirs[:3]),
               "are" if len(dirs[:3]) > 1 else "is",
               EVIDENCE_PREFIX_ENV))


def _check_iteration_honest(grid: Grid) -> InvariantResult:
    budget = grid.budget
    if budget.iterations <= budget.iterations_max:
        return InvariantResult(name="ITERATION_HONEST", passed=True, severity="blocking")
    passed = any(
        c.resolution == CellResolution.STUB
        and isinstance(c.attestation, str)
        and _ITERATION_EXHAUSTION_PATTERN.search(c.attestation)
        for c in grid.cells
    )
    details = None if passed else "iterations over cap with no STUB cell attesting exhaustion"
    return InvariantResult(name="ITERATION_HONEST", passed=passed, severity="blocking", details=details)


def summarize_invariant_names(report: InvariantReport) -> Dict[str, List[str]]:
    return {
        "passed": [r.name for r in report.passed],
        "failed": [r.name for r in report.failed],
    }


def is_cell_missing_attestation(cell: GridCell) -> bool:
    return cell.resolution in RESOLUTIONS_REQUIRING_ATTESTATION and not cell.attestation
