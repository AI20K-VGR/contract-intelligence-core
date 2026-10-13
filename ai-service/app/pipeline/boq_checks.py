from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from app.contracts.models import BoqCheckProjection, Citation, ReviewState, TableProjectionCoverage
from app.pipeline.table_headers import fold


def check_boq_table(
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
) -> BoqCheckProjection:
    folded = [fold(value) for value in headers]
    description = _find(folded, ("hang muc", "description", "item", "dien giai"))
    quantity = _find(folded, ("so luong", "quantity", "qty"))
    unit_price = _find(folded, ("don gia", "unit price", "unit cost"))
    amount = _find(folded, ("thanh tien", "amount", "gia tri", "subtotal", "tong cong", "total"))
    if description is None and quantity is None and unit_price is None:
        return BoqCheckProjection(
            table_id=table_id, source_role=source_role if source_role in {"body", "annex"} else None,
            line_count=0, review_state=ReviewState.NEEDS_REVIEW,
            coverage=_coverage(rows, source_rows, len(headers), 0, 0, complete, reason or "BOQ columns not identified"),
            issues=["BOQ columns not identified"],
        )
    max_rows = max(0, max_rows)
    max_cells = max(0, max_cells)
    selected = rows[:max_rows]
    offered_cells = sum(len(item.get("cells", [])) for item in selected)
    cell_limited = offered_cells > max_cells
    source_rows = max(len(rows), source_rows or len(rows))
    partial_reason = reason or ("row or cell processing cap reached" if len(rows) > max_rows or cell_limited else None)
    is_complete = complete and source_rows <= max_rows and not cell_limited and partial_reason is None
    line_sum = Decimal("0")
    line_count = 0
    citations: list[Citation] = []
    issues: list[str] = []
    currency = _currency(headers)
    tax_rate: Decimal | None = None
    summary_amounts: dict[str, Decimal] = {}
    parsed_any = False
    oversized_numeric = False

    for row in selected:
        cells = row.get("cells", [])
        label = " ".join(str(value or "") for value in cells[: (amount if amount is not None else len(cells))])
        folded_label = fold(label)
        raw_amount = _cell(cells, amount)
        raw_qty = _cell(cells, quantity)
        raw_price = _cell(cells, unit_price)
        if any(value is not None and len(value) > max_numeric_chars for value in (raw_amount, raw_qty, raw_price)):
            oversized_numeric = True
        amount_value = _decimal(raw_amount, max_numeric_chars) if amount is not None else None
        if amount_value is not None:
            parsed_any = True
            citation = _citation(row, amount)
            if citation:
                citations.append(citation)
        kind = _summary_kind(folded_label) if not raw_qty and not raw_price else None
        if kind:
            if amount_value is not None:
                if kind in summary_amounts and summary_amounts[kind] != amount_value:
                    issues.append(f"conflicting {kind} values")
                summary_amounts[kind] = amount_value
            match = re.search(r"(?:vat|thue)\s*(\d+(?:[.,]\d+)?)\s*%", folded_label)
            if match:
                tax_rate = _decimal(match.group(1), max_numeric_chars)
            continue
        if _is_header_or_empty(cells):
            continue
        qty = _decimal(raw_qty, max_numeric_chars) if quantity is not None else None
        price = _decimal(raw_price, max_numeric_chars) if unit_price is not None else None
        if qty is None and price is None and amount_value is None:
            continue
        line_count += 1
        if qty is None or price is None or amount_value is None:
            issues.append(f"incomplete amount cells at row {row.get('row_index', 0)}")
            continue
        expected = qty * price
        if expected != amount_value:
            issues.append(f"quantity × unit price mismatch at row {row.get('row_index', 0)}")
        line_sum += amount_value
        for column in (quantity, unit_price, amount):
            citation = _citation(row, column)
            if citation:
                citations.append(citation)

    stated_subtotal = summary_amounts.get("subtotal")
    tax_amount = summary_amounts.get("tax")
    grand_total = summary_amounts.get("total")
    if stated_subtotal is not None and stated_subtotal != line_sum:
        issues.append("line sum does not match stated subtotal")
    if tax_amount is not None and stated_subtotal is not None and grand_total is not None and stated_subtotal + tax_amount != grand_total:
        issues.append("subtotal plus tax does not match grand total")
    if tax_rate is not None and stated_subtotal is not None and tax_amount is not None:
        expected_tax = (stated_subtotal * tax_rate / Decimal("100")).quantize(Decimal("0.01"))
        if abs(expected_tax - tax_amount) > Decimal("1"):
            issues.append("tax amount does not match stated tax rate")
    if not currency:
        issues.append("currency is missing or ambiguous")
    if not parsed_any or line_count == 0:
        issues.append("no complete BOQ line amounts found")
    if oversized_numeric:
        is_complete = False
        partial_reason = "numeric character limit reached"
    if not is_complete:
        issues.append(partial_reason or "source table is incomplete")
    passed = is_complete and parsed_any and line_count > 0 and bool(currency) and not issues
    return BoqCheckProjection(
        table_id=table_id,
        source_role=source_role if source_role in {"body", "annex"} else None,
        currency=currency,
        line_count=line_count,
        computed_line_sum=_format(line_sum) if parsed_any and line_count and is_complete else None,
        stated_subtotal=_format(stated_subtotal) if stated_subtotal is not None else None,
        tax_rate=_format(tax_rate) if tax_rate is not None else None,
        tax_amount=_format(tax_amount) if tax_amount is not None else None,
        grand_total=_format(grand_total) if grand_total is not None else None,
        review_state=ReviewState.PASS if passed else ReviewState.NEEDS_REVIEW,
        coverage=_coverage(rows, source_rows, len(headers), len(selected), min(offered_cells, max_cells), is_complete, partial_reason),
        citations=_unique_citations(citations),
        issues=issues,
    )


def _find(headers: list[str], terms: tuple[str, ...]) -> int | None:
    return next((i for i, value in enumerate(headers) if any(term in value for term in terms)), None)


def _cell(cells: list[Any], index: int | None) -> str | None:
    if index is None or index >= len(cells) or cells[index] is None:
        return None
    value = str(cells[index]).strip()
    return value or None


def _citation(row: dict[str, Any], index: int | None) -> Citation | None:
    if index is None:
        return None
    payload = row.get("cell_citations", {}).get(str(index))
    return Citation.model_validate(payload) if payload else None


def _decimal(value: Any, limit: int) -> Decimal | None:
    if value is None:
        return None
    raw = str(value).strip().replace(" ", "").replace("₫", "").replace("đ", "").replace("VND", "").replace("USD", "")
    if not raw or len(raw) > limit or not re.fullmatch(r"[+-]?\d+(?:[.,]\d+)*", raw):
        return None
    if re.fullmatch(r"[+-]?\d{1,3}[.,]\d{3}", raw):
        return None  # Single grouped-looking separator is locale-ambiguous.
    # Vietnamese grouped thousands are unambiguous with repeated 3-digit groups.
    if "." in raw and "," not in raw and re.fullmatch(r"[+-]?\d{1,3}(?:\.\d{3})+", raw):
        raw = raw.replace(".", "")
    elif "," in raw and "." not in raw and re.fullmatch(r"[+-]?\d{1,3}(?:,\d{3})+", raw):
        raw = raw.replace(",", "")
    elif "." in raw and "," in raw:
        decimal_sep = "." if raw.rfind(".") > raw.rfind(",") else ","
        group_sep = "," if decimal_sep == "." else "."
        raw = raw.replace(group_sep, "").replace(decimal_sep, ".")
    elif "," in raw:
        raw = raw.replace(",", ".")
    try:
        result = Decimal(raw)
    except InvalidOperation:
        return None
    return result if result.is_finite() and abs(result.adjusted()) <= 100 else None


def _currency(headers: list[str]) -> str | None:
    text = " ".join(fold(value) for value in headers)
    has_vnd = any(token in text for token in ("vnd", "vnđ", "dong", "đong"))
    has_usd = "usd" in text or "$" in text
    if has_vnd == has_usd:
        return None
    return "VND" if has_vnd else "USD"


def _summary_kind(label: str) -> str | None:
    if re.search(r"\b(vat|thue)\b", label):
        return "tax"
    if any(token in label for token in ("tong cong", "grand total", "total")):
        return "total"
    if any(token in label for token in ("tam tinh", "subtotal", "cong")):
        return "subtotal"
    return None


def _is_header_or_empty(cells: list[Any]) -> bool:
    return not any(str(value or "").strip() for value in cells)


def _format(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value.normalize(), "f")


def _unique_citations(citations: list[Citation]) -> list[Citation]:
    unique: dict[str, Citation] = {}
    for citation in citations:
        key = citation.citation_id or "|".join((citation.node_id, citation.page_revision_id, citation.cell_id or "", citation.text_span))
        unique.setdefault(key, citation)
    return list(unique.values())


def _coverage(rows, source_rows, n_cols, processed_rows, processed_cells, complete, reason):
    source_rows = max(len(rows), source_rows or len(rows))
    return TableProjectionCoverage(
        complete=bool(complete), source_rows=source_rows, processed_rows=processed_rows,
        source_cells=source_rows * n_cols, processed_cells=processed_cells,
        page_count=len({citation.get("page_revision_id") for row in rows for citation in row.get("cell_citations", {}).values() if citation.get("page_revision_id")}),
        reason=reason,
    )
