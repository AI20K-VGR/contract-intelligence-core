"""Grid stopping — the deterministic referee the expansion loop consults
after every cell: keep going, or stop (and why). Pure function, no I/O.

7 stop reasons, priority order 1 (highest) to 7 (lowest) — a reason never
overrides a higher one even when both conditions hold, so the checks below
run strictly top-to-bottom and return on the first match:

  1. qa-failed                  a blocking invariant already failed
  2. token-budget-exhausted      spent >= the density_tier's own depth token budget
  3. iteration-cap               hit the iteration budget
  4. advisor-escalation-needed    too many confab-flagged cells
  5. density-met                  coverage floor reached
  6. no-progress                  2 consecutive rounds processed 0 new cells
  7. queue-empty                  nothing left to expand
  (else) continue with the next queued cell

Token spend USED to be telemetry-only at tầng-1 — a comment here noted the
harness "cannot measure it", and a matching stop reason was removed. The
removal went one step too far: the loop already accumulates the per-cell
figure into ``grid.budget.depth_tokens_used`` every iteration (``loop.py``),
so a running total exists — it was simply never compared against a ceiling.
Without that comparison the iteration counter was the ONLY runtime spend
fence, and a density_tier's iteration cap can cost several times its own token
budget once real per-cell cost is counted (a MID grid's 40-iteration cap can
spend up to 40 * per_cell_token_cap with nothing checking that this stayed
under ``depth_tokens_max``). The reason is reinstated with a real ceiling
check, placed ABOVE ``iteration-cap``: a run that is out of budget should
stop for THAT reason even when it is also at its iteration cap in the same
step.

HONEST LIMITATION — read before treating this as a spend guarantee. The
running total is built from a figure the MODEL self-reports
(``expander.py``'s ``ExpanderLlmResponse.tokens_used``), and ``loop.py``
adds ``(tokens_spent or 0)``: an invoker that reports nothing contributes
zero, so this fence never fires for it. That makes it a COOPERATIVE fence,
not an enforced one. The enforced bound remains ``iteration-cap``, which
counts a quantity the harness observes itself. The two are complementary,
and the honest worst case is `iterations_max * per_cell_token_cap` for a
non-reporting invoker — bounded, but by the iteration cap alone. Anything
claiming a hard token ceiling at tầng-1 is overstating what this module
can see.

``invariant_report`` (reason 1) is read duck-typed — only
``.all_blocking_passed`` / ``.blocking_failures`` — so this module has no
runtime dependency on ``grid.invariants``. That keeps the two phases free to
run in the same parallel build batch (an import here would create an
undeclared invariants->stopping build-order edge).
"""
from dataclasses import dataclass
from enum import Enum
from typing import Any, List, Optional

from .density import DensityConfig
from .types import CellResolution, Grid, cell_is_resolved


class StopReason(str, Enum):
    DENSITY_MET = "density-met"
    ITERATION_CAP = "iteration-cap"
    TOKEN_BUDGET_EXHAUSTED = "token-budget-exhausted"
    ADVISOR_ESCALATION_NEEDED = "advisor-escalation-needed"
    QA_FAILED = "qa-failed"
    NO_PROGRESS = "no-progress"
    QUEUE_EMPTY = "queue-empty"


@dataclass
class StopDecision:
    # "continue" is a Python keyword, hence the _expansion suffix.
    continue_expansion: bool
    reason: Optional[str] = None
    next_cell: Optional[Any] = None
    details: Optional[str] = None


@dataclass
class ShouldContinueOptions:
    prev_cells_processed: Optional[int] = None
    prev_cells_processed_before: Optional[int] = None
    # Duck-typed: only .all_blocking_passed / .blocking_failures are read.
    # Optional[Any] rather than InvariantReport to avoid a runtime import.
    invariant_report: Optional[Any] = None


def cells_processed(grid: Grid) -> int:
    budget = grid.budget
    return budget.cells_expanded + budget.cells_stubbed + budget.cells_missing


def expansion_breadth_ratio(grid: Grid) -> float:
    """BREADTH: how much of the grid has moved off SKELETON at all
    (non-SKELETON/total) — an honesty-agnostic "touched" ratio. Drives
    density classification (SKELETON/FILLED/DEEP at the 0.5/0.9 thresholds).
    Distinct from ``compute_coverage_ratio`` (depth, below): a grid filled
    entirely with attested STUBs reads breadth=1.0 but depth=0.0. Never reads
    ``frozen_rules`` — breadth has no N/A-verification concept."""
    if not grid.cells:
        return 0.0
    non_skeleton = sum(1 for c in grid.cells if c.resolution != CellResolution.SKELETON)
    return non_skeleton / len(grid.cells)


def compute_coverage_ratio(grid: Grid, frozen_rules=None) -> float:
    """DEPTH (Option-3, fail-closed): numerator = HIGH + LOW cells, plus any
    N/A cell whose attestation points to a pre-registered, frozen "rule:<id>"
    that ``verify_na_points_to_frozen_rule`` (a later phase) confirms
    actually forbids this cell's coordinates. ``frozen_rules=None`` (every
    caller today: density-met below, loop attestation, snapshot) means the
    verify step never runs -> 0 N/A credit. That is FAIL-CLOSED BY DEFAULT,
    not by caller discipline: "no frozen ruleset yet" must never silently
    read as "N/A credited". STUB/MISSING/SKELETON/free-text N/A/unverified
    N/A never enter the numerator — their honesty lives in ``stub_ratio``
    (loop.py), never in this ratio. Denominator is always total cells (an
    empty grid -> 0.0, never a div-by-zero)."""
    if not grid.cells:
        return 0.0
    resolved = 0
    for c in grid.cells:
        if c.resolution in (CellResolution.HIGH, CellResolution.LOW):
            resolved += 1
        elif c.resolution == CellResolution.NA and frozen_rules is not None:
            # Deferred import: this branch only runs once a caller actually
            # threads a frozen ruleset through (frozen_rules is not None).
            # Every caller today passes the default None, so this import
            # never executes and the verify module need not exist yet.
            from .preregister import (
                parse_na_rule_ref,
                verify_na_points_to_frozen_rule,
            )
            rule_id = parse_na_rule_ref(c.attestation or "")
            if rule_id is not None and verify_na_points_to_frozen_rule(
                rule_id, frozen_rules, c.coordinates
            ).ok:
                resolved += 1
    return resolved / len(grid.cells)


def should_continue(
    grid: Grid,
    policy: DensityConfig,
    queue: List[Any],
    options: Optional[ShouldContinueOptions] = None,
) -> StopDecision:
    options = options or ShouldContinueOptions()
    budget = grid.budget

    # 1. qa-failed
    report = options.invariant_report
    if report is not None and not report.all_blocking_passed:
        return StopDecision(
            continue_expansion=False,
            reason=StopReason.QA_FAILED.value,
            details=f"{report.blocking_failures} blocking invariants failed",
        )

    # 2. token-budget-exhausted — a COOPERATIVE spend fence: it fires only
    # for an invoker that actually reports its usage (see the module
    # docstring's honest-limitation note). Guarded on a truthy
    # depth_tokens_max so a grid built with an unset/zero budget (a handful
    # of pre-existing test fixtures) never trips this at
    # depth_tokens_used=0.
    if budget.depth_tokens_max and budget.depth_tokens_used >= budget.depth_tokens_max:
        return StopDecision(
            continue_expansion=False,
            reason=StopReason.TOKEN_BUDGET_EXHAUSTED.value,
            details=f"{budget.depth_tokens_used} tokens spent >= {budget.depth_tokens_max} max",
        )

    # 3. iteration-cap
    if budget.iterations >= budget.iterations_max:
        return StopDecision(continue_expansion=False, reason=StopReason.ITERATION_CAP.value)

    # 4. advisor-escalation-needed
    if budget.cells_confab_flagged >= policy.confab_escalation_threshold:
        return StopDecision(continue_expansion=False, reason=StopReason.ADVISOR_ESCALATION_NEEDED.value)

    # 5. density-met (depth, not breadth — a grid full of honest STUBs never
    # trips this on its own; frozen_rules defaults to None -> fail-closed)
    #
    # Two conditions, not one. The floor bounds how DEEP the cells you filled
    # must be; on its own it also read as permission to stop with cells never
    # touched at all (8 HIGH + 4 SKELETON clears a 0.60 floor). grid_emit_guard
    # refuses precisely that grid, and a re-run lands on the same floor — so
    # the engine could not walk itself out, and the author's remaining exits
    # were attesting cells that are not thin or raising the density_tier as a lever.
    # cell_is_resolved is the shared predicate the gate uses; keep them
    # matched. This never creates an unbounded loop: iteration-cap (3),
    # no-progress (6) and queue-empty (7) still bound it, and the caps above
    # this line outrank an unresolved cell.
    coverage = compute_coverage_ratio(grid)
    unresolved = [c for c in grid.cells
                  if not cell_is_resolved(c.resolution, c.attestation)]
    if coverage >= policy.coverage_floor and not unresolved:
        return StopDecision(continue_expansion=False, reason=StopReason.DENSITY_MET.value)

    # 6. no-progress (needs both prior samples defined AND stalled AND flat)
    processed = cells_processed(grid)
    if (
        options.prev_cells_processed is not None
        and options.prev_cells_processed_before is not None
        and options.prev_cells_processed == options.prev_cells_processed_before
        and processed == options.prev_cells_processed
    ):
        return StopDecision(continue_expansion=False, reason=StopReason.NO_PROGRESS.value)

    # 7. queue-empty
    if len(queue) == 0:
        return StopDecision(continue_expansion=False, reason=StopReason.QUEUE_EMPTY.value)

    return StopDecision(continue_expansion=True, next_cell=queue[0])
