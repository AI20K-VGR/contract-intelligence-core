"""Grid data model — the shared shape every grid module builds on (schema grid/v2).

A Grid is a structured artifact produced by the grid-planning primitive for the
planner (macro), QA (review), or executor (micro). It enforces breadth-before-depth:
every axis intersection is enumerated as a cell at SKELETON resolution before any
depth expansion, so missing coverage is structurally visible rather than silently
absent. STUB/MISSING/N/A resolutions require attestation, HIGH requires evidence —
both anti-confabulation contracts enforced by downstream invariant/confab modules
that import the constants defined here.

This is the tầng-1 independent copy — never import from ``orchestrator/``.
"""

import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class CellResolution(Enum):
    """Cell fill states. "N/A" is not a valid Python identifier, so it is carried
    as an enum value-string (``CellResolution.NA.value == "N/A"``), never as an
    attribute literally named N/A."""

    SKELETON = "SKELETON"
    LOW = "LOW"
    HIGH = "HIGH"
    STUB = "STUB"
    MISSING = "MISSING"
    NA = "N/A"


class GridDensity(Enum):
    SKELETON = "SKELETON"
    FILLED = "FILLED"
    DEEP = "DEEP"


class GridDensityTier(Enum):
    LOW = "LOW"
    MID = "MID"
    HIGH = "HIGH"


# Stable, ordered contract — downstream consumers iterate this tuple expecting
# this exact order (skeleton -> filled resolutions -> honest-gap resolutions).
CELL_RESOLUTIONS = (
    CellResolution.SKELETON,
    CellResolution.LOW,
    CellResolution.HIGH,
    CellResolution.STUB,
    CellResolution.MISSING,
    CellResolution.NA,
)

RESOLUTIONS_REQUIRING_ATTESTATION = frozenset(
    {CellResolution.STUB, CellResolution.MISSING, CellResolution.NA}
)

RESOLUTIONS_REQUIRING_EVIDENCE = frozenset({CellResolution.HIGH})

# The exact attestation the graceful-degradation path writes when no LLM
# invoker is wired. It lives HERE, not in expander.py, because it is not an
# expander detail: it is the fingerprint of "this cell was never actually
# processed", and both the expansion loop's stop referee and the emit gate
# have to recognise it. expander.py imports it into _STUB_ATTESTATIONS.
NEVER_FILLED_ATTESTATION = (
    "no LLM invoker wired — returning SKELETON→STUB fallback per "
    "graceful-degradation contract"
)


def cell_is_resolved(resolution, attestation=None) -> bool:
    """ONE definition of "this cell was actually processed" — shared by the
    expansion loop's stop referee (``stopping.should_continue``) and the emit
    gate (``grid_emit_guard``). Accepts a ``CellResolution`` or its wire
    string, since the loop holds enums and the gate holds parsed JSON.

    The two sides drifted apart once, and the failure was not cosmetic: the
    loop stopped at the density_tier's coverage floor with cells still SKELETON (two
    thirds of the cells filled clears the lowest density_tier's floor), while the gate
    refused exactly that grid. Re-running hit the same floor and stopped, so
    nothing the engine offers escaped it — the only exits left were attesting
    cells that are not thin, or raising the density_tier as a lever. Both write a
    false statement into the artifact. Keep this the only definition.

    Unresolved is a deliberately NARROW set: SKELETON (built, never expanded)
    and the no-invoker degradation STUB, whose attestation matches
    ``NEVER_FILLED_ATTESTATION`` exactly. A STUB carrying any other reason
    ([JUSTIFIED-THIN], a human note) is processed work that is honestly thin,
    and MISSING/N/A are honest gaps — none of those may hold the loop open, or
    every legitimately thin grid would spin to its iteration cap.

    Orthogonal to depth: ``compute_coverage_ratio`` asks how deep the filled
    cells are; this asks whether a cell was touched at all.
    """
    res = getattr(resolution, "value", resolution)
    if res == CellResolution.SKELETON.value:
        return False
    if res == CellResolution.STUB.value and attestation == NEVER_FILLED_ATTESTATION:
        return False
    return True

GRID_SCHEMA_VERSION = "grid/v2"

# Evidence entries must anchor to a concrete project artifact — the anti-confab
# anchor shared by invariants.py (PHANTOM_EVIDENCE), confab.py, and expander.py.
# Defined ONCE here; every other module imports this constant, it never
# re-hardcodes a copy (a per-module copy is exactly how the pattern drifts).
#
# Default is the harness-flavored UNION set, in three groups:
#   FrankCode-original — src/, tests/, PLAN-, TASK-, RFC-, metric:, axis:
#   tầng-1 harness paths/IDs — harness/, plans/, docs/, DEC-, artifacts/, BL-,
#     VL-, PRD-, BRD-, EPIC-, STORY-, commit:  (real artifacts this harness
#     mints — grid/verification/review-decision JSONs, backlog & validation-log
#     IDs, the product-tier spec IDs, and SHA citations)
#   common cross-project — adr/, ADR-, config/, http(s)://  (near-universal
#     evidence anchors an operator reaches for)
# Shipping the FrankCode-only default would fail every real harness citation,
# driving PHANTOM_EVIDENCE on every grid and gutting the invariant's signal.
# Deliberately EXCLUDED (too broad — would gut the signal): test:, log:,
# bench:, spec/.
#
# `src/` is here as A source dir, not THE source dir. A project that packages
# under another name (taskman/, app/, pkg/) has no shipped prefix covering its
# own code, so every citation to real source flags PHANTOM_EVIDENCE and the
# author is pushed toward citing prose instead — the inverse of the point.
# Extend per-project via EVIDENCE_PREFIX_ENV (below); read the EFFECTIVE
# pattern through evidence_pattern(), never this constant, in any code that
# judges an author's evidence.
EVIDENCE_PREFIX_PATTERN = re.compile(
    r"^(harness/|plans/|docs/|src/|tests/|artifacts/|config/|adr/|"
    r"PLAN-|TASK-|RFC-|DEC-|BL-|VL-|PRD-|BRD-|EPIC-|STORY-|ADR-|"
    r"metric:|axis:|commit:|https?://)"
)

# Per-project extension seam. Config that varies per project rides an explicit
# HARNESS_* env (harness/data/ is bin-global and shared under a global install,
# so a data-file override would leak one project's dirs into every other).
# Value: comma-separated literal prefixes, e.g. "taskman/,internal/".
EVIDENCE_PREFIX_ENV = "HARNESS_GRID_EVIDENCE_PREFIXES"


def _parse_extra_prefixes(raw):
    """Literal prefixes from the env value — blank entries dropped. Each is
    re.escape()d at compile time: an operator writes a PATH, not a regex, so
    `a.b/` must not silently match `axb/` (and a stray paren must not raise)."""
    return [s.strip() for s in (raw or "").split(",") if s.strip()]


def configured_extra_prefixes():
    """The per-project prefix extension currently in effect, as a list.

    Exposed so the artifact writer can RECORD the judging context: without it,
    the same grid file passes PHANTOM_EVIDENCE on the machine that emitted it
    and fails anywhere the env is not exported, with nothing in the artifact
    to explain the difference. Recording it is transparency only — judging
    code must keep calling ``evidence_pattern()``, which reads the live
    environment, never a value carried inside the artifact being judged.
    """
    return _parse_extra_prefixes(os.environ.get(EVIDENCE_PREFIX_ENV))


def evidence_pattern(extra=None):
    """The EFFECTIVE evidence anchor pattern: the shipped union above, plus any
    per-project prefixes. This is what every validator must call — matching the
    bare constant is what made the "overridable" claim false for three
    consumers at once.

    Not cached: the env is a test seam as well as an operator seam, and the
    compile is microseconds against a per-cell string match."""
    prefixes = _parse_extra_prefixes(
        os.environ.get(EVIDENCE_PREFIX_ENV) if extra is None else extra)
    if not prefixes:
        return EVIDENCE_PREFIX_PATTERN
    alts = "|".join(re.escape(p) for p in prefixes)
    return re.compile("%s|^(%s)" % (EVIDENCE_PREFIX_PATTERN.pattern, alts))


@dataclass
class GridAxis:
    id: str
    label: str
    values: List[str]
    ordered_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "id": self.id,
            "label": self.label,
            "values": list(self.values),
        }
        if self.ordered_by is not None:
            out["ordered_by"] = self.ordered_by
        return out

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GridAxis":
        return cls(
            id=data["id"],
            label=data["label"],
            values=list(data["values"]),
            ordered_by=data.get("ordered_by"),
        )


@dataclass
class GridCell:
    coordinates: Dict[str, str]
    resolution: CellResolution
    content: Optional[str] = None
    attestation: Optional[str] = None
    evidence: Optional[List[str]] = None
    tokens_spent: Optional[int] = None
    budget_exceeded: Optional[bool] = None
    iteration_expanded: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "coordinates": dict(self.coordinates),
            "resolution": self.resolution.value,
        }
        if self.content is not None:
            out["content"] = self.content
        if self.attestation is not None:
            out["attestation"] = self.attestation
        if self.evidence is not None:
            out["evidence"] = list(self.evidence)
        if self.tokens_spent is not None:
            out["tokens_spent"] = self.tokens_spent
        if self.budget_exceeded is not None:
            out["budget_exceeded"] = self.budget_exceeded
        if self.iteration_expanded is not None:
            out["iteration_expanded"] = self.iteration_expanded
        return out

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GridCell":
        return cls(
            coordinates=dict(data["coordinates"]),
            resolution=CellResolution(data["resolution"]),
            content=data.get("content"),
            attestation=data.get("attestation"),
            evidence=list(data["evidence"]) if "evidence" in data else None,
            tokens_spent=data.get("tokens_spent"),
            budget_exceeded=data.get("budget_exceeded"),
            iteration_expanded=data.get("iteration_expanded"),
        )


@dataclass
class BudgetLedger:
    """``depth_tokens_used``/``depth_tokens_max`` carry a figure the MODEL
    self-reports — tầng-1 never measures token spend itself. ``stopping.py``
    does compare the two (``token-budget-exhausted``), so they are no longer
    telemetry-only, but that check is COOPERATIVE: an invoker reporting
    nothing accumulates zero and never trips it. ``iterations``/
    ``iterations_max`` are the opposite case — a quantity the harness counts
    itself — and remain the enforced bound (``stopping.py``'s
    ``iteration-cap``, ``invariants.py``'s ``ITERATION_HONEST``)."""

    skeleton_tokens: int
    depth_tokens_used: int
    depth_tokens_max: int
    cells_expanded: int
    cells_stubbed: int
    cells_missing: int
    cells_confab_flagged: int
    iterations: int
    iterations_max: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skeleton_tokens": self.skeleton_tokens,
            "depth_tokens_used": self.depth_tokens_used,
            "depth_tokens_max": self.depth_tokens_max,
            "cells_expanded": self.cells_expanded,
            "cells_stubbed": self.cells_stubbed,
            "cells_missing": self.cells_missing,
            "cells_confab_flagged": self.cells_confab_flagged,
            "iterations": self.iterations,
            "iterations_max": self.iterations_max,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BudgetLedger":
        return cls(
            skeleton_tokens=data["skeleton_tokens"],
            depth_tokens_used=data["depth_tokens_used"],
            depth_tokens_max=data["depth_tokens_max"],
            cells_expanded=data["cells_expanded"],
            cells_stubbed=data["cells_stubbed"],
            cells_missing=data["cells_missing"],
            cells_confab_flagged=data["cells_confab_flagged"],
            iterations=data["iterations"],
            iterations_max=data["iterations_max"],
        )


@dataclass
class GridAttestation:
    density: GridDensity
    total_cells: int
    coverage_ratio: float
    stub_ratio: float
    missing_ratio: float
    # na_ratio (na-option3 companion): share of ALL N/A cells (free-text
    # + rule:-pointing, credited or not) over total_cells — the SAME population
    # invariants.py::_check_na_ratio_advisory bells on, so this field never
    # desyncs from the anti-gaming advisory. Always written (never omitted),
    # unlike the omit-when-None Grid.strength below — a float default of 0.0
    # is itself a meaningful "no N/A cells" reading, not an absence marker.
    na_ratio: float = 0.0
    confab_signals: List[str] = field(default_factory=list)
    invariants_passed: List[str] = field(default_factory=list)
    invariants_failed: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "density": self.density.value,
            "total_cells": self.total_cells,
            "coverage_ratio": self.coverage_ratio,
            "stub_ratio": self.stub_ratio,
            "missing_ratio": self.missing_ratio,
            "na_ratio": self.na_ratio,
            "confab_signals": list(self.confab_signals),
            "invariants_passed": list(self.invariants_passed),
            "invariants_failed": list(self.invariants_failed),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GridAttestation":
        return cls(
            density=GridDensity(data["density"]),
            total_cells=data["total_cells"],
            coverage_ratio=data["coverage_ratio"],
            stub_ratio=data["stub_ratio"],
            missing_ratio=data["missing_ratio"],
            na_ratio=data.get("na_ratio", 0.0),
            confab_signals=list(data.get("confab_signals", [])),
            invariants_passed=list(data.get("invariants_passed", [])),
            invariants_failed=list(data.get("invariants_failed", [])),
        )


@dataclass
class Grid:
    """Field order follows gridTypes.ts:81-92 except ``plan_id``/``task_id`` are
    moved to the end: Python dataclasses (3.9, no ``kw_only``) require every
    field after the first one carrying a default to also carry a default, and
    the two TS optional fields sit ahead of several required ones. Moving them
    after ``schema_version`` keeps every field's own optionality unchanged."""

    agent: str
    axes: List[GridAxis]
    cells: List[GridCell]
    budget: BudgetLedger
    attestation: GridAttestation
    density_tier: GridDensityTier
    created_at: str
    # strength: the CA strength `t` the skeleton was built at
    # (parallel to `density_tier`, which is depth — strength is breadth). Optional and
    # omit-when-None like plan_id/task_id below: an older record predating
    # this field, or a grid never run through build_grid_skeleton's stamp,
    # has no meaningful t to report.
    strength: Optional[int] = None
    schema_version: str = GRID_SCHEMA_VERSION
    plan_id: Optional[str] = None
    task_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "agent": self.agent,
            "axes": [axis.to_dict() for axis in self.axes],
            "cells": [cell.to_dict() for cell in self.cells],
            "budget": self.budget.to_dict(),
            "attestation": self.attestation.to_dict(),
            "density_tier": self.density_tier.value,
            "created_at": self.created_at,
            "schema_version": self.schema_version,
        }
        if self.strength is not None:
            out["strength"] = self.strength
        if self.plan_id is not None:
            out["plan_id"] = self.plan_id
        if self.task_id is not None:
            out["task_id"] = self.task_id
        return out

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Grid":
        return cls(
            agent=data["agent"],
            axes=[GridAxis.from_dict(a) for a in data["axes"]],
            cells=[GridCell.from_dict(c) for c in data["cells"]],
            budget=BudgetLedger.from_dict(data["budget"]),
            attestation=GridAttestation.from_dict(data["attestation"]),
            density_tier=GridDensityTier(data["density_tier"]),
            created_at=data["created_at"],
            strength=data.get("strength"),
            schema_version=data.get("schema_version", GRID_SCHEMA_VERSION),
            plan_id=data.get("plan_id"),
            task_id=data.get("task_id"),
        )
