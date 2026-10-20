from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from app.contracts.models import (
    Citation,
    PaymentMilestoneProjection,
    PaymentScheduleProjection,
    ReviewState,
    TableProjectionCoverage,
)
from app.pipeline.table_headers import fold


def project_payment_schedule(
    table_id: str,
    headers: list[str],
    rows: list[dict[str, Any]],
    *,
    source_role: str | None = None,
    source_rows: int | None = None,
    complete: bool = True,
    reason: str | None = None,
    max_rows: int = 2000,
    max_cells: int = 50000,
    max_numeric_chars: int = 128,
) -> PaymentScheduleProjection | None:
    """Project payment milestones while retaining row evidence and source values."""
    folded = [fold(value) for value in headers]
    percent_col = _find(folded, ("ty le", "phan tram", "percent", "rate", "%"))
    if percent_col is None or not any(token in " ".join(folded) for token in ("thanh toan", "payment", "dot")):
        return None
    label_col = _find(folded, ("dot", "milestone", "giai doan", "lan"))
    event_col = _find(folded, ("moc thanh toan", "su kien", "event", "milestone"))
    trigger_col = _find(folded, ("dieu kien", "trigger", "condition", "can cu"))
    deadline_col = _find(folded, ("thoi han", "deadline", "within", "ngay"))
    condition_col = _find(folded, ("dieu kien", "condition", "trigger"))
    base_col = _find(folded, ("co so", "base", "gia tri tinh"))
    max_cells = max(0, max_cells)
    selected = rows[:max_rows]
    processed_cells = min(sum(len(item.get("cells", [])) for item in selected), max_cells)
    cell_limited = sum(len(item.get("cells", [])) for item in selected) > max_cells
    source_rows = max(len(rows), source_rows or len(rows))
    partial_reason = reason or ("row or cell processing cap reached" if len(rows) > len(selected) or cell_limited else None)
    is_complete = complete and source_rows <= max_rows and not cell_limited and partial_reason is None
    milestones: list[PaymentMilestoneProjection] = []
    issues: list[str] = []
    seen: set[str] = set()
    total = Decimal("0")
    percent_valid = True
    pages: set[str] = set()
    has_data_gap = False
    oversized_numeric = False
    for row in selected:
        cells = row.get("cells", [])
        label = _cell(cells, label_col) or ""
        raw_percent = _cell(cells, percent_col)
        normalized = _percent(raw_percent, max_numeric_chars)
        if not label and not raw_percent:
            continue
        citation_col = label_col if label_col is not None and _citation(row, label_col) else percent_col
        citation = _citation(row, citation_col) or Citation(
            node_id=table_id, page_revision_id="", text_span=label or str(raw_percent or "")
        )
        pages.add(citation.page_revision_id)
        milestone_id = label.strip() or f"row-{row.get('row_index', len(milestones)) + 1}"
        if milestone_id in seen:
            issues.append(f"duplicate milestone label: {milestone_id}")
            percent_valid = False
        seen.add(milestone_id)
        if raw_percent is not None and len(str(raw_percent)) > max_numeric_chars:
            oversized_numeric = True
        if normalized is None or not Decimal("0") < Decimal(normalized) <= Decimal("100"):
            percent_valid = False
            has_data_gap = True
            issues.append(f"missing or invalid percentage for {milestone_id}")
        else:
            total += Decimal(normalized)
        milestones.append(PaymentMilestoneProjection(
            milestone_id=milestone_id,
            raw_label=label,
            raw_percent=str(raw_percent) if raw_percent is not None else None,
            percent=normalized,
            event=_cell(cells, event_col),
            trigger=_cell(cells, trigger_col),
            deadline=_cell(cells, deadline_col),
            condition=_cell(cells, condition_col),
            base=_cell(cells, base_col),
            raw_cells=[str(value) if value is not None else None for value in cells],
            citation=citation,
            cell_citations={
                str(index): Citation.model_validate(payload)
                for index, payload in row.get("cell_citations", {}).items()
                if int(index) < len(cells)
            },
        ))
    if not milestones and source_rows == 0:
        return None
    if oversized_numeric:
        is_complete = False
        partial_reason = "numeric character limit reached"
    elif has_data_gap and is_complete:
        is_complete = False
        partial_reason = "required milestone field missing or invalid"
    if not is_complete:
        issues.append(partial_reason or "source table is incomplete")
    if percent_valid and is_complete and total != Decimal("100"):
        issues.append("milestone percentages do not total 100")
    passed = is_complete and percent_valid and total == Decimal("100") and not any("duplicate" in item for item in issues)
    coverage = TableProjectionCoverage(
        complete=is_complete,
        source_rows=source_rows,
        processed_rows=len(selected),
        source_cells=source_rows * len(headers),
        processed_cells=processed_cells,
        page_count=len(pages),
        reason=partial_reason,
    )
    return PaymentScheduleProjection(
        table_id=table_id,
        source_role=source_role if source_role in {"body", "annex"} else None,
        milestones=milestones,
        total_percent=str(total) if percent_valid and is_complete else None,
        review_state=ReviewState.PASS if passed else ReviewState.NEEDS_REVIEW,
        coverage=coverage,
        issues=issues,
        raw_rows=[[str(value) if value is not None else None for value in item.get("cells", [])] for item in selected],
    )


def _find(headers: list[str], terms: tuple[str, ...]) -> int | None:
    return next((i for i, value in enumerate(headers) if any(term in value for term in terms)), None)


def _cell(cells: list[Any], index: int | None) -> str | None:
    if index is None or index >= len(cells) or cells[index] is None:
        return None
    value = str(cells[index]).strip()
    return value or None


def _citation(row: dict[str, Any], index: int) -> Citation | None:
    payload = row.get("cell_citations", {}).get(str(index))
    return Citation.model_validate(payload) if payload else None


def _percent(value: Any, limit: int) -> str | None:
    if value is None:
        return None
    raw = str(value).strip().replace("%", "").replace(",", ".").strip()
    if not raw or len(raw) > limit or not re.fullmatch(r"\d+(?:\.\d+)?", raw):
        return None
    try:
        number = Decimal(raw)
    except InvalidOperation:
        return None
    return format(number.normalize(), "f") if number.is_finite() else None
