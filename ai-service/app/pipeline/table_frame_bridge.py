"""Bridge typed table projections into grounded semantic frames.

The bridge keeps table rows as evidence.  It never invents an actor, currency,
or legal modality when the source table does not provide one.
"""

from __future__ import annotations

import hashlib
import re
from decimal import Decimal, InvalidOperation
from typing import Iterable

from app.contracts.clause_frames import SLOT_NAMES, ClauseFrame, Evidence, Slot
from app.contracts.models import BoqCheckProjection, PaymentScheduleProjection, TableSnapshot


def payment_schedule_frames(
    projection: PaymentScheduleProjection,
    *,
    table: TableSnapshot,
    profile: str,
    dossier_id: str,
    document_id: str,
    snapshot_id: str,
) -> tuple[ClauseFrame, ...]:
    """Create one frame per payment milestone with row and header evidence."""
    if projection.table_id != table.table_id:
        raise ValueError("payment projection/table identity mismatch")
    if not document_id.strip() or not snapshot_id.strip():
        raise ValueError("table frame identity requires document and snapshot")
    frames: list[ClauseFrame] = []
    scope = _table_scope(table)
    header_text = next((value.strip() for value in table.header if value and value.strip()), "")
    for milestone in projection.milestones:
        raw = (milestone.raw_label or "").strip()
        if not raw:
            raw = next((value for value in milestone.raw_cells if value), None) or milestone.milestone_id
        row_evidence = Evidence(
            document_id, snapshot_id,
            f"{table.table_id}:row:{milestone.milestone_id}", raw,
        )
        evidence = (row_evidence,)
        if header_text:
            evidence = (*evidence, Evidence(
                document_id, snapshot_id,
                f"{table.table_id}:header", header_text,
            ))
        slots = {name: Slot(None, "UNKNOWN", evidence, "not_assessed") for name in sorted(SLOT_NAMES)}
        _ground(slots, "action", "PAY", row_evidence)
        if milestone.percent is not None:
            amount = _decimal(milestone.percent)
            if amount is not None:
                _ground(slots, "amount", amount, row_evidence)
                _ground(slots, "unit", "percent", row_evidence)
        trigger = milestone.trigger or milestone.event
        if trigger:
            _ground(slots, "temporal_trigger", trigger, row_evidence)
        if milestone.deadline:
            value, unit = _deadline(milestone.deadline)
            if value is not None:
                _ground(slots, "deadline", value, row_evidence)
            if unit is not None:
                _ground(slots, "deadline_unit", unit, row_evidence)
        if milestone.condition:
            _ground(slots, "condition", milestone.condition, row_evidence)
        if milestone.base:
            _ground(slots, "base", milestone.base, row_evidence)
        if scope:
            _ground(slots, "object_scope", scope, evidence[-1])
        identity = f"{dossier_id}|{document_id}|{snapshot_id}|{table.table_id}|{milestone.milestone_id}"
        frame_id = hashlib.sha256(identity.encode()).hexdigest()[:24]
        frames.append(ClauseFrame(
            frame_id, "OBLIGATION", profile, document_id, snapshot_id,
            evidence, tuple(slots.items()), dossier_id,
        ))
    return tuple(frames)


def table_projection_frames(
    schedules: Iterable[PaymentScheduleProjection],
    *,
    tables: Iterable[TableSnapshot],
    profile: str,
    dossier_id: str,
    document_id: str,
    snapshot_id: str,
) -> tuple[ClauseFrame, ...]:
    by_id = {table.table_id: table for table in tables}
    frames: list[ClauseFrame] = []
    for schedule in schedules:
        table = by_id.get(schedule.table_id)
        if table is None:
            continue
        frames.extend(payment_schedule_frames(
            schedule, table=table, profile=profile, dossier_id=dossier_id,
            document_id=document_id, snapshot_id=snapshot_id,
        ))
    return tuple(frames)


def boq_check_frames(
    projection: BoqCheckProjection,
    *,
    table: TableSnapshot,
    profile: str,
    dossier_id: str,
    document_id: str,
    snapshot_id: str,
) -> tuple[ClauseFrame, ...]:
    """Keep BOQ arithmetic as a typed projection; expose only grounded totals.

    BOQ rows are not payment obligations.  A total is represented as a
    parameter frame so later comparison can reason about values without
    turning every line item into a duty.
    """
    if projection.table_id != table.table_id:
        raise ValueError("BOQ projection/table identity mismatch")
    if projection.grand_total is None:
        return ()
    raw = f"T?ng c?ng | {projection.grand_total}"
    evidence = Evidence(document_id, snapshot_id, f"{table.table_id}:total", raw)
    slots = {name: Slot(None, "UNKNOWN", (evidence,), "not_assessed") for name in sorted(SLOT_NAMES)}
    _ground(slots, "parameter", "BOQ_TOTAL", evidence)
    amount = _decimal(projection.grand_total)
    if amount is None:
        return ()
    _ground(slots, "amount", amount, evidence)
    if projection.currency:
        _ground(slots, "currency", projection.currency, evidence)
    frame_id = hashlib.sha256(f"{dossier_id}|{document_id}|{snapshot_id}|{table.table_id}|total".encode()).hexdigest()[:24]
    return (ClauseFrame(
        frame_id, "PARAMETER", profile, document_id, snapshot_id,
        (evidence,), tuple(slots.items()), dossier_id,
    ),)


def _ground(slots: dict[str, Slot], name: str, value: str | Decimal, evidence: Evidence) -> None:
    slots[name] = Slot(value, "GROUNDED", (evidence,))


def _table_scope(table: TableSnapshot) -> str | None:
    for value in (table.section_scope, table.title):
        text = str(value or "").strip()
        if text and text.casefold() not in {"table", "b?ng", "schedule", "payment schedule"}:
            return text
    return None


def _decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    raw = str(value).strip().replace("%", "").replace(",", ".")
    try:
        result = Decimal(raw)
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def _deadline(value: str) -> tuple[str | None, str | None]:
    match = re.search(r"(\d+(?:[.,]\d+)?)\s+([^\d,.;]+)", value, re.I)
    if not match:
        return None, None
    unit = _fold(match.group(2))
    if "lam viec" in unit or "business" in unit:
        normalized = "business-day"
    elif "thang" in unit or unit == "month":
        normalized = "month"
    elif "ngay" in unit or unit == "day":
        normalized = "day"
    else:
        return None, None
    return match.group(1), normalized


def _fold(value: str) -> str:
    import unicodedata
    text = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in text if unicodedata.category(char) != "Mn").strip()
