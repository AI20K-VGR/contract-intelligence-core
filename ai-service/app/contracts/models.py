from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ReviewState(str, Enum):
    PASS = "PASS"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    BLOCKED = "BLOCKED"
    ANSWERED = "ANSWERED"
    NOT_COMPARABLE = "NOT_COMPARABLE"


class TableCoverage(str, Enum):
    """What the upstream handoff actually established about tables."""

    NOT_PRESENT = "NOT_PRESENT"
    DETECTED = "DETECTED"
    UNKNOWN = "UNKNOWN"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"


class JobStatus(str, Enum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class LifecycleState(str, Enum):
    ACTIVE = "ACTIVE"
    SOFT_DELETED = "SOFT_DELETED"
    PURGE_PENDING = "PURGE_PENDING"
    PURGED = "PURGED"


class ObjectRoute(str, Enum):
    FIELD = "FIELD"
    TABLE = "TABLE"
    CLAUSE = "CLAUSE"
    COMPARE = "COMPARE"
    QUERY = "QUERY"


class FindingType(str, Enum):
    MATCH = "MATCH"
    DIVERGENCE = "DIVERGENCE"
    GAP = "GAP"
    AMBIGUITY = "AMBIGUITY"
    COMPARABLE_MATCH = "COMPARABLE_MATCH"
    COMPARABLE_DIFFERENCE = "COMPARABLE_DIFFERENCE"
    CANDIDATE_AMENDMENT = "CANDIDATE_AMENDMENT"
    NEEDS_EVIDENCE = "NEEDS_EVIDENCE"


class Disposition(str, Enum):
    NEEDS_EVIDENCE = "NEEDS_EVIDENCE"
    NOT_COMPARABLE = "NOT_COMPARABLE"
    CANDIDATE_AMENDMENT = "CANDIDATE_AMENDMENT"
    COMPARABLE_MATCH = "COMPARABLE_MATCH"
    COMPARABLE_DIFFERENCE = "COMPARABLE_DIFFERENCE"


class ComparisonScope(str, Enum):
    WITHIN_DOCUMENT = "WITHIN_DOCUMENT"
    CONTRACT_ANNEX = "CONTRACT_ANNEX"
    ANNEX_ANNEX = "ANNEX_ANNEX"


class RelationType(str, Enum):
    PARENT_OF = "PARENT_OF"
    SAME_CLAUSE = "SAME_CLAUSE"
    REFERENCES = "REFERENCES"
    AMENDS = "AMENDS"
    DEFINES = "DEFINES"
    USES_DEFINED_TERM = "USES_DEFINED_TERM"


class RelationSupport(str, Enum):
    STRUCTURAL = "STRUCTURAL"
    EXPLICIT_TEXT = "EXPLICIT_TEXT"
    HEURISTIC = "HEURISTIC"


class ModelDisposition(str, Enum):
    CONSISTENT = "CONSISTENT"
    CONFLICTING = "CONFLICTING"
    INCOMPLETE = "INCOMPLETE"
    UNCLEAR = "UNCLEAR"


class VersionPins(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest_version: int
    source_snapshot_digest: str
    tenant_profile_version: int
    policy_version: int
    ocr_run_version: int
    reconstruction_version: int
    extraction_version: int
    index_version: str | None = None
    # Snapshot lineage fields. ``source_snapshot_digest`` remains the
    # compatibility pin used by the reasoning pipeline.
    source_digest: str | None = None
    snapshot_digest: str | None = None


class DossierDocument(BaseModel):
    """Explicit body/annex membership for a multi-document dossier."""

    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    snapshot_id: str = Field(
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    role: Literal["body", "annex"]
    source_digest: str = Field(pattern=r"^[a-fA-F0-9]{64}$")


class DossierManifest(BaseModel):
    """Explicit grouping contract carried alongside canonical v1 snapshots."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["ai1.dossier-manifest.v1"]
    manifest_id: str = Field(
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    dossier_id: str = Field(
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    documents: list[DossierDocument] = Field(min_length=1, max_length=6)

    @model_validator(mode="after")
    def validate_membership(self) -> "DossierManifest":
        document_ids = [item.document_id for item in self.documents]
        snapshot_ids = [item.snapshot_id for item in self.documents]
        if len(document_ids) != len(set(document_ids)):
            raise ValueError("manifest documents must have unique document_id values")
        if len(snapshot_ids) != len(set(snapshot_ids)):
            raise ValueError("manifest documents must have unique snapshot_id values")
        if sum(item.role == "body" for item in self.documents) != 1:
            raise ValueError("manifest must contain exactly one body document")
        return self


class AI2IdpRequest(BaseModel):
    """Canonical v1 request containing a manifest and its snapshots."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["ai2.idp.request.v1"]
    task_id: str = Field(
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    attempt_id: str = Field(
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    manifest: DossierManifest
    snapshots: list[dict[str, Any]] = Field(min_length=1, max_length=6)

    @model_validator(mode="after")
    def validate_snapshot_membership(self) -> "AI2IdpRequest":
        snapshot_ids = [str(item.get("snapshot_id")) for item in self.snapshots]
        if any(item == "None" for item in snapshot_ids):
            raise ValueError("snapshots must contain snapshot_id")
        if len(snapshot_ids) != len(set(snapshot_ids)):
            raise ValueError("snapshots must have unique snapshot_id values")
        expected = {item.snapshot_id for item in self.manifest.documents}
        if set(snapshot_ids) != expected:
            raise ValueError("manifest and snapshots must contain the same snapshot IDs")
        return self


class AuthContext(BaseModel):
    actor_id: str
    tenant_id: str
    dossier_id: str
    acl_revision: int
    permissions: list[str] = Field(default_factory=list)
    member_ids: list[str] = Field(default_factory=list)
    member_documents: dict[str, str] = Field(default_factory=dict)
    lifecycle: LifecycleState = LifecycleState.ACTIVE


class ToolEnvelope(BaseModel):
    auth: AuthContext
    pins: VersionPins


class Citation(BaseModel):
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


class RelationNode(BaseModel):
    node_id: str
    node_kind: str
    source_file_id: str | None = None
    source_role: str | None = None
    page_range: list[int] = Field(default_factory=list)
    page_revision_id: str | None = None
    quality: str | None = None


class RelationEdge(BaseModel):
    edge_id: str
    from_node_id: str
    to_node_id: str
    relation_type: RelationType
    support: RelationSupport
    citations: list[Citation] = Field(default_factory=list)
    review_state: ReviewState = ReviewState.NEEDS_REVIEW
    source_snapshot_digest: str


class RelationGraph(BaseModel):
    graph_id: str
    source_snapshot_digest: str
    nodes: list[RelationNode] = Field(default_factory=list)
    edges: list[RelationEdge] = Field(default_factory=list)
    issues: list["EvidenceIssue"] = Field(default_factory=list)


class ContractPart(BaseModel):
    """A bounded part of one contract snapshot.

    ``BODY`` and ``ANNEX`` are document-context labels only.  They do not
    establish legal precedence or decide which text governs.
    """

    part_id: str
    kind: Literal["BODY", "ANNEX", "UNKNOWN"]
    label: str
    annex_number: str | None = None
    node_ids: list[str] = Field(default_factory=list)
    page_range: list[int] = Field(default_factory=list)
    citation: Citation | None = None
    confidence: float = 0.0


class ContextFinding(BaseModel):
    """Evidence-linked context signal; never a legal winner."""

    finding_id: str
    kind: Literal[
        "PART_LINK",
        "REFERENCE",
        "AMENDMENT_SIGNAL",
        "CONTEXT_CONFLICT",
        "CONTEXT_GAP",
    ]
    relation_type: RelationType | None = None
    subject_key: str | None = None
    source_node_ids: list[str] = Field(default_factory=list)
    reason: str
    review_state: ReviewState = ReviewState.NEEDS_REVIEW
    citations: list[Citation] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContractContext(BaseModel):
    """Machine-readable context inventory for exactly one source document."""

    context_id: str
    scope: Literal["SINGLE_DOCUMENT"] = "SINGLE_DOCUMENT"
    source_file_ids: list[str] = Field(default_factory=list)
    parts: list[ContractPart] = Field(default_factory=list)
    findings: list[ContextFinding] = Field(default_factory=list)


class ContractEvent(BaseModel):
    """A source-grounded contractual event or obligation signal."""

    event_id: str
    event_type: str
    label: str
    subject: str | None = None
    actor_roles: list[str] = Field(default_factory=list)
    trigger: str | None = None
    raw_text: str
    clause_key: str | None = None
    date_signals: list[str] = Field(default_factory=list)
    source_node_id: str
    citation: Citation
    provenance: str = "L0"
    review_state: ReviewState = ReviewState.NEEDS_REVIEW


class SourceFile(BaseModel):
    file_id: str
    filename: str
    role: Literal["body", "annex"] = "body"
    digest: str = ""
    n_pages: int = 0
    # Raw producer metadata is retained when an upstream document role is not
    # part of the legacy body/annex enum (for example OCR-lab's ``contract``).
    document_role: str | None = None
    input_type: str | None = None
    engine: str | None = None
    raw_digest: str | None = None


class PageSnapshot(BaseModel):
    page_revision_id: str
    page_number: int
    quality: Literal["OK", "LOW", "EMPTY", "ENCRYPTED", "FAILED"] = "OK"
    coverage: float = 1.0
    rotation: int = 0
    source_block_ids: list[str] = Field(default_factory=list)
    text: str = ""
    source_file_id: str | None = None
    page_in_file: int | None = None
    table_coverage: TableCoverage = TableCoverage.UNKNOWN
    width: int | None = None
    height: int | None = None
    image_key: str | None = None
    line_texts: dict[str, str] = Field(default_factory=dict)
    line_bboxes: dict[str, list[float]] = Field(default_factory=dict)
    source_hash: str | None = None
    # ``text`` and ``line_texts`` remain the immutable source view used by
    # citation verification.  These fields are derived analysis-only views.
    analysis_text: str | None = None
    analysis_line_texts: dict[str, str] = Field(default_factory=dict)


class TableCell(BaseModel):
    """A sparse AI1 table cell; column position is evidence, not inference."""

    cell_id: str
    row_index: int
    column_index: int
    text: str = ""
    bbox: list[float] = Field(default_factory=list)
    bbox_fragments: list[list[float]] = Field(default_factory=list)
    line_ids: list[str] = Field(default_factory=list)
    row_span: int = 1
    column_span: int = 1
    geometry_provenance: str = "MEASURED"


class StructuralNode(BaseModel):
    node_id: str
    type: Literal["CLAUSE", "FIELD", "TABLE", "SECTION", "UNNUMBERED_BLOCK"]
    raw_label: str
    parent_id: str | None = None
    order: int = 0
    has_children: bool = False
    status: Literal["CONFIRMED", "PARTIAL", "FAILED"] = "CONFIRMED"
    text: str = ""
    page_range: list[int] = Field(default_factory=list)
    page_revision_id: str | None = None
    bbox: list[float] = Field(default_factory=list)
    structured_key: str | None = None
    structured_value: str | None = None
    source_file_id: str | None = None
    page_in_file: int | None = None
    provenance: Literal["AI1", "AI2_REPAIRED"] = "AI1"
    repaired_from_node_id: str | None = None
    structure_level: str = "BLOCK"
    scope_id: str | None = None
    heading_confidence: float | None = None
    parent_confidence: float | None = None
    source_line_ids: list[str] = Field(default_factory=list)
    is_synthetic: bool = False
    source_node_id: str | None = None


class TableSnapshot(BaseModel):
    table_id: str
    title: str = ""
    header: list[str]
    rows: list[list[str | None]]
    continuation: bool = False
    node_id: str | None = None
    page_revision_id: str | None = None
    cell_citations: dict[str, Citation] = Field(default_factory=dict)
    cells: list[TableCell] = Field(default_factory=list)
    header_row_indices: list[int] = Field(default_factory=list)
    source_role: str | None = None
    section_scope: str | None = None
    header_source_table_id: str | None = None
    logical_table_id: str | None = None
    geometry_provenance: str | None = None
    continuity_decision: str | None = None
    continuity_confidence: float | None = None


class TenantProfile(BaseModel):
    version: int
    aliases: dict[str, list[str]] = Field(default_factory=dict)
    field_keys: list[str] = Field(default_factory=list)


class Fact(BaseModel):
    fact_id: str
    raw_value: str
    normalized_value: str | None = None
    subject: str | None = None
    role: str | None = None
    unit: str | None = None
    currency: str | None = None
    vat_basis: str | None = None
    condition: str | None = None
    scope: str | None = None
    validity: str | None = None
    item_key: str | None = None
    tax_basis: str | None = None
    period_start: str | None = None
    source_role: Literal["body", "annex"] | None = None
    citation: Citation
    provenance: str = "L0"
    review_state: ReviewState = ReviewState.NEEDS_REVIEW

    @field_validator("raw_value")
    @classmethod
    def raw_not_empty(cls, v: str) -> str:
        if not v:
            raise ValueError("raw_value must be preserved and non-empty")
        return v


class Candidate(BaseModel):
    candidate_id: str
    left_id: str
    right_id: str
    finding_type: FindingType
    model_disposition: ModelDisposition
    review_state: ReviewState
    evidence_left: list[Citation] = Field(default_factory=list)
    evidence_right: list[Citation] = Field(default_factory=list)
    reason: str = ""
    disposition: Disposition | None = None
    scope: ComparisonScope | None = None
    item_key: str | None = None

    @field_validator("finding_type", mode="before")
    @classmethod
    def no_legal_winner(cls, v: Any) -> Any:
        if isinstance(v, str) and v.upper() in {"LEGAL_WINNER", "WINNER"}:
            raise ValueError("LEGAL_WINNER is forbidden")
        return v


class EvidenceIssue(BaseModel):
    issue_id: str
    missing: str
    reason: str
    citation: Citation | None = None
    review_state: ReviewState = ReviewState.INSUFFICIENT_EVIDENCE


class Chunk(BaseModel):
    chunk_id: str
    parent_node_id: str
    page_range: list[int] = Field(default_factory=list)
    source_block_ids: list[str] = Field(default_factory=list)
    text_span: str
    bbox_fragments: list[list[float]] = Field(default_factory=list)
    breadcrumb: list[str] = Field(default_factory=list)
    continuation: bool = False
    index_version: str | None = None
    review_state: ReviewState = ReviewState.PASS


class HandoffIssue(BaseModel):
    code: str
    message: str
    review_state: ReviewState
    citation: Citation | None = None
    error_id: str | None = None
    stage: str | None = None
    document_id: str | None = None
    location: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    retryable: bool = False


class ValidatedHandoff(BaseModel):
    tenant_id: str
    dossier_id: str
    pins: VersionPins
    pages: list[PageSnapshot]
    nodes: list[StructuralNode]
    tables: list[TableSnapshot]
    profile: TenantProfile
    issues: list[HandoffIssue] = Field(default_factory=list)
    blocked: bool = False


class IndexContribution(BaseModel):
    facts: list[Fact] = Field(default_factory=list)
    chunks: list[Chunk] = Field(default_factory=list)
    candidates: list[Candidate] = Field(default_factory=list)
    evidence_issues: list[EvidenceIssue] = Field(default_factory=list)
    contract_context: ContractContext | None = None
    events: list[ContractEvent] = Field(default_factory=list)
    coverage: dict[str, Any] = Field(default_factory=dict)
    extraction_version: int
    proposed_index_version: str
    publish: Literal["propose"] = "propose"


class JobResult(BaseModel):
    job_id: str
    status: JobStatus
    review_state: ReviewState
    handoff_issues: list[HandoffIssue] = Field(default_factory=list)
    contribution: IndexContribution | None = None
    query_answer: dict[str, Any] | None = None
    error: str | None = None


class ReviewItem(BaseModel):
    review_item_id: str
    kind: str
    status: str = "OPEN"
    review_state: ReviewState = ReviewState.NEEDS_REVIEW
    reason: str
    source_ids: list[str] = Field(default_factory=list)
    citation_ids: list[str] = Field(default_factory=list)
    candidate_id: str | None = None
    proposed_action: str | None = None
    revision: int = 0


class DecimalEncoder:
    """Helpers for table numeric cells — never coerce missing to 0."""

    @staticmethod
    def parse_cell(value: str | None) -> Decimal | None:
        if value is None:
            return None
        text = value.strip().replace(" ", "").replace(",", "")
        if text in {"", "-", "—", "N/A", "n/a"}:
            return None
        return Decimal(text)
