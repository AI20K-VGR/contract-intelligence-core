"""Grid-planning primitive (tầng-1, schema grid/v2) — the independent harness copy.

Never import from ``orchestrator/`` — this package is a deliberately separate
implementation, not a re-export shim over the tầng-2 grid engine.
"""
import sys as _sys
from pathlib import Path as _Path

# axes.py/preregister.py/density.py import the shared yaml_io (harness/scripts/)
# at module top-level. This package is reachable via the "repo root route"
# (`import harness.scripts.grid.axes` with only the repo root on sys.path,
# never harness/scripts itself — see test_grid_import_surface.py), so a sibling
# `import yaml_io` in those files cannot resolve on its own. This __init__.py
# always runs before any of its submodules (Python initializes a parent package
# before importing a submodule of it), so the bootstrap belongs here once
# rather than copied into each of the three files.
_HARNESS_SCRIPTS = str(_Path(__file__).resolve().parent.parent)
if _HARNESS_SCRIPTS not in _sys.path:
    _sys.path.append(_HARNESS_SCRIPTS)

from .types import (
    GRID_SCHEMA_VERSION,
    CELL_RESOLUTIONS,
    EVIDENCE_PREFIX_PATTERN,
    RESOLUTIONS_REQUIRING_ATTESTATION,
    RESOLUTIONS_REQUIRING_EVIDENCE,
    BudgetLedger,
    CellResolution,
    Grid,
    GridAttestation,
    GridAxis,
    GridDensityTier,
    GridCell,
    GridDensity,
)

__all__ = [
    "GRID_SCHEMA_VERSION",
    "CELL_RESOLUTIONS",
    "EVIDENCE_PREFIX_PATTERN",
    "RESOLUTIONS_REQUIRING_ATTESTATION",
    "RESOLUTIONS_REQUIRING_EVIDENCE",
    "BudgetLedger",
    "CellResolution",
    "Grid",
    "GridAttestation",
    "GridAxis",
    "GridDensityTier",
    "GridCell",
    "GridDensity",
]
