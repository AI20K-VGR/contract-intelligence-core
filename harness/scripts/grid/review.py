"""QA grid-review gate — blocks a planner grid from reaching the executor
unless it satisfies the anti-confab/density/evidence contract. Two-tier
review:

  1. Deterministic invariants (``run_invariants``) + confab detector
     (``detect_confabulation``) — sub-second, 0-token, always runs.
  2. Optional Advisor escalation — only when the deterministic pass is
     already clean of a reject but HIGH-density_tier heuristics warrant a semantic
     sanity check.

Emits a ``GridReviewVerdict`` with ``gate='grid'``. Deterministic by default:
a call with no advisor invoker (``invoke_advisor=None``, the default) still
returns a full verdict at 0 tokens. The advisor seam only ever TIGHTENS a
verdict, never loosens it — see ``review_grid`` below.

Port note (TS async -> Python sync): ``qaGridReview.ts``'s ``AdvisorInvoker``
is an async callable; here it is a plain synchronous callable, matching the
rest of this tầng-1 grid package (``expander.py`` made the same choice).
"""
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .axes import EXECUTOR_AXIS_IDS, PLANNER_AXIS_IDS, strength_config
from .confab import ConfabFinding, cells_exceeding_signal_threshold, detect_confabulation
from .density import DensityConfig
from .expander import is_evidence_well_anchored, lint_tier_mismatch
from .invariants import InvariantReport, run_invariants
from .stopping import compute_coverage_ratio
from .types import CellResolution, Grid, GridDensityTier, GridCell

VERDICT_PASS = "pass"
VERDICT_NEEDS_DETAIL = "needs-detail"
VERDICT_REJECT = "reject"


@dataclass
class ReviewFinding:
    invariant: str
    severity: str  # "advisory" | "blocking" | "critical"
    explanation: str
    fix_hint: str
    cell_coordinates: Optional[Dict[str, str]] = None


@dataclass
class AdvisorRequest:
    grid: Grid
    suspect_cells: List[GridCell]
    questions: List[str]


@dataclass
class AdvisorVerdict:
    verdict: str  # "pass" | "needs-detail" | "reject"
    confidence: str  # "high" | "medium" | "low"
    notes: Optional[str] = None


# Sync seam (TS: async, returns Promise<AdvisorVerdict>). Conceptually maps
# to hs:escalation-consultant for tầng-1 callers, but stays a plain injectable
# callable — default None means deterministic-only, no agent/orchestrator
# import here.
AdvisorInvoker = Callable[[AdvisorRequest], AdvisorVerdict]


@dataclass
class EscalationContext:
    grid: Grid
    policy: DensityConfig
    suspect_cells: List[GridCell]
    coverage: float


@dataclass
class AxisSelection:
    """A ``--axes-src`` producer's (``@grid-axis-selector`` or any other
    writer honoring the same contract) reasons-dict receipt: which axes made
    it into the grid and why, keyed by ``"<axis>"`` or ``"<axis>=<value>"``.
    Producer-agnostic — review only reads this shape, never who wrote it."""

    axes: List[str]
    reasons: Dict[str, str]


_AXIS_UNIVERSE = frozenset(PLANNER_AXIS_IDS) | frozenset(EXECUTOR_AXIS_IDS)


def load_axis_selection(path) -> AxisSelection:
    """Load + validate a ``grid-axis-src.json`` (the ``--axes-src`` seam).
    Fail-LOUD (``ValueError``), never a silent fallback, on: unreadable/
    malformed JSON, a non-object document, ``axes`` not a list, an axis id
    outside the universe (``grid-axes.yaml``), or a missing ``reasons``
    dict (mirrors ``axes.py``'s fail-closed style)."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError("axis selection %r unreadable: %s" % (path, exc)) from exc
    except ValueError as exc:
        raise ValueError("axis selection %r is not valid JSON: %s" % (path, exc)) from exc

    if not isinstance(raw, dict):
        raise ValueError("axis selection %r is not a JSON object" % path)
    axes_list = raw.get("axes")
    if not isinstance(axes_list, list):
        raise ValueError("axis selection %r: 'axes' must be a list" % path)
    unknown = [a for a in axes_list if a not in _AXIS_UNIVERSE]
    if unknown:
        raise ValueError(
            "axis selection %r references unknown axis id(s) %r (universe: %r)"
            % (path, unknown, sorted(_AXIS_UNIVERSE))
        )
    reasons = raw.get("reasons")
    if not isinstance(reasons, dict):
        raise ValueError("axis selection %r missing a 'reasons' dict" % path)
    return AxisSelection(axes=list(axes_list), reasons=dict(reasons))


@dataclass
class RevalidateRequest:
    grid: Grid
    cell: GridCell


# Sync seam cloned from ``AdvisorInvoker`` above — a SEPARATE, independent
# lane (gemini/partner via a later phase's SKILL spawn relayer) for a
# post-fill re-derivation pass over HIGH cells. Distinct from the advisor
# escalation seam: revalidate is hậu-fill (after fill), the advisor escalation
# is a pre-executor sanity check; neither ever calls the other.
RevalidateInvoker = Callable[[RevalidateRequest], AdvisorVerdict]


def revalidate_high_cells(grid: Grid, invoker: Optional[RevalidateInvoker]) -> List[ReviewFinding]:
    """Re-drive every HIGH cell through an injected second-engine lane AFTER
    fill -- independent of both the advisor escalation seam and the
    axes-selector seam (neither gates nor is gated by this). ``invoker=None``
    degrades SOFTLY (one advisory finding, mirrors the advisor-throw path
    below), never raises."""
    if invoker is None:
        return [
            ReviewFinding(
                invariant="REVALIDATE:UNAVAILABLE",
                severity="advisory",
                explanation="revalidate requested but no lane invoker was injected — skipping re-derivation",
                fix_hint="wire a revalidate_invoker (gemini/partner lane) or omit --revalidate",
            )
        ]
    findings: List[ReviewFinding] = []
    for cell in grid.cells:
        if cell.resolution != CellResolution.HIGH:
            continue
        try:
            verdict = invoker(RevalidateRequest(grid=grid, cell=cell))
        except Exception:
            findings.append(
                ReviewFinding(
                    invariant="REVALIDATE:UNAVAILABLE",
                    severity="advisory",
                    cell_coordinates=cell.coordinates,
                    explanation="revalidate lane call failed — retaining the original HIGH resolution",
                    fix_hint="retry revalidate or accept the original HIGH resolution",
                )
            )
            continue
        if verdict.verdict == VERDICT_REJECT:
            findings.append(
                ReviewFinding(
                    invariant="REVALIDATE:REJECT",
                    severity="advisory",
                    cell_coordinates=cell.coordinates,
                    explanation=verdict.notes or "revalidate lane rejected this HIGH cell",
                    fix_hint="review the flagged HIGH cell",
                )
            )
        elif verdict.verdict == VERDICT_NEEDS_DETAIL:
            findings.append(
                ReviewFinding(
                    invariant="REVALIDATE:NEEDS_DETAIL",
                    severity="advisory",
                    cell_coordinates=cell.coordinates,
                    explanation=verdict.notes or "revalidate lane flagged this HIGH cell for more detail",
                    fix_hint="review the flagged HIGH cell",
                )
            )
    return findings


@dataclass
class GridReviewInput:
    grid: Grid
    policy: DensityConfig
    invoke_advisor: Optional[AdvisorInvoker] = None
    should_escalate: Optional[Callable[[EscalationContext], bool]] = None
    now: Optional[Callable[[], str]] = None
    # Additive review seams — every one defaults to inert (None/False), so a
    # caller supplying none of them gets a BYTE-IDENTICAL verdict to the
    # pre-seam baseline.
    axis_selection: Optional[AxisSelection] = None
    revalidate: bool = False
    revalidate_invoker: Optional[RevalidateInvoker] = None
    # Duck-typed (mirrors GridLoopConfig.frozen_rules): never import
    # preregister.py here — only grid_engine.py's --rules loader produces a
    # real FrozenRuleset. Default None -> fail-closed, 0 N/A credit.
    frozen_rules: Optional[Any] = None


@dataclass
class GridReviewVerdict:
    gate: str
    verdict: str
    findings: List[ReviewFinding]
    confidence: str
    advisor_consulted: bool
    timestamp: str
    invariant_report: InvariantReport
    confab_findings: List[ConfabFinding] = field(default_factory=list)
    # Provenance passthrough: flows to the grid-decisions module + the
    # coverage-grid artifact. None when no --axes-src was threaded in.
    axis_selection: Optional[AxisSelection] = None


# Post-build axis-fitness safety net. Threshold lives in the strength SSOT
# (grid-strength.yaml: na_ratio_refit); this default only applies if that read
# raises. Deliberately NOT a coverage-floor value (floor-literal guard).
NA_RATIO_REFIT_DEFAULT = 0.66


def _resolve_na_refit_threshold() -> float:
    try:
        return strength_config()["na_ratio_refit"]
    except Exception:
        return NA_RATIO_REFIT_DEFAULT


def _na_ratio(grid: Grid) -> float:
    total = len(grid.cells)
    if not total:
        return 0.0
    na = sum(1 for c in grid.cells if c.resolution == CellResolution.NA)
    return na / total


def review_grid(review_input: GridReviewInput) -> GridReviewVerdict:
    """Run the two-tier review and return a full verdict. Deterministic and
    0-token when ``review_input.invoke_advisor`` is None (the default)."""
    grid = review_input.grid
    policy = review_input.policy
    now = review_input.now or (lambda: datetime.now(timezone.utc).isoformat())

    invariant_report = run_invariants(grid, policy, frozen_rules=review_input.frozen_rules)
    confab_findings = detect_confabulation(grid)
    findings: List[ReviewFinding] = []

    for fail in invariant_report.failed:
        findings.append(
            ReviewFinding(
                invariant=fail.name,
                severity=fail.severity,
                cell_coordinates=fail.cell_coordinates,
                explanation=fail.details or f"{fail.name} failed",
                fix_hint=fix_hint_for(fail.name),
            )
        )

    for f in confab_findings:
        findings.append(
            ReviewFinding(
                invariant=f"CONFAB:{f.signal}",
                severity=confab_severity_for(f.signal),
                cell_coordinates=f.coordinates,
                explanation=f.details,
                fix_hint=confab_fix_hint_for(f.signal),
            )
        )

    # Post-hoc keyword lint (replaces the retired pre-hoc tier-suggestion
    # router) — a cell touching a STRONG-tier keyword
    # but resolved thin earns one advisory finding. Advisory-not-gate: this
    # can only ever land on VERDICT_NEEDS_DETAIL via determine_deterministic_
    # verdict below, never VERDICT_REJECT.
    for tier_finding in lint_tier_mismatch(grid):
        findings.append(
            ReviewFinding(
                invariant="TIER_MISMATCH",
                severity="advisory",
                cell_coordinates=tier_finding.coordinates,
                explanation=tier_finding.detail,
                fix_hint=fix_hint_for("TIER_MISMATCH"),
            )
        )

    # Post-build axis-fitness safety net: an N/A wall past the refit threshold
    # with NO axis-selection receipt means the axes were most likely left as
    # the canned defaults, unpruned for this project. Advisory (the grid may
    # already reject on coverage floor) — its value is naming the RIGHT remedy
    # (@grid-axis-selector) instead of the generic "expand more cells". Silent
    # once a receipt exists: a high N/A ratio is then a reviewed, deliberate
    # outcome, not a mismatch to nag about.
    if review_input.axis_selection is None:
        na_ratio = _na_ratio(grid)
        if na_ratio >= _resolve_na_refit_threshold():
            findings.append(
                ReviewFinding(
                    invariant="AXIS_FITNESS",
                    severity="advisory",
                    explanation=(
                        "na_ratio=%.4f past the refit threshold with no axis-selection "
                        "receipt — the grid axes are likely mismatched to this project" % na_ratio
                    ),
                    fix_hint=(
                        "run @grid-axis-selector (subagent_type hs:grid-axis-selector) to prune/"
                        "replace axis values for this project, then rebuild the grid"
                    ),
                )
            )

    # --revalidate is a SEPARATE, opt-in, post-fill pass — independent of
    # both the axis-selector seam (below) and the advisor escalation seam.
    # Gated on review_input.revalidate ONLY, never on axis_selection.
    if review_input.revalidate:
        findings.extend(revalidate_high_cells(grid, review_input.revalidate_invoker))

    # Anti-fraud: a rule:<id> N/A that fails verify_na_points_to_frozen_rule
    # (fabricated id, inapplicable combo, tampered hash, non-forbidding
    # verdict) is not merely denied coverage credit -- it is a hard REJECT.
    # Deferred import mirrors stopping.compute_coverage_ratio's own
    # frozen_rules-gated import of the same module (only runs once a caller
    # actually threads a frozen ruleset through).
    forged_rule_refs = []
    if review_input.frozen_rules is not None:
        from .preregister import assert_no_unfrozen_rule_ref
        forged_rule_refs = assert_no_unfrozen_rule_ref(grid, review_input.frozen_rules)
        for v in forged_rule_refs:
            findings.append(
                ReviewFinding(
                    invariant="FORGED_RULE_REF",
                    severity="critical",
                    cell_coordinates=v.cell_coordinates,
                    explanation="N/A cell cites rule:%s, which does not verify against "
                                "the frozen ruleset (%s)" % (v.rule_id, v.reason),
                    fix_hint="point the N/A attestation at a rule genuinely present in "
                             "the frozen ruleset, or fill the cell",
                )
            )

    suspect_cells = collect_suspect_cells(grid, confab_findings, policy)
    verdict = determine_deterministic_verdict(invariant_report, findings)
    if forged_rule_refs:
        verdict = VERDICT_REJECT
    confidence = "high" if (verdict == VERDICT_REJECT or not findings) else "medium"

    advisor_consulted = False
    if (
        verdict != VERDICT_REJECT
        and review_input.invoke_advisor is not None
        and should_escalate_to_advisor(review_input, suspect_cells)
    ):
        try:
            advisor = review_input.invoke_advisor(
                AdvisorRequest(
                    grid=grid,
                    suspect_cells=suspect_cells,
                    questions=advisor_questions_for(suspect_cells),
                )
            )
            advisor_consulted = True
            if advisor.verdict == VERDICT_REJECT:
                verdict = VERDICT_REJECT
            elif advisor.verdict == VERDICT_NEEDS_DETAIL and verdict == VERDICT_PASS:
                verdict = VERDICT_NEEDS_DETAIL
            confidence = advisor.confidence
            if advisor.notes:
                findings.append(
                    ReviewFinding(
                        invariant="ADVISOR:NOTE",
                        severity="advisory",
                        explanation=advisor.notes,
                        fix_hint="review advisor recommendation",
                    )
                )
        except Exception:
            # Advisor call is never allowed to propagate — keep the
            # deterministic verdict and flag the gap instead.
            findings.append(
                ReviewFinding(
                    invariant="ADVISOR:UNAVAILABLE",
                    severity="advisory",
                    explanation="Advisor call failed — retaining deterministic verdict",
                    fix_hint="retry with advisor or accept deterministic outcome",
                )
            )

    return GridReviewVerdict(
        gate="grid",
        verdict=verdict,
        findings=findings,
        confidence=confidence,
        advisor_consulted=advisor_consulted,
        timestamp=now(),
        invariant_report=invariant_report,
        confab_findings=confab_findings,
        axis_selection=review_input.axis_selection,
    )


def determine_deterministic_verdict(report: InvariantReport, findings: List[ReviewFinding]) -> str:
    """Fixed order (qaGridReview.ts:177-186) — do NOT reorder: any critical
    finding, then any blocking-invariant failure, then any blocking finding,
    then any advisory finding, else clean."""
    if any(f.severity == "critical" for f in findings):
        return VERDICT_REJECT
    if not report.all_blocking_passed:
        return VERDICT_REJECT
    if any(f.severity == "blocking" for f in findings):
        return VERDICT_REJECT
    if any(f.severity == "advisory" for f in findings):
        return VERDICT_NEEDS_DETAIL
    return VERDICT_PASS


def should_escalate_to_advisor(review_input: GridReviewInput, suspect_cells: List[GridCell]) -> bool:
    """Default trigger (qaGridReview.ts:188-208): density_tier HIGH with >=3 suspect
    cells, OR coverage sitting in the narrow density_tier just at the floor
    (``[floor, floor + 0.02)``). A caller-supplied ``should_escalate``
    overrides both defaults entirely. ``coverage`` here is DEPTH
    (``compute_coverage_ratio``), not breadth — a grid padded with honest
    STUBs to inflate breadth must not dodge this escalation density_tier."""
    grid = review_input.grid
    coverage = compute_coverage_ratio(grid)

    if review_input.should_escalate is not None:
        return review_input.should_escalate(
            EscalationContext(
                grid=grid,
                policy=review_input.policy,
                suspect_cells=suspect_cells,
                coverage=coverage,
            )
        )
    if grid.density_tier == GridDensityTier.HIGH and len(suspect_cells) >= 3:
        return True
    floor = review_input.policy.coverage_floor
    if floor <= coverage < floor + 0.02:
        return True
    return False


def collect_suspect_cells(grid: Grid, confab: List[ConfabFinding], policy: DensityConfig) -> List[GridCell]:
    """Cells the advisor should look at: any cell whose confab signals reach the
    per-cell signal threshold, plus any HIGH cell whose evidence fails the
    anchor-prefix check (qaGridReview.ts:210-234)."""
    confab_coords = cells_exceeding_signal_threshold(confab, policy.confab_signal_threshold)
    flagged_keys = {_coord_key(c) for c in confab_coords}
    suspects: List[GridCell] = []
    for cell in grid.cells:
        if _coord_key(cell.coordinates) in flagged_keys:
            suspects.append(cell)
            continue
        if cell.resolution == CellResolution.HIGH and any(
            not is_evidence_well_anchored(e) for e in (cell.evidence or [])
        ):
            suspects.append(cell)
    return suspects


def advisor_questions_for(cells: List[GridCell]) -> List[str]:
    return [
        "Does each cell content actually address its coordinates?",
        "Does evidence plausibly support the HIGH claim?",
        "Would a missing/STUB cell leave an observable gap?",
        f"Review {len(cells)} suspect cell(s) for confabulation.",
    ]


def _coord_key(coords: Dict[str, str]) -> str:
    return "|".join(f"{k}={v}" for k, v in sorted(coords.items()))


def confab_severity_for(_signal: str) -> str:
    """Confab detector is a heuristic first-pass — every signal surfaces as
    advisory at this layer. Blocking escalation happens via invariant checks
    (HIGH_NEEDS_EVIDENCE is blocking on its own) or via the advisor once
    signals accumulate past the per-cell threshold — never here."""
    return "advisory"


_FIX_HINTS: Dict[str, str] = {
    "CA_COVERAGE": (
        "regenerate the covering array — every t-tuple of axis values must be covered by >=1 cell"
    ),
    "NO_ORPHAN_CELL": "every cell must carry coordinates for exactly the declared axes",
    "COVERAGE_FLOOR": "expand more SKELETON cells or attest them as STUB/N/A",
    "STUB_REASON_REQUIRED": "add attestation text to every STUB/MISSING/N/A cell",
    "HIGH_NEEDS_EVIDENCE": (
        "attach evidence[] prefixed (src/|tests/|PLAN-|TASK-|RFC-|metric:|axis:) or downgrade to STUB"
    ),
    "PHANTOM_EVIDENCE": "replace evidence strings with real file paths / plan refs",
    "ITERATION_HONEST": "either stay under iterationsMax or attest iteration exhaustion on ≥1 cell",
    "TIER_MISMATCH": (
        "cell touches a strong-tier keyword (security/auth/crypto/...) but was resolved "
        "thin — review whether it deserves deeper treatment"
    ),
}

_FIX_HINT_DEFAULT = "review the flagged cells and patch per policy"


def fix_hint_for(name: str) -> str:
    return _FIX_HINTS.get(name, _FIX_HINT_DEFAULT)


_CONFAB_FIX_HINTS: Dict[str, str] = {
    "UNANCHORED_HIGH": "provide evidence[] or downgrade to STUB",
    "PHANTOM_EVIDENCE": "replace evidence strings with real prefixes",
    "DUPLICATE_CONTENT": "remove recycled filler — attest as STUB or rewrite",
    "COORDINATE_LEAK": "expand beyond restating coordinates",
    "HEDGING_DENSITY": "replace hedging language with concrete claims or downgrade to STUB",
    "STUB_AVOIDANCE": "content under 40 chars is not HIGH — STUB with attestation",
}

_CONFAB_FIX_HINT_DEFAULT = "review confab signal"


def confab_fix_hint_for(signal: str) -> str:
    return _CONFAB_FIX_HINTS.get(signal, _CONFAB_FIX_HINT_DEFAULT)
