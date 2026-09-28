"""Grid-expansion loop orchestrator — the step-wise state machine that
drives a SKELETON grid toward the policy's density floor through many small,
individually-testable expansions:

  1. ``should_continue`` — keep going, or stop (and why)?
  2. ``expand_cell`` the next queued cell (the ONLY non-deterministic seam;
     injected, default None -> every cell degrades to STUB).
  3. Update the budget ledger (tokens, iteration count, per-resolution
     counters, confab-flagged count) and the cell in place.
  4. Recompute attestation ratios (coverage/stub/missing + density
     classification).
  5. Go to 1.

Terminates at a clean cell boundary — never mid-expansion — and returns the
finalized ``Grid`` plus one snapshot per iteration (plus a terminal
snapshot). The caller owns observability via the optional ``on_iteration``
callback.

Port note (TS async -> Python sync): ``gridLoop.ts`` is async/Promise based;
this module has no asyncio anywhere — ``expand_cell`` is already a
plain synchronous callable, so the loop is simpler than the source and
equally deterministic.

Round-1 scope (YAGNI): only the TS ``sequential`` branch (gridLoop.ts:
206-248) is ported. The TS ``parallelCells > 1`` batch-parallel branch
(125-205) is an I/O optimization for concurrent LLM calls — irrelevant to a
deterministic, injectable-seam engine — and is deliberately left unported.

``qa-failed`` is never emitted by this loop with default options: unlike the
TS source (which never actually wires an ``invariantReport`` into the
mid-loop ``shouldContinue`` call either), this loop calls ``should_continue``
with only the previous-processed-counts — the invariant report is computed
solely at ``finalize_grid``, at the very end.
"""
import copy
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .confab import cells_exceeding_signal_threshold, detect_confabulation
from .density import DensityConfig
from .expander import ExpanderInput, LlmInvoker, expand_cell
from .invariants import run_invariants, summarize_invariant_names
from .stopping import (
    ShouldContinueOptions,
    StopReason,
    cells_processed,
    compute_coverage_ratio,
    expansion_breadth_ratio,
    should_continue,
)
from .types import CellResolution, Grid, GridCell, GridDensity

# Density CLASSIFICATION thresholds (attestation.density SKELETON/FILLED/DEEP)
# — distinct from a density_tier's coverage_floor (tầng-1 SSOT: {0.60, 0.85, 0.95}).
# Named constants so neither literal is ever mistaken for (or flagged as) a
# copy of the coverage-floor SSOT.
DENSITY_FILLED_THRESHOLD = 0.5
DENSITY_DEEP_THRESHOLD = 0.9

Prioritizer = Callable[[List[GridCell], Grid], List[GridCell]]


@dataclass
class GridLoopConfig:
    grid: Grid
    policy: DensityConfig
    invoke_llm: Optional[LlmInvoker] = None
    plan_context: Optional[str] = None
    prioritize: Optional[Prioritizer] = None
    on_iteration: Optional[Callable[["LoopSnapshot"], None]] = None
    max_iterations: Optional[int] = None
    # Duck-typed: this module has NO ``from __future__ import
    # annotations``, so annotating this field with the (frozen-ruleset)
    # type from a later phase's module would eval AT IMPORT TIME -> NameError,
    # since that module and type do not exist yet. ``Optional[Any]`` (never
    # importing that later-phase module here) is the house precedent
    # (``stopping.py``'s own ``ShouldContinueOptions.invariant_report``).
    # Default None -> fail-closed (0 N/A credit) until a caller (a later
    # phase's ``--rules`` loader) threads a real frozen ruleset through.
    frozen_rules: Optional[Any] = None
    # NOTE: no parallel_cells — batch-parallel expansion is out of scope
    # round-1 (see module docstring).


@dataclass
class LoopSnapshot:
    iteration: int
    cells_expanded: int
    cells_stubbed: int
    cells_missing: int
    cells_confab_flagged: int
    coverage: float
    tokens_used: int
    tokens_max: int
    cell_coordinates: Optional[Dict[str, str]] = None
    last_stop_reason: Optional[str] = None


@dataclass
class LoopResult:
    grid: Grid
    stop_reason: str
    iterations: List[LoopSnapshot] = field(default_factory=list)


def clone_grid(grid: Grid) -> Grid:
    """Deep-copy independent of the input grid — the loop must never mutate
    the caller's grid (gridLoop.ts:252-269). Every field on ``Grid`` and its
    nested dataclasses is plain data (no callables), so a full deep copy is
    safe and simpler than a manual field-by-field clone."""
    return copy.deepcopy(grid)


def natural_prioritize(cells: List[GridCell], grid: Grid) -> List[GridCell]:
    """Default prioritizer — natural (skeleton-enumeration) order, unchanged."""
    return list(cells)


def find_cell(grid: Grid, coordinates: Dict[str, str]) -> Optional[GridCell]:
    for cell in grid.cells:
        if _same_coords(cell.coordinates, coordinates):
            return cell
    return None


def patch_cell_in_place(grid: Grid, original: GridCell, updated: GridCell) -> None:
    """Replace ``original`` with ``updated`` in ``grid.cells``, keeping the
    ORIGINAL coordinates (an expander response never carries its own
    coordinates back)."""
    for idx, cell in enumerate(grid.cells):
        if _same_coords(cell.coordinates, original.coordinates):
            grid.cells[idx] = GridCell(
                coordinates=dict(original.coordinates),
                resolution=updated.resolution,
                content=updated.content,
                attestation=updated.attestation,
                evidence=list(updated.evidence) if updated.evidence is not None else None,
                tokens_spent=updated.tokens_spent,
                budget_exceeded=updated.budget_exceeded,
                iteration_expanded=updated.iteration_expanded,
            )
            return


def _same_coords(a: Dict[str, str], b: Dict[str, str]) -> bool:
    return a == b


def round2(n: float) -> float:
    # Half-UP at the .xx5 boundary to match the TS reference's Math.round
    # (gridLoop.ts:326) — Python's built-in round() is banker's/half-to-even,
    # which drifts the reported attestation ratios from FrankCode on the exact
    # .xx5 ratios that small Cartesian cell counts make common (e.g. 1/8=0.125
    # -> 0.13, not 0.12). Reported-number parity only; gate decisions use the
    # raw un-rounded ratio.
    return math.floor(n * 100 + 0.5) / 100


def classify_density(breadth: float) -> GridDensity:
    """>=DEEP threshold -> DEEP; >=FILLED threshold -> FILLED; else SKELETON.
    Takes BREADTH (``expansion_breadth_ratio``), never depth — 0.5/0.9 are
    breadth thresholds; the input source changed, the thresholds did not."""
    if breadth >= DENSITY_DEEP_THRESHOLD:
        return GridDensity.DEEP
    if breadth >= DENSITY_FILLED_THRESHOLD:
        return GridDensity.FILLED
    return GridDensity.SKELETON


def update_attestation_ratios(grid: Grid, frozen_rules: Optional[Any] = None) -> None:
    """``frozen_rules`` threads to ``compute_coverage_ratio``'s depth numerator
    (default None -> fail-closed, matching every other caller in this module).
    Only ``finalize_grid`` (the TERMINAL path) passes a real ruleset through;
    the per-iteration call inside ``run_grid_loop`` keeps the default None —
    mid-loop density-met stays conservative (R2 [M-OPEN])."""
    total = len(grid.cells) or 1
    stub = sum(1 for c in grid.cells if c.resolution == CellResolution.STUB)
    missing = sum(1 for c in grid.cells if c.resolution == CellResolution.MISSING)
    na = sum(1 for c in grid.cells if c.resolution == CellResolution.NA)
    grid.attestation.total_cells = len(grid.cells)
    grid.attestation.coverage_ratio = round2(compute_coverage_ratio(grid, frozen_rules))  # depth
    grid.attestation.stub_ratio = round2(stub / total)
    grid.attestation.missing_ratio = round2(missing / total)
    # na_ratio counts ALL N/A cells (free-text + rule:-pointing, credited or
    # not) — the same population invariants.py::_check_na_ratio_advisory
    # bells on, so the artifact number and the bell's number never desync.
    grid.attestation.na_ratio = round2(na / total)
    grid.attestation.density = classify_density(expansion_breadth_ratio(grid))  # breadth


def build_snapshot(
    grid: Grid,
    cell_coordinates: Optional[Dict[str, str]],
    last_stop_reason: Optional[str] = None,
) -> LoopSnapshot:
    return LoopSnapshot(
        iteration=grid.budget.iterations,
        cell_coordinates=dict(cell_coordinates) if cell_coordinates else None,
        cells_expanded=grid.budget.cells_expanded,
        cells_stubbed=grid.budget.cells_stubbed,
        cells_missing=grid.budget.cells_missing,
        cells_confab_flagged=grid.budget.cells_confab_flagged,
        coverage=round2(compute_coverage_ratio(grid)),  # depth (matches density-met)
        tokens_used=grid.budget.depth_tokens_used,
        tokens_max=grid.budget.depth_tokens_max,
        last_stop_reason=last_stop_reason,
    )


def finalize_grid(grid: Grid, policy: DensityConfig, frozen_rules: Optional[Any] = None) -> None:
    """Recompute attestation ratios, then run all 8 invariants and stamp
    passed/failed names onto the grid. ``frozen_rules`` threads to
    COVERAGE_FLOOR's depth numerator (default None -> fail-closed); the
    NA_RATIO_ADVISORY threshold resolves from ``policy`` when the policy
    object carries one (skeleton/strength wiring — not yet shipped, so this is
    normally None and ``run_invariants`` falls back to the grid-strength.yaml
    SSOT)."""
    update_attestation_ratios(grid, frozen_rules)
    na_thr = getattr(policy, "na_ratio_advisory", None)
    report = run_invariants(grid, policy, na_ratio_advisory=na_thr, frozen_rules=frozen_rules)
    names = summarize_invariant_names(report)
    grid.attestation.invariants_passed = names["passed"]
    grid.attestation.invariants_failed = names["failed"]


def run_grid_loop(config: GridLoopConfig) -> LoopResult:
    """Run the sequential expansion loop to completion. Deterministic and
    0-token when ``config.invoke_llm`` is None (the default) — every cell
    degrades to an attested STUB and the loop still halts finite."""
    grid = clone_grid(config.grid)
    policy = config.policy
    max_iterations = config.max_iterations if config.max_iterations is not None else grid.budget.iterations_max
    prioritize = config.prioritize or natural_prioritize
    snapshots: List[LoopSnapshot] = []

    queue = prioritize([c for c in grid.cells if c.resolution == CellResolution.SKELETON], grid)
    prev_processed = -1
    prev_processed_before = -1

    while True:
        decision = should_continue(
            grid,
            policy,
            queue,
            ShouldContinueOptions(
                prev_cells_processed=prev_processed,
                prev_cells_processed_before=prev_processed_before,
            ),
        )

        if not decision.continue_expansion:
            snapshots.append(build_snapshot(grid, None, decision.reason))
            finalize_grid(grid, policy, config.frozen_rules)
            return LoopResult(grid=grid, stop_reason=decision.reason, iterations=snapshots)

        if grid.budget.iterations >= max_iterations:
            snapshots.append(build_snapshot(grid, None, StopReason.ITERATION_CAP.value))
            finalize_grid(grid, policy, config.frozen_rules)
            return LoopResult(grid=grid, stop_reason=StopReason.ITERATION_CAP.value, iterations=snapshots)

        target = decision.next_cell
        expansion = expand_cell(
            ExpanderInput(
                grid=grid,
                cell=target,
                policy=policy,
                plan_context=config.plan_context,
                invoke_llm=config.invoke_llm,
            )
        )

        patch_cell_in_place(grid, target, expansion.cell)
        grid.budget.iterations += 1
        grid.budget.depth_tokens_used += (expansion.tokens_spent or 0)

        patched = find_cell(grid, target.coordinates)
        if patched is not None:
            if patched.resolution == CellResolution.STUB:
                grid.budget.cells_stubbed += 1
            elif patched.resolution == CellResolution.MISSING:
                grid.budget.cells_missing += 1
            elif patched.resolution != CellResolution.SKELETON:
                grid.budget.cells_expanded += 1

        confab_findings = detect_confabulation(grid)
        # per-cell signal threshold (how many signals mark ONE cell as flagged),
        # NOT the flagged-cell escalation count read by stopping.py.
        flagged = cells_exceeding_signal_threshold(confab_findings, policy.confab_signal_threshold)
        grid.budget.cells_confab_flagged = len(flagged)
        grid.attestation.confab_signals = list(dict.fromkeys(f.signal for f in confab_findings))

        update_attestation_ratios(grid)
        snapshot = build_snapshot(grid, target.coordinates)
        snapshots.append(snapshot)
        if config.on_iteration is not None:
            config.on_iteration(snapshot)

        prev_processed_before = prev_processed
        prev_processed = cells_processed(grid)
        queue = prioritize([c for c in grid.cells if c.resolution == CellResolution.SKELETON], grid)
