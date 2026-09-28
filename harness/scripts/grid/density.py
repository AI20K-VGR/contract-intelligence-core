"""DensityTier -> DensityConfig dispatch (grid/v2). Pure lookup over the frozen SSOT
in ``harness/data/grid-density-tier.yaml`` — the single source every other
grid module (invariants, expander, stopping, review) reads for the coverage
floor, evidence policy, budget, and per-cell token cap.

Fail-closed by design: an unknown density_tier raises rather than falling back to a
default floor, which would silently under-cover a case nobody classified. The
table is cached once (read off ``__file__``, never CWD); every lookup returns
a defensive copy so a caller mutating a row can't corrupt the shared table.

This module deliberately does NOT import ``skeleton`` — in the FrankCode TS
source ``densityPolicy.ts`` imports its budget defaults from
``gridSkeleton.ts``; here that import is inverted so the budget lives in the
YAML instead and ``skeleton.py`` (a later phase) reads it back out through
``density_policy(density_tier).budget``. Keeps this module's only dependency on the
axis types module.
"""
import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Union

import yaml_io

from .types import CellResolution, GridDensityTier, GridDensity

_DATA = Path(__file__).resolve().parent.parent.parent / "data" / "grid-density-tier.yaml"

_TABLE = None


class UnknownDensityTierError(Exception):
    """density_tier absent from the frozen SSOT — fail closed, never a default floor."""


@dataclass
class DensityConfig:
    density_tier: GridDensityTier
    density: GridDensity
    coverage_floor: float
    evidence_required: str
    budget: Dict[str, int]
    per_cell_token_cap: int
    meta_critique_enabled: bool
    # Two distinct confab axes (FrankCode collapsed both into one field):
    #   confab_signal_threshold     — signals on ONE cell before it is flagged
    #                                 (loop/review: cells_exceeding_signal_threshold)
    #   confab_escalation_threshold — flagged CELLS before advisor escalation
    #                                 (stopping: advisor-escalation-needed)
    # Shipped defaults are equal, so the split is behaviour-preserving.
    confab_signal_threshold: int
    confab_escalation_threshold: int


def _load_table(path=None):
    """Return the {density_tier_name: row} map. Cached when reading the default SSOT;
    a custom path (tests) bypasses the cache so fixtures don't poison the
    shared table."""
    global _TABLE
    if path is None and _TABLE is not None:
        return _TABLE
    src = Path(path) if path else _DATA
    doc = yaml_io.safe_load(src.read_text(encoding="utf-8")) or {}
    table = doc.get("density_tiers") or {}
    if path is None:
        _TABLE = table
    return table


def density_policy(density_tier: Union[GridDensityTier, str], path=None) -> DensityConfig:
    """Look up the frozen density policy for a density_tier. Raises ``UnknownDensityTierError``
    for anything not in the SSOT — never returns a default row."""
    density_tier_enum = density_tier if isinstance(density_tier, GridDensityTier) else _coerce_density_tier(density_tier)
    table = _load_table(path)
    key = density_tier_enum.value if density_tier_enum is not None else str(density_tier)
    if density_tier_enum is None or key not in table:
        raise UnknownDensityTierError(density_tier)
    row = table[key]
    return DensityConfig(
        density_tier=density_tier_enum,
        density=GridDensity(row["density"]),
        coverage_floor=float(row["coverage_floor"]),
        evidence_required=row["evidence_required"],
        budget=copy.deepcopy(
            {
                "depth_tokens_max": row["depth_tokens_max"],
                "iterations_max": row["iterations_max"],
            }
        ),
        per_cell_token_cap=row["per_cell_token_cap"],
        meta_critique_enabled=bool(row["meta_critique"]),
        confab_signal_threshold=row["confab_signal_threshold"],
        confab_escalation_threshold=row["confab_escalation_threshold"],
    )


def _coerce_density_tier(density_tier):
    try:
        return GridDensityTier(density_tier)
    except ValueError:
        return None


def evidence_required_for_resolution(density_tier: Union[GridDensityTier, str], resolution: CellResolution) -> bool:
    """True if a non-SKELETON cell must carry evidence under the given density_tier's
    policy. STUB/MISSING/N/A are exempt; their honesty anchor is the
    attestation string, not evidence."""
    config = density_policy(density_tier)
    if config.evidence_required == "no":
        return False
    if config.evidence_required == "always":
        return resolution in (CellResolution.HIGH, CellResolution.LOW)
    # on-high-only
    return resolution == CellResolution.HIGH
