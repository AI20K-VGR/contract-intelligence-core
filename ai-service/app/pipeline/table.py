from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from hashlib import sha256

from app.contracts.models import (
    BoqCheckProjection,
    Citation,
    Fact,
    PaymentScheduleProjection,
    ReviewState,
    ToolEnvelope,
)
from app.llm.client import NineRouterClient
from app.pipeline.boq_checks import check_boq_table
from app.pipeline.payment_schedule import project_payment_schedule
from app.pipeline.runtime import ProcessingRuntime
from app.pipeline.table_headers import amount_column, fold, parse_amount
from app.tools.gateway import ToolGateway

DEFAULT_CODE = """
result = []
amount_idx = header.index("amount")
for i, row in enumerate(rows):
    raw = row[amount_idx] if amount_idx < len(row) else None
    val = decimal(raw)
    result.append({
        "row_index": i,
        "raw": raw,
        "normalized": str(val) if val is not None else None,
        "missing": raw is None or str(raw).strip() == "",
    })
"""


class TableExtractionError(RuntimeError):
    """Raised when a table cannot be safely extracted into row facts."""


@dataclass(frozen=True)
class TableProcessingLimits:
    max_pages: int = 100
    max_rows: int = 2000
    max_cells: int = 50000
    max_numeric_chars: int = 128
    max_operations: int = 250000
    max_seconds: float = 2.0


@dataclass
class TableExtractionResult:
    facts: list[Fact] = field(default_factory=list)
    payment_schedule: PaymentScheduleProjection | None = None
    boq_check: BoqCheckProjection | None = None


class TablePipeline:
    def __init__(
        self,
        gateway: ToolGateway,
        llm: NineRouterClient | None = None,
        runtime: ProcessingRuntime | None = None,
        limits: TableProcessingLimits | None = None,
    ) -> None:
        self.gateway = gateway
        self.llm = llm
        self.runtime = runtime
        self.limits = limits or TableProcessingLimits()

    def extract(self, envelope: ToolEnvelope, table_id: str) -> list[Fact]:
        return self.extract_with_projection(envelope, table_id).facts

    def extract_with_projection(self, envelope: ToolEnvelope, table_id: str) -> TableExtractionResult:
        meta = self.gateway.call("get_table_meta", envelope, table_id=table_id)
        continuation = bool(meta.get("continuation"))
        n_rows = max(0, int(meta.get("n_rows", 0)))
        n_cols = max(0, int(meta.get("n_cols", len(meta.get("header", [])))))
        row_limit = min(n_rows, self.limits.max_rows)
        if n_cols:
            row_limit = min(row_limit, self.limits.max_cells // n_cols)
        elif n_rows:
            row_limit = 0
        row_limit = min(row_limit, self.limits.max_operations // max(1, n_cols))
        cap_hit = row_limit < n_rows
        started = time.monotonic()
        all_rows = self.gateway.call("get_table_rows", envelope, table_id=table_id, start=0, end=row_limit)
        bounded_rows: list[dict] = []
        page_ids: set[str] = set()
        time_hit = False
        page_hit = False
        for item in all_rows:
            if time.monotonic() - started > self.limits.max_seconds:
                time_hit = True
                break
            row = dict(item)
            cells = list(row.get("cells", []))[:n_cols]
            row["cells"] = cells
            citations = row.get("cell_citations", {})
            for key, citation in list(citations.items()):
                if int(key) >= len(cells):
                    citations.pop(key, None)
                elif citation.get("page_revision_id"):
                    page_ids.add(citation["page_revision_id"])
            if len(page_ids) > self.limits.max_pages:
                page_hit = True
                break
            bounded_rows.append(row)
        if time.monotonic() - started > self.limits.max_seconds:
            time_hit = True
            bounded_rows = []
        reason = "processing time limit reached" if time_hit else "page limit reached" if page_hit else "row, cell, or operation limit reached" if cap_hit else None
        source_complete = not (time_hit or page_hit or cap_hit) and len(bounded_rows) == n_rows
        column = amount_column(meta["header"])
        used_llm_code = False
        facts: list[Fact] = []
        if column is not None:
          for item in bounded_rows:
            idx = item.get("row_index", 0)
            if idx < 0 or idx >= n_rows or idx in meta.get("header_row_indices", []):
                continue
            cells = item["cells"]
            raw = cells[column] if column < len(cells) else None
            oversized_value = raw is not None and len(str(raw)) > self.limits.max_numeric_chars
            row_label = " ".join(str(v or "") for v in cells[:column])
            if amount_column([str(v or "") for v in cells]) is not None or fold(row_label).startswith(("luu y:", "ghi chu:", "note:")):
                continue
            missing = raw is None or str(raw).strip() == ""
            citation_payload = item.get("cell_citations", {}).get(str(column), {})
            citation = Citation.model_validate(
                {
                    **citation_payload,
                    "node_id": citation_payload.get("node_id", table_id),
                    "page_revision_id": citation_payload.get("page_revision_id", ""),
                    "bbox": citation_payload.get("bbox") or [],
                    "text_span": str(raw) if raw is not None else str(citation_payload.get("text_span") or ""),
                }
            )
            fact_id = "tbl_" + sha256(f"{table_id}:{idx}:{column}:{citation.page_revision_id}".encode()).hexdigest()[:24]
            label = fold(row_label)
            role = _amount_role(label)
            if missing:
                facts.append(
                    Fact(
                        fact_id=fact_id,
                        role=role,
                        subject=row_label,
                        source_role=meta.get("source_role"),
                        validity=meta.get("section_scope"),
                        raw_value="MISSING",
                        normalized_value=None,
                        citation=citation,
                        provenance="L0",
                        review_state=ReviewState.NEEDS_REVIEW,
                        item_key=_row_item_key(row_label) if meta.get("source_role") == "annex" else None,
                    )
                )
                continue
            facts.append(
                Fact(
                    fact_id=fact_id,
                    role=role,
                    subject=row_label,
                    source_role=meta.get("source_role"),
                    validity=meta.get("section_scope"),
                    raw_value=str(raw),
                    normalized_value=None if oversized_value else parse_amount(raw),
                    citation=citation,
                    provenance="L2" if used_llm_code else "L0",
                    review_state=(
                        ReviewState.NEEDS_REVIEW
                        if continuation or oversized_value or parse_amount(raw) is None
                        else ReviewState.PASS
                    ),
                    item_key=_row_item_key(row_label) if meta.get("source_role") == "annex" else None,
                )
            )
        schedule = project_payment_schedule(
            table_id, meta["header"], bounded_rows, source_role=meta.get("source_role"),
            source_rows=n_rows, complete=source_complete, reason=reason,
            max_rows=self.limits.max_rows, max_cells=self.limits.max_cells,
            max_numeric_chars=self.limits.max_numeric_chars,
        )
        boq = check_boq_table(
            table_id, meta["header"], bounded_rows, source_role=meta.get("source_role"),
            source_rows=n_rows, complete=source_complete, reason=reason,
            max_rows=self.limits.max_rows, max_cells=self.limits.max_cells,
            max_numeric_chars=self.limits.max_numeric_chars,
        ) if _looks_like_boq(meta["header"]) else None
        return TableExtractionResult(facts=facts, payment_schedule=schedule, boq_check=boq)

    @staticmethod
    def _needs_fallback(executed: dict, meta: dict) -> bool:
        if executed.get("errors"):
            return True
        rows_out = executed.get("rows_out")
        if meta.get("n_rows", 0) and not isinstance(rows_out, list):
            return True
        if meta.get("n_rows", 0) and not rows_out:
            return True
        if not isinstance(rows_out, list) or any(not isinstance(item, dict) for item in rows_out):
            return True
        indices = [item.get("row_index") for item in rows_out]
        if len(indices) != meta.get("n_rows", 0) or any(type(i) is not int for i in indices):
            return True
        if set(indices) != set(range(meta.get("n_rows", 0))):
            return True
        return any(
            not isinstance(item, dict)
            or not isinstance(item.get("row_index"), int)
            or item.get("row_index") < 0
            or "raw" not in item
            or "normalized" not in item
            or "missing" not in item
            for item in (rows_out or [])
        )

    def _generate_code(self, meta: dict, strong: bool) -> str:
        prompt = (
            "Write Python assigned to `result`. Helpers: rows, header, cell(r,c), decimal(value), Decimal. "
            "Missing cells must stay None, never 0. No imports. JSON {code: '...'}"
            f"\nheader={meta['header']}\nn_rows={meta['n_rows']}\nfirst={meta['first_rows']}\nlast={meta['last_rows']}"
        )
        if self.runtime is not None:
            data = self.runtime.complete_json(
                self.llm,
                "You generate sandbox table extraction code only.",
                prompt,
                strong=strong,
            )
        else:
            data = self.llm.complete_json("You generate sandbox table extraction code only.", prompt, strong=strong)
        return (data or {}).get("code") or DEFAULT_CODE


def _looks_like_boq(headers: list[str]) -> bool:
    folded = [fold(value) for value in headers]
    has_quantity = any(any(term in value for term in ("so luong", "quantity", "qty")) for value in folded)
    has_price = any(any(term in value for term in ("don gia", "unit price", "unit cost")) for value in folded)
    has_amount = any(any(term in value for term in ("thanh tien", "amount", "gia tri")) for value in folded)
    return has_quantity and has_price and has_amount


def _amount_role(label: str) -> str:
    if re.search(r"\bvat\s*\d|\bvat$|\bthue\b", label):
        return "vat_amount"
    if "giam gia" in label or "discount" in label:
        return "discount_amount"
    if "subtotal" in label or "tam tinh" in label:
        return "subtotal_amount"
    if "tong" in label or "total" in label:
        return "total_amount"
    return "line_amount"


def _row_item_key(label: str) -> str | None:
    """Use an explicit leading row number as a comparison key only."""

    match = re.match(r"^\s*(\d+(?:\.\d+)?)\b", str(label or ""))
    return match.group(1) if match else None
