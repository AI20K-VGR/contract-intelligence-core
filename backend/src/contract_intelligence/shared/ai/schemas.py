"""AI service canonical schemas — DOC-05c §6.

Backend Client và AI Service Server dùng chung Pydantic schemas này.
Wrap theo SemVer: bump ``ai_contract_version`` khi schema thay đổi.

Module này thuộc ``shared/ai/`` vì CẢ Backend và AI Service cùng reference.
Khi AI Service repo tách riêng, copy file này vào ``ai-service/app/contracts/``.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    # None: AI1 gave no confidence for this line (unknown, not 0).
    confidence: float | None = Field(default=None, ge=0, le=1)
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
    source_id: str | None = None
    continued_from_source_id: str | None = None
    is_multi_page: bool = False


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


class SemanticWireCitation(BaseModel):
    node_id: str
    page_revision_id: str
    bbox: list[float] = Field(default_factory=list)
    bbox_fragments: list[list[float]] = Field(default_factory=list)
    text_span: str
    source_file_id: str | None = None
    page: int | None = None
    page_range: list[int] = Field(default_factory=list)
    line_ids: list[str] = Field(default_factory=list)
    char_start: int | None = None
    char_end: int | None = None
    breadcrumb: list[str] = Field(default_factory=list)
    structure_path: str | None = None
    geometry_available: bool = False
    citation_id: str | None = None
    source_hash: str | None = None
    quote_sha256: str | None = None
    coordinate_system: str | None = None
    geometry_source: str | None = None
    precision: str | None = None
    validation_status: str = "UNVERIFIED"
    table_id: str | None = None
    cell_id: str | None = None


class SemanticClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ContextBounds(SemanticClosedModel):
    max_hops: int = Field(ge=0, le=8, strict=True)
    max_nodes: int = Field(ge=1, le=256, strict=True)
    max_context_tokens: int = Field(ge=1, le=32768, strict=True)
    max_output_tokens: int = Field(ge=1, le=8192, strict=True)
    max_llm_calls: int = Field(ge=0, le=20, strict=True)
    max_seconds: int = Field(ge=1, le=300, strict=True)


class SemanticAlias(SemanticClosedModel):
    source: str
    symbol: str
    kind: Literal["action", "qualifier"]
    proposal_id: str


class SemanticProfile(SemanticClosedModel):
    schema_version: Literal["ai2.semantic-profile.v1"]
    capability: Literal["ai2.semantic.v1"]
    tenant_id: str = Field(min_length=1)
    version: int = Field(ge=1, strict=True)
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    contract_type: Literal[
        "SALES", "SUPPLY_SERVICE", "LEASE", "CONSTRUCTION_WORK", "EMPLOYMENT", "NDA"
    ]
    alias_version: int = Field(ge=0, strict=True)
    alias_digest: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    aliases: list[SemanticAlias] = Field(default_factory=list)
    activation_state: Literal["ACTIVE", "DRAFT_ONLY"]
    context_bounds: ContextBounds
    alias_proposal_minimum_length: int | None = Field(default=None, ge=4, le=120, strict=True)

    @model_validator(mode="after")
    def pinned_digest(self):
        import hashlib
        import json

        from contract_intelligence.shared.ai.tenant_lexicon_contracts import (
            digest_json,
            normalize_source,
            validate_alias,
        )

        payload = self.model_dump(mode="json", exclude={"digest"})
        expected = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if self.digest != expected:
            raise ValueError("semantic profile digest mismatch")
        if self.activation_state != "ACTIVE" and self.aliases:
            raise ValueError("draft profile must not activate aliases")
        if self.alias_version == 0 and (self.aliases or self.alias_digest is not None):
            raise ValueError("unversioned alias profile")
        if self.alias_version:
            seen = set()
            for alias in self.aliases:
                validate_alias(alias.source, alias.symbol, alias.kind, minimum_length=4)
                key = (alias.kind, normalize_source(alias.source))
                if key in seen:
                    raise ValueError("alias collision")
                seen.add(key)
            alias_data = {
                "tenant_id": self.tenant_id,
                "version": self.alias_version,
                "aliases": [
                    {
                        "source": normalize_source(a.source),
                        "symbol": a.symbol,
                        "kind": a.kind,
                        "proposal_id": a.proposal_id,
                    }
                    for a in sorted(
                        self.aliases, key=lambda a: (a.kind, normalize_source(a.source))
                    )
                ],
            }
            if digest_json(alias_data) != self.alias_digest:
                raise ValueError("alias digest mismatch")
        return self


class SemanticCitation(SemanticWireCitation):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SemanticEvidence(SemanticClosedModel):
    document_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    raw: str = Field(min_length=1)
    citation: SemanticCitation


class SemanticSlot(SemanticClosedModel):
    value_type: Literal["DECIMAL", "TEXT", "NONE"]
    value: str | None
    state: Literal["GROUNDED", "UNKNOWN", "ABSENT", "UNSUPPORTED"]
    evidence: list[SemanticEvidence]
    reason: str

    @model_validator(mode="after")
    def typed_value(self):
        if self.value_type == "NONE" and self.value is not None:
            raise ValueError("NONE value must be null")
        if self.value_type != "NONE" and self.value is None:
            raise ValueError("typed value required")
        if self.value_type == "DECIMAL":
            from decimal import InvalidOperation

            try:
                valid = Decimal(self.value).is_finite()
            except InvalidOperation as exc:
                raise ValueError("invalid decimal text") from exc
            if not valid:
                raise ValueError("finite decimal required")
        if self.state == "GROUNDED" and (
            not self.value or not self.value.strip() or not self.evidence
        ):
            raise ValueError("grounded value and evidence required")
        if self.state == "ABSENT" and (self.value is not None or not self.evidence):
            raise ValueError("absent requires source and null value")
        return self


class SemanticKey(SemanticClosedModel):
    key: list[str] | None
    certainty: Literal["DEFINITE", "UNKNOWN"]
    reason: str
    method: Literal["CLOSED_SYMBOL", "TENANT_ALIAS"]
    alias_digest: str | None = Field(pattern=r"^[a-f0-9]{64}$")
    alias_version: int | None = Field(ge=1, strict=True)
    alias_proposal_ids: list[str]

    @model_validator(mode="after")
    def certainty_and_method(self):
        if self.certainty == "UNKNOWN" and self.key is not None:
            raise ValueError("unknown key cannot carry identity")
        if self.certainty == "DEFINITE" and (not self.key or any(not s.strip() for s in self.key)):
            raise ValueError("definite key needs identity")
        if self.method == "TENANT_ALIAS" and (
            not self.alias_digest or not self.alias_version or not self.alias_proposal_ids
        ):
            raise ValueError("tenant alias provenance required")
        return self


class SemanticFrame(SemanticClosedModel):
    frame_id: str
    family: Literal["OBLIGATION", "RIGHT", "PROHIBITION", "REMEDY", "PARAMETER", "DEFINITION"]
    profile: str
    document_id: str
    snapshot_id: str
    dossier_id: str
    evidence: list[SemanticEvidence] = Field(min_length=1)
    slots: dict[str, SemanticSlot]
    key: SemanticKey

    @model_validator(mode="after")
    def scoped_slots(self):
        slot_names = {
            "actor",
            "beneficiary",
            "action",
            "qualifier",
            "modality_negation",
            "object_scope",
            "condition",
            "exception",
            "temporal_trigger",
            "deadline",
            "deadline_unit",
            "amount",
            "currency",
            "unit",
            "base",
            "period",
            "parameter",
            "definition",
        }

        if set(self.slots) - slot_names:
            raise ValueError("unknown semantic slot")
        for evidence in [*self.evidence, *(e for s in self.slots.values() for e in s.evidence)]:
            if (evidence.document_id, evidence.snapshot_id) != (self.document_id, self.snapshot_id):
                raise ValueError("semantic evidence scope mismatch")
        return self


class SemanticPair(SemanticClosedModel):
    pair_id: str
    left_id: str
    right_id: str
    disposition: Literal[
        "DUPLICATE",
        "COMPARABLE_DIFFERENCE",
        "NOT_COMPARABLE",
        "GENERAL_VS_SPECIFIC",
        "SCOPE_DIFFERS",
        "NEEDS_REVIEW_UNPARSED",
        "NEEDS_REVIEW_BACKOFF",
        "GRADUATED",
        "CUMULATIVE",
        "CONFLICT_CANDIDATE",
    ]
    reason: str
    left_evidence: list[SemanticEvidence] = Field(min_length=1)
    right_evidence: list[SemanticEvidence] = Field(min_length=1)
    review_state: Literal["NEEDS_REVIEW"] = "NEEDS_REVIEW"
    method: Literal["CLOSED_SYMBOL", "TENANT_ALIAS"]
    candidate_sources: list[str]
    # Optional v2 diagnostics; omitted by legacy producers/readers.
    alignment_key: list[str] | None = None
    conflict_kind: (
        Literal[
            "SEMANTIC_CONFLICT",
            "ARITHMETIC_INCONSISTENCY",
            "AMENDMENT_REVIEW",
            "COMPARABLE_DIFFERENCE",
        ]
        | None
    ) = None
    slots_in_difference: list[str] = Field(default_factory=list)


class SemanticTimeline(SemanticClosedModel):
    edge_id: str
    source_id: str
    target_id: str | None
    relation: Literal["REFERENCES", "AMENDS"]
    date_role: Literal["EFFECTIVE", "SIGNING", "UNKNOWN"]
    date_value: str | None
    evidence: list[SemanticEvidence] = Field(min_length=1)
    acceptance: SemanticSlot | None
    value_slot: str | None
    proposed_value: SemanticSlot | None
    reasons: list[str]
    review_state: Literal["NEEDS_REVIEW"] = "NEEDS_REVIEW"

    @model_validator(mode="after")
    def review_only_proposal(self):
        from datetime import date

        if self.date_value is not None:
            date.fromisoformat(self.date_value)
        if self.proposed_value is not None and (
            self.relation != "AMENDS"
            or self.date_role != "EFFECTIVE"
            or self.date_value is None
            or self.acceptance is None
            or self.acceptance.state != "GROUNDED"
            or self.acceptance.value != "ACCEPTED"
            or self.target_id is None
            or self.proposed_value.state != "GROUNDED"
        ):
            raise ValueError("unproven amendment proposal")
        if self.proposed_value is not None:
            import unicodedata

            def folded(value):
                return "".join(
                    c
                    for c in unicodedata.normalize("NFD", value.casefold()).replace("đ", "d")
                    if unicodedata.category(c) != "Mn"
                )

            if not any(
                folded(e.raw).startswith("cac ben dong y sua doi ")
                for e in self.acceptance.evidence
            ):
                raise ValueError("affirmative amendment acceptance evidence required")
            if not any(
                self.date_value in e.raw and "co hieu luc tu" in folded(e.raw)
                for e in self.evidence
            ):
                raise ValueError("effective date source required")
        return self


class SemanticCoverage(SemanticClosedModel):
    state: Literal["NEEDS_REVIEW", "NOT_MEASURED"]
    attempted_nodes: int = Field(ge=0)
    frames: int = Field(ge=0)
    grounded_slots: int = Field(ge=0)
    unresolved_slots: int = Field(ge=0)
    invalid_evidence: int = Field(ge=0)
    reasons: list[str]
    context_nodes: int = Field(ge=0)
    context_calls: int = Field(ge=0)
    by_family: dict[str, dict[str, int]] = Field(default_factory=dict)
    by_slot: dict[str, dict[str, int]] = Field(default_factory=dict)
    by_output: dict[str, dict[str, int]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def counters(self):
        for groups in (self.by_family, self.by_slot, self.by_output):
            for values in groups.values():
                if set(values) != {"attempted", "covered", "review", "missing"} or any(
                    type(v) is not int or v < 0 for v in values.values()
                ):
                    raise ValueError("invalid semantic coverage counters")
                if any(
                    values[name] > values["attempted"] for name in ("covered", "review", "missing")
                ):
                    raise ValueError("coverage counts exceed denominator")
        return self


class SemanticAliasDraft(SemanticClosedModel):
    source: str
    symbol: str
    kind: Literal["action", "qualifier"]
    source_ref: str
    status: Literal["DRAFT"] = "DRAFT"


class SemanticExtension(SemanticClosedModel):
    schema_version: Literal["ai2.semantic.v1"]
    tenant_id: str
    dossier_id: str
    profile_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    alias_version: int = Field(ge=0)
    alias_digest: str | None
    frames: list[SemanticFrame]
    rows: list[str]
    pairs: list[SemanticPair]
    timeline: list[SemanticTimeline]
    alias_drafts: list[SemanticAliasDraft]
    coverage: SemanticCoverage

    @model_validator(mode="after")
    def references(self):
        frames = {f.frame_id: f for f in self.frames}
        if (
            len(frames) != len(self.frames)
            or len(set(self.rows)) != len(self.rows)
            or set(self.rows) != set(frames)
        ):
            raise ValueError("semantic row/frame identity mismatch")
        if any(f.dossier_id != self.dossier_id for f in self.frames):
            raise ValueError("semantic dossier mismatch")
        if any(
            f.key.method == "TENANT_ALIAS"
            and (
                f.key.alias_version != self.alias_version or f.key.alias_digest != self.alias_digest
            )
            for f in self.frames
        ):
            raise ValueError("semantic key alias pin mismatch")
        for pair in self.pairs:
            if (
                pair.left_id not in frames
                or pair.right_id not in frames
                or pair.left_id == pair.right_id
            ):
                raise ValueError("semantic pair target mismatch")
            if (
                pair.left_evidence != frames[pair.left_id].evidence
                or pair.right_evidence != frames[pair.right_id].evidence
            ):
                raise ValueError("semantic pair evidence mismatch")
            if pair.disposition == "DUPLICATE":
                left, right = frames[pair.left_id], frames[pair.right_id]
                required = {
                    "actor",
                    "action",
                    "modality_negation",
                    "object_scope",
                    "beneficiary",
                    "condition",
                    "exception",
                    "temporal_trigger",
                    "deadline",
                }
                if left.family == "PARAMETER" and "parameter" in left.slots:
                    required.difference_update(
                        {"actor", "action", "modality_negation", "beneficiary"}
                    )
                    required.add("parameter")
                elif left.family == "DEFINITION":
                    required = {
                        "parameter",
                        "definition",
                        "object_scope",
                        "condition",
                        "exception",
                        "temporal_trigger",
                    }
                if left.family == "REMEDY":
                    required.add("qualifier")
                if left.family in {"REMEDY", "PARAMETER"} or any(
                    f.slots.get("amount")
                    and f.slots["amount"].value is not None
                    or f.slots.get("action")
                    and f.slots["action"].value in {"PAY", "COMPENSATE", "PENALTY"}
                    for f in (left, right)
                ):
                    required.update({"amount", "unit", "currency", "base", "period"})
                required.update(
                    name
                    for f in (left, right)
                    for name, slot in f.slots.items()
                    if slot.state in {"GROUNDED", "ABSENT"}
                )
                if (
                    left.key.certainty != "DEFINITE"
                    or right.key.certainty != "DEFINITE"
                    or left.key.key != right.key.key
                    or left.family != right.family
                    or left.profile != right.profile
                    or any(
                        name not in f.slots or f.slots[name].state in {"UNKNOWN", "UNSUPPORTED"}
                        for f in (left, right)
                        for name in required
                    )
                    or any(
                        e.citation.validation_status != "VALID"
                        for f in (left, right)
                        for e in f.evidence
                    )
                ):
                    raise ValueError("DUPLICATE requires assessed grounded evidence")
                key_fields = {"qualifier"} if left.family == "REMEDY" else set()
                if left.family != "DEFINITION" and not (
                    left.family == "PARAMETER" and "parameter" in left.slots
                ):
                    key_fields.add("action")
                for name in required - key_fields:
                    a, b = left.slots[name], right.slots[name]
                    values = (
                        (Decimal(a.value), Decimal(b.value))
                        if a.value_type == b.value_type == "DECIMAL"
                        else (a.value, b.value)
                    )
                    if a.state != b.state or a.value_type != b.value_type or values[0] != values[1]:
                        raise ValueError("DUPLICATE cannot hide assessed slot differences")
        if len({p.pair_id for p in self.pairs}) != len(self.pairs):
            raise ValueError("duplicate semantic pair")
        for edge in self.timeline:
            if edge.source_id not in frames:
                raise ValueError("semantic timeline source missing")
            allowed = {
                (frames[x].document_id, frames[x].snapshot_id)
                for x in (edge.source_id, edge.target_id)
                if x in frames
            }
            evidence = [
                *edge.evidence,
                *(edge.acceptance.evidence if edge.acceptance else []),
                *(edge.proposed_value.evidence if edge.proposed_value else []),
            ]
            if any((e.document_id, e.snapshot_id) not in allowed for e in evidence):
                raise ValueError("semantic timeline evidence scope mismatch")
            if edge.target_id not in frames and "missing_target" not in edge.reasons:
                raise ValueError("missing timeline target must remain visible")
            if edge.proposed_value and any(
                e.citation.validation_status != "VALID" for e in evidence
            ):
                raise ValueError("amendment proposal citations must verify")
        if len({e.edge_id for e in self.timeline}) != len(self.timeline):
            raise ValueError("duplicate timeline edge")
        if self.coverage.frames != len(frames):
            raise ValueError("semantic frame coverage mismatch")
        return self
