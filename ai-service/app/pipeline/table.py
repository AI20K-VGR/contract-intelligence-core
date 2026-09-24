from __future__ import annotations

from hashlib import sha256
import re

from app.contracts.models import Citation, Fact, ReviewState, ToolEnvelope
from app.llm.client import NineRouterClient
from app.pipeline.runtime import ProcessingRuntime
from app.tools.gateway import ToolGateway
from app.pipeline.table_headers import amount_column, fold, parse_amount

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


class TablePipeline:
    def __init__(
        self,
        gateway: ToolGateway,
        llm: NineRouterClient | None = None,
        runtime: ProcessingRuntime | None = None,
    ) -> None:
        self.gateway = gateway
        self.llm = llm
        self.runtime = runtime

    def extract(self, envelope: ToolEnvelope, table_id: str) -> list[Fact]:
        meta = self.gateway.call("get_table_meta", envelope, table_id=table_id)
        continuation = bool(meta.get("continuation"))
        column = amount_column(meta["header"])
        if column is None:
            return []
        used_llm_code = False
        facts: list[Fact] = []
        all_rows = self.gateway.call("get_table_rows", envelope, table_id=table_id, start=0, end=meta["n_rows"])
        for item in all_rows:
            idx = item.get("row_index", 0)
            if idx < 0 or idx >= len(all_rows) or idx in meta.get("header_row_indices", []):
                continue
            cells = all_rows[idx]["cells"]
            raw = cells[column] if column < len(cells) else None
            row_label = " ".join(str(v or "") for v in cells[:column])
            if amount_column([str(v or "") for v in cells]) is not None or fold(row_label).startswith(("luu y:", "ghi chu:", "note:")):
                continue
            missing = raw is None or str(raw).strip() == ""
            citation_payload = all_rows[idx].get("cell_citations", {}).get(str(column), {})
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
                    normalized_value=parse_amount(raw),
                    citation=citation,
                    provenance="L2" if used_llm_code else "L0",
                    review_state=(
                        ReviewState.NEEDS_REVIEW
                        if continuation or parse_amount(raw) is None
                        else ReviewState.PASS
                    ),
                    item_key=_row_item_key(row_label) if meta.get("source_role") == "annex" else None,
                )
            )
        return facts

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
