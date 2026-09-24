"""AI service canonical schemas — DOC-05c §6.

Backend Client và AI Service Server dùng chung Pydantic schemas này.
Wrap theo SemVer: bump ``ai_contract_version`` khi schema thay đổi.

Module này thuộc ``shared/ai/`` vì CẢ Backend và AI Service cùng reference.
Khi AI Service repo tách riêng, copy file này vào ``ai-service/app/contracts/``.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# -----------------------------------------------------------------------------
# Common — headers chuẩn nội bộ + bounding box CPS
# -----------------------------------------------------------------------------

# BBox CPS — [x0, y0, x1, y1] đã chuẩn hóa 0..1
BBox = tuple[float, float, float, float]


class PageKind(str, Enum):  # noqa: UP042 — match DOC-05c §6 verbatim
    """Phân loại trang sau OCR."""

    NATIVE = "native"
    SCANNED = "scanned"
    HYBRID = "hybrid"


class JobStatus(str, Enum):  # noqa: UP042 — match DOC-05c §6 verbatim
    """Vòng đời job nội bộ của AI Service."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# -----------------------------------------------------------------------------
# Usage ledger — DOC-05c §5.4 — ghi sổ chi phí LLM & latency
# -----------------------------------------------------------------------------


class UsageLedgerReport(BaseModel):
    """Hạch toán chi phí token & latency — AI service trả về mỗi completion.

    Backend lưu vào bảng ``usage_ledger`` (xem DOC-04c §11).
    """

    model_config = ConfigDict(extra="forbid")

    provider: str
    model_requested: str
    model_returned: str
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    pages_processed: int = 0
    cache_hit: bool = False
    latency_ms: int
    cost_usd: float
    price_version: str


# -----------------------------------------------------------------------------
# AI1 — OCR & Layout (POST /jobs/ocr)
# -----------------------------------------------------------------------------


class WordItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    bbox: BBox
    conf: float


class OcrLineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_no: int
    line_no: int
    text: str
    bbox: BBox
    confidence: float
    doc_char_start: int
    doc_char_end: int
    words: list[WordItem] = Field(default_factory=list)


class ClauseRegionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_no: int
    bbox: BBox
    bbox_source: str = "detector"


class ClauseNodeItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_type: str  # article | clause | point
    label: str
    number: str
    title: str
    text: str
    page_start: int
    page_end: int
    confidence: float
    doc_char_start: int
    doc_char_end: int
    regions: list[ClauseRegionItem] = Field(default_factory=list)
    # AI1 snapshot ids. Used only to rebuild parent_id before insert.
    source_id: str | None = None
    parent_source_id: str | None = None


class TableCellItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row_idx: int
    col_idx: int
    row_span: int = 1
    col_span: int = 1
    text: str
    bbox: BBox
    is_header: bool = False
    confidence: float


class DocTableItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_no: int
    bbox: BBox
    rows_count: int
    cols_count: int
    has_borders: bool
    cells: list[TableCellItem]


class PageItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_no: int
    width_pt: float
    height_pt: float
    rotation: int = 0
    kind: PageKind
    render_blob_uri: str
    preview_blob_uri: str
    features: dict[str, Any] = Field(default_factory=dict)


class Ai1SnapshotPayload(BaseModel):
    """Canonical OCR + Layout snapshot — DOC-05c §5.1."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "ai1.snapshot.v3"
    document_id: str
    total_pages: int
    pages: list[PageItem]
    full_text_nfc: str
    lines: list[OcrLineItem]
    clauses: list[ClauseNodeItem] = Field(default_factory=list)
    tables: list[DocTableItem] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# AI2 — Extraction (POST /jobs/extract)
# -----------------------------------------------------------------------------


class CitationSegmentItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_no: int
    line_id: str
    char_start: int
    char_end: int
    bbox: BBox


class CitationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quote: str
    quote_sha256: str
    doc_char_start: int
    doc_char_end: int
    segments: list[CitationSegmentItem]


class FactItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    fact_type: str
    raw_text: str
    normalized_value: dict[str, Any]
    confidence: float
    extractor: str
    context_text: str | None = None
    citation: CitationItem


class EvidenceGapItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_no: int
    crop_bbox: BBox
    reason: str
    severity: str
    suggested_profile: str | None = None


class Ai2ExtractionPayload(BaseModel):
    """Canonical extraction result — DOC-05c §5.2."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "ai2.extraction.v2"
    document_id: str
    facts: list[FactItem]
    evidence_gaps: list[EvidenceGapItem] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# AI2 — Comparison (POST /jobs/compare)
# -----------------------------------------------------------------------------


class FindingSideItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    fact_id: str | None = None
    clause_node_id: str | None = None
    citation: CitationItem
    value_snapshot: dict[str, Any] | None = None


class FindingItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_type: str  # structured | semantic
    scope: str  # contract_annex | within_document | annex_annex
    key_or_topic: str
    disposition: str
    severity: str  # high | medium | low
    confidence: float
    rationale: str
    method: str
    side_a: FindingSideItem
    side_b: FindingSideItem


class AnnexLinkItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    annex_document_id: str
    contract_document_id: str
    score: float
    annex_sequence: int
    effective_date: str | None = None
    status: str
    citation: CitationItem


class Ai2ComparisonPayload(BaseModel):
    """Canonical comparison result — DOC-05c §5.3."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "ai2.comparison.v2"
    dossier_id: str
    annex_links: list[AnnexLinkItem]
    findings: list[FindingItem]


# -----------------------------------------------------------------------------
# Request envelopes — Backend gửi sang AI service
# -----------------------------------------------------------------------------


class OcrJobRequest(BaseModel):
    """Request cho POST /jobs/ocr — DOC-05c §4.1."""

    model_config = ConfigDict(extra="forbid")

    task_id: int
    attempt_id: int
    tenant_id: str
    document_id: str
    source_blob_get_url: str
    source_sha256: str
    pages_to_process: list[int]
    render_target: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)


class ReOcrJobRequest(BaseModel):
    """Request cho POST /jobs/reocr — DOC-05c §4.2."""

    model_config = ConfigDict(extra="forbid")

    task_id: int
    attempt_id: int
    tenant_id: str
    document_id: str
    page_id: str
    page_no: int
    source_page_render_url: str
    crop_bbox: BBox | None = None
    profile: str = "high_res_binarize"
    options: dict[str, Any] = Field(default_factory=dict)


class ExtractJobRequest(BaseModel):
    """Request cho POST /jobs/extract — DOC-05c §4.3."""

    model_config = ConfigDict(extra="forbid")

    task_id: int
    attempt_id: int
    tenant_id: str
    document_id: str
    snapshot_digest: str
    document_text_nfc: str
    clause_tree: list[dict[str, Any]] = Field(default_factory=list)
    requested_schema_keys: list[str] = Field(default_factory=list)
    llm_config: dict[str, Any] = Field(default_factory=dict)


class CompareJobRequest(BaseModel):
    """Request cho POST /jobs/compare — DOC-05c §4.4."""

    model_config = ConfigDict(extra="forbid")

    task_id: int
    attempt_id: int
    tenant_id: str
    dossier_id: str
    contract_document: dict[str, Any]
    annex_documents: list[dict[str, Any]] = Field(default_factory=list)
    comparison_keys: list[str] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# Response envelopes — AI service trả về
# -----------------------------------------------------------------------------


class JobSubmission(BaseModel):
    """Response 202 Accepted khi gửi job — DOC-05c §4.1/4.2/4.3/4.4."""

    model_config = ConfigDict(extra="forbid")

    job_id: str
    kind: str
    status: JobStatus = JobStatus.QUEUED
    created_at: str


class JobStatusReport(BaseModel):
    """Response khi polling GET /jobs/{id} — DOC-05c §4.5."""

    model_config = ConfigDict(extra="forbid")

    job_id: str
    kind: str
    status: JobStatus
    progress_pct: int = 0
    current_stage: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    finished_at: str | None = None
    # Result — một trong các canonical payload khi status=completed
    result: dict[str, Any] | None = None
    usage: UsageLedgerReport | None = None
    error: dict[str, Any] | None = None


__all__ = [
    # Common
    "BBox",
    "PageKind",
    "JobStatus",
    # Ledger
    "UsageLedgerReport",
    # AI1
    "Ai1SnapshotPayload",
    "ClauseNodeItem",
    "ClauseRegionItem",
    "DocTableItem",
    "OcrLineItem",
    "PageItem",
    "TableCellItem",
    "WordItem",
    # AI2 extract
    "Ai2ExtractionPayload",
    "CitationItem",
    "CitationSegmentItem",
    "EvidenceGapItem",
    "FactItem",
    # AI2 compare
    "Ai2ComparisonPayload",
    "AnnexLinkItem",
    "FindingItem",
    "FindingSideItem",
    # Requests
    "CompareJobRequest",
    "ExtractJobRequest",
    "OcrJobRequest",
    "ReOcrJobRequest",
    # Responses
    "JobStatusReport",
    "JobSubmission",
]
