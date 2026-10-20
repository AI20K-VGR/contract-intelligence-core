"""Deterministic page/unit planning for long-document processing.

The demo still executes in one process, but the unit shape is deliberately
serializable so a PostgreSQL worker can checkpoint and resume it later.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum

from app.tools.store import DossierRecord


class UnitStage(str, Enum):
    STRUCTURE = "STRUCTURE"
    EXTRACT = "EXTRACT"
    COMPARE = "COMPARE"


class UnitState(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INTERRUPTED = "INTERRUPTED"


@dataclass(frozen=True)
class ProcessingUnit:
    unit_id: str
    stage: UnitStage
    page_numbers: tuple[int, ...]
    node_ids: tuple[str, ...] = ()
    table_ids: tuple[str, ...] = ()
    input_digest: str = ""


@dataclass
class UnitCheckpoint:
    unit_id: str
    state: UnitState = UnitState.PENDING
    attempt: int = 0
    generation: int = 0
    error_code: str | None = None
    artifact_digest: str | None = None


def plan_units(record: DossierRecord, *, pages_per_unit: int = 2) -> list[ProcessingUnit]:
    """Partition a dossier into bounded, complete page windows.

    Every page is represented, including blank/failed pages. Nodes and tables
    are attached by page overlap; no text is concatenated here.
    """

    if pages_per_unit < 1:
        raise ValueError("pages_per_unit must be >= 1")
    pages = sorted({page.page_number for page in record.pages})
    if not pages:
        return []
    units: list[ProcessingUnit] = []
    for start in range(0, len(pages), pages_per_unit):
        window = tuple(pages[start : start + pages_per_unit])
        page_set = set(window)
        node_ids = tuple(
            node.node_id
            for node in sorted(record.evidence_nodes(), key=lambda item: (item.order, item.node_id))
            if page_set.intersection(node.page_range)
        )
        page_revisions = {
            page.page_revision_id
            for page in record.pages
            if page.page_number in page_set
        }
        table_ids = tuple(
            table.table_id
            for table in record.tables
            if (
                table.page_revision_id in page_revisions
                or table.node_id in node_ids
                or table.table_id in node_ids
            )
        )
        raw = f"{record.dossier_id}|{window}|{node_ids}|{table_ids}|{record.pins.source_snapshot_digest}"
        unit_id = f"unit:{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"
        units.append(
            ProcessingUnit(
                unit_id=unit_id,
                stage=UnitStage.EXTRACT,
                page_numbers=window,
                node_ids=node_ids,
                table_ids=table_ids,
                input_digest=record.pins.source_snapshot_digest,
            )
        )
    return units


def checkpoint_for(unit: ProcessingUnit, *, generation: int = 0) -> UnitCheckpoint:
    """Create an idempotent checkpoint envelope for a planned unit."""

    return UnitCheckpoint(unit_id=unit.unit_id, generation=generation)
