"""Grid skeleton — the first, 0-token stage of the grid engine: turn a set of
axes + a density_tier + a strength into a covering-array (CA) cell grid. Pure and
deterministic (no LLM call anywhere in this module); the expander (a later
phase) is what turns a SKELETON cell into LOW/HIGH/STUB/MISSING content.

DensityTier and strength are two PARALLEL, independent axes answering two
different questions ("how deep to fill" vs "how wide to cover"): ``density_tier``
still feeds ``density_policy(density_tier).budget`` unchanged; ``strength`` (int t,
default ``DEFAULT_STRENGTH_T``) is new and drives ``ca.greedy_ca(shape,
t)``. The two never interact and must never be merged into one knob — each
has its own SSOT (``grid-density-tier.yaml`` vs ``grid-strength.yaml``).

Two things this module deliberately does NOT do, both to keep the phase
dependency graph acyclic:
  - it does not import ``axes.py`` — axes are passed in as data, never built
    here, so a caller (test or a future planner-facing entrypoint) owns axis
    construction;
  - it does not hardcode a budget-by-density_tier table — ``density_policy(density_tier)`` is
    the single source for ``depth_tokens_max``/``iterations_max``, so a density_tier's
    budget only ever needs updating in the YAML SSOT.

``build_grid_skeleton`` stamps the resolved `t` onto ``Grid.strength`` as an
AUDIT record — auditable/reproducible evidence of what strength a grid
was built at. That stamp is audit-only, NOT an escalation input: the
escalate glue below (``cells_to_rows``/``extend_grid_skeleton``) — the
counterpart to a build-time strength, climbing an already-built grid to t+1
without losing filled work — still re-derives the CURRENT t from the cells
themselves via ``ca.infer_max_t`` and never trusts the stored
``Grid.strength`` field for climbing. Both invert/extend through ``ca.py``
only.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple, Union

from . import ca
from .density import density_policy
from .types import (
    BudgetLedger,
    CellResolution,
    Grid,
    GridAttestation,
    GridAxis,
    GridDensityTier,
    GridCell,
    GridDensity,
)

# Agents whose grid identifies a plan (vs. an executor grid, which identifies
# a task). "frankode-planner" is the FrankCode-ported alias for "planner".
_AGENTS_REQUIRING_PLAN_ID = frozenset({"frankode-planner", "planner", "qa"})

# Lowest strength ship tier (t2 — every PAIR of axis values covered at least
# once). An int CA strength, never a coverage-floor ratio, so this can never
# collide with the coverage_floor SSOT's float-literal guard.
DEFAULT_STRENGTH_T = 2


def _coerce_density_tier(density_tier: Union[GridDensityTier, str]) -> GridDensityTier:
    return density_tier if isinstance(density_tier, GridDensityTier) else GridDensityTier(density_tier)


def build_grid_skeleton(grid_input: Dict[str, Any]) -> Grid:
    """Validate agent/id pairing, build a covering array over the axes at
    strength `t`, and seed the budget ledger + attestation. ``grid_input``
    keys: ``agent``, ``axes``, ``density_tier`` (required); ``plan_id``, ``task_id``,
    ``strength`` (int t, default ``DEFAULT_STRENGTH_T``), ``now`` (ISO
    string; injected so the grid's ``created_at`` is deterministic in
    tests)."""
    agent = grid_input["agent"]
    plan_id = grid_input.get("plan_id")
    task_id = grid_input.get("task_id")

    if agent in _AGENTS_REQUIRING_PLAN_ID and not plan_id:
        raise ValueError(f"build_grid_skeleton: agent '{agent}' requires plan_id")
    if agent == "executor" and not task_id:
        raise ValueError("build_grid_skeleton: agent 'executor' requires task_id")

    axes = grid_input.get("axes") or []
    if not axes:
        raise ValueError("build_grid_skeleton: axes must not be empty")

    density_tier = _coerce_density_tier(grid_input["density_tier"])
    t = int(grid_input.get("strength", DEFAULT_STRENGTH_T))
    if t < DEFAULT_STRENGTH_T:
        raise ValueError(
            "build_grid_skeleton: strength %d is below the floor (t%d) — "
            "the coverage-grid schema requires strength >= %d and the ship "
            "ladder starts at t%d" % (t, DEFAULT_STRENGTH_T, DEFAULT_STRENGTH_T, DEFAULT_STRENGTH_T)
        )

    shape = [len(a.values) for a in axes]
    if len(axes) < t:
        # Reached by dropping every optional axis. Previously this fell
        # through to ca.greedy_ca and surfaced its internal bound
        # ("t must satisfy 1 <= t <= 1"), which reads as an engine fault
        # rather than a grid that cannot exist.
        #
        # Refused, not quietly built at a lower t: with fewer axes than t
        # there are no t-tuples to leave uncovered, so the artifact would be
        # a list wearing the grid schema (and a stamped strength below the
        # documented floor). The message deliberately steers away from
        # padding an axis to satisfy the tool — that is how a grid ends up
        # mostly N/A.
        raise ValueError(
            "build_grid_skeleton: strength t%d needs at least %d axes, got %d "
            "(%s). A grid at this strength exposes uncovered %d-tuples; with "
            "%d axis/axes there are none, so a grid adds nothing here — plan "
            "it as a plain list instead. Do NOT pad a filler axis to reach the "
            "count: a padded axis is what turns a grid into an N/A wall."
            % (t, t, len(axes), ", ".join(a.id for a in axes), t, len(axes)))
    rows = ca.greedy_ca(shape, t)
    cells = [
        GridCell(
            coordinates={a.id: a.values[row[i]] for i, a in enumerate(axes)},
            resolution=CellResolution.SKELETON,
        )
        for row in rows
    ]

    budget_cfg = density_policy(density_tier).budget
    budget = BudgetLedger(
        skeleton_tokens=0,
        depth_tokens_used=0,
        depth_tokens_max=budget_cfg["depth_tokens_max"],
        cells_expanded=0,
        cells_stubbed=0,
        cells_missing=0,
        cells_confab_flagged=0,
        iterations=0,
        iterations_max=budget_cfg["iterations_max"],
    )
    attestation = GridAttestation(
        density=GridDensity.SKELETON,
        total_cells=len(cells),
        coverage_ratio=0.0,
        stub_ratio=0.0,
        missing_ratio=0.0,
    )
    created_at = grid_input.get("now") or datetime.now(timezone.utc).isoformat()

    return Grid(
        agent=agent,
        axes=axes,
        cells=cells,
        budget=budget,
        attestation=attestation,
        density_tier=density_tier,
        created_at=created_at,
        strength=t,
        plan_id=plan_id,
        task_id=task_id,
    )


def cells_to_rows(grid: Grid) -> List[Tuple[int, ...]]:
    """Invert ``build_grid_skeleton``: map every ``GridCell.coordinates``
    back to the value-index row that produced it (``axis.values.index(...)``
    per axis), so ``ca.seeded_extend``/``ca.infer_max_t`` can work from a
    grid that carries no stored strength field. Requires unique axis values
    (``axes.build_planner_axes``/``build_executor_axes`` enforce this at
    construction) — a duplicate value would make ``.index()`` non-injective
    and silently corrupt the inferred row."""
    axes = grid.axes
    return [
        tuple(a.values.index(cell.coordinates[a.id]) for a in axes)
        for cell in grid.cells
    ]


def extend_grid_skeleton(grid: Grid, t_new: int) -> Grid:
    """Escalate a built grid's strength to `t_new` (typically current t + 1)
    via ``ca.seeded_extend``. Every existing ``GridCell`` is kept VERBATIM —
    the same object, so content/attestation/evidence/resolution stay
    byte-identical in the returned grid; only the delta rows
    ``seeded_extend`` newly adds become fresh SKELETON cells. The caller
    (``grid_engine._cmd_expand``) owns extending the budget ledger and
    re-running the fill loop over the delta."""
    axes = grid.axes
    shape = [len(a.values) for a in axes]
    existing_rows = cells_to_rows(grid)
    all_rows = ca.seeded_extend(existing_rows, shape, t_new)

    cells = list(grid.cells)
    for row in all_rows[len(existing_rows):]:
        cells.append(
            GridCell(
                coordinates={a.id: a.values[row[i]] for i, a in enumerate(axes)},
                resolution=CellResolution.SKELETON,
            )
        )

    return Grid(
        agent=grid.agent,
        axes=axes,
        cells=cells,
        budget=grid.budget,
        attestation=grid.attestation,
        density_tier=grid.density_tier,
        created_at=grid.created_at,
        strength=t_new,
        schema_version=grid.schema_version,
        plan_id=grid.plan_id,
        task_id=grid.task_id,
    )
