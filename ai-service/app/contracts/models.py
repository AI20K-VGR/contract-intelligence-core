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
    CONTRACT_CONTRACT = "CONTRACT_CONTRACT"
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


class TableProjectionCoverage(BaseModel):
    """Bounded source coverage for a derived table projection."""

    complete: bool
    source_rows: int = Field(ge=0)
    processed_rows: int = Field(ge=0)
    source_cells: int = Field(ge=0)
    processed_cells: int = Field(ge=0)
    page_count: int = Field(ge=0)
    reason: str | None = None


class PaymentMilestoneProjection(BaseModel):
    milestone_id: str
    raw_label: str
    raw_percent: str | None = None
    percent: str | None = None
    event: str | None = None
    trigger: str | None = None
    deadline: str | None = None
    condition: str | None = None
    base: str | None = None
    raw_cells: list[str | None]
    citation: Citation
    cell_citations: dict[str, Citation] = Field(default_factory=dict)


class PaymentScheduleProjection(BaseModel):
    table_id: str
    source_role: Literal["body", "annex"] | None = None
    milestones: list[PaymentMilestoneProjection]
    raw_rows: list[list[str | None]] = Field(default_factory=list)
    total_percent: str | None = None
    review_state: ReviewState
    coverage: TableProjectionCoverage
    issues: list[str] = Field(default_factory=list)


class BoqCheckProjection(BaseModel):
    table_id: str
    source_role: Literal["body", "annex"] | None = None
    currency: str | None = None
    line_count: int = Field(ge=0)
    computed_line_sum: str | None = None
    stated_subtotal: str | None = None
    tax_rate: str | None = None
    tax_amount: str | None = None
    grand_total: str | None = None
    review_state: ReviewState
    coverage: TableProjectionCoverage
    citations: list[Citation] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


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
    contract_type: Literal["SALES", "SUPPLY_SERVICE", "LEASE", "CONSTRUCTION_WORK", "EMPLOYMENT", "NDA"]
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

        from app.pipeline.tenant_aliases import ApprovedAlias, ApprovedAliasSnapshot

        payload = self.model_dump(mode="json", exclude={"digest"})
        expected = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                             separators=(",", ":")).encode()).hexdigest()
        if self.digest != expected:
            raise ValueError("semantic profile digest mismatch")
        if self.activation_state != "ACTIVE" and self.aliases:
            raise ValueError("draft profile must not activate aliases")
        if self.alias_version == 0 and (self.aliases or self.alias_digest is not None):
            raise ValueError("unversioned alias profile")
        if self.alias_version:
            snapshot = ApprovedAliasSnapshot(self.tenant_id, self.alias_version,
                tuple(ApprovedAlias(**a.model_dump()) for a in self.aliases))
            if snapshot.digest != self.alias_digest:
                raise ValueError("alias digest mismatch")
        return self


class SemanticCitation(Citation):
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
        if self.state == "GROUNDED" and (not self.value or not self.value.strip() or not self.evidence):
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
        if self.method == "TENANT_ALIAS" and (not self.alias_digest or not self.alias_version or not self.alias_proposal_ids):
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
        from app.contracts.clause_frames import SLOT_NAMES

        if set(self.slots) - SLOT_NAMES:
            raise ValueError("unknown semantic slot")
        for evidence in [*self.evidence, *(e for s in self.slots.values() for e in s.evidence)]:
            if (evidence.document_id, evidence.snapshot_id) != (self.document_id, self.snapshot_id):
                raise ValueError("semantic evidence scope mismatch")
        return self


class SemanticPair(SemanticClosedModel):
    pair_id: str
    left_id: str
    right_id: str
    disposition: Literal["DUPLICATE", "COMPARABLE_DIFFERENCE", "NOT_COMPARABLE", "GENERAL_VS_SPECIFIC",
                         "SCOPE_DIFFERS", "NEEDS_REVIEW_UNPARSED", "NEEDS_REVIEW_BACKOFF", "GRADUATED",
                         "CUMULATIVE", "CONFLICT_CANDIDATE"]
    reason: str
    left_evidence: list[SemanticEvidence] = Field(min_length=1)
    right_evidence: list[SemanticEvidence] = Field(min_length=1)
    review_state: Literal["NEEDS_REVIEW"] = "NEEDS_REVIEW"
    method: Literal["CLOSED_SYMBOL", "TENANT_ALIAS"]
    candidate_sources: list[str]


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
        if self.proposed_value is not None and (self.relation != "AMENDS" or self.date_role != "EFFECTIVE"
                or self.date_value is None or self.acceptance is None or self.acceptance.state != "GROUNDED"
                or self.acceptance.value != "ACCEPTED" or self.target_id is None
                or self.proposed_value.state != "GROUNDED"):
            raise ValueError("unproven amendment proposal")
        if self.proposed_value is not None:
            import unicodedata
            def folded(value):
                return "".join(c for c in unicodedata.normalize("NFD", value.casefold()).replace("đ", "d") if unicodedata.category(c) != "Mn")
            if not any(folded(e.raw).startswith("cac ben dong y sua doi ") for e in self.acceptance.evidence):
                raise ValueError("affirmative amendment acceptance evidence required")
            if not any(self.date_value in e.raw and "co hieu luc tu" in folded(e.raw) for e in self.evidence):
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
                        type(v) is not int or v < 0 for v in values.values()):
                    raise ValueError("invalid semantic coverage counters")
                if any(values[name] > values["attempted"] for name in ("covered", "review", "missing")):
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
        if len(frames) != len(self.frames) or len(set(self.rows)) != len(self.rows) or set(self.rows) != set(frames):
            raise ValueError("semantic row/frame identity mismatch")
        if any(f.dossier_id != self.dossier_id for f in self.frames):
            raise ValueError("semantic dossier mismatch")
        if any(f.key.method == "TENANT_ALIAS" and (f.key.alias_version != self.alias_version
                or f.key.alias_digest != self.alias_digest) for f in self.frames):
            raise ValueError("semantic key alias pin mismatch")
        for pair in self.pairs:
            if pair.left_id not in frames or pair.right_id not in frames or pair.left_id == pair.right_id:
                raise ValueError("semantic pair target mismatch")
            if pair.left_evidence != frames[pair.left_id].evidence or pair.right_evidence != frames[pair.right_id].evidence:
                raise ValueError("semantic pair evidence mismatch")
            if pair.disposition == "DUPLICATE":
                left, right = frames[pair.left_id], frames[pair.right_id]
                required = {"actor", "action", "modality_negation", "object_scope", "beneficiary",
                            "condition", "exception", "temporal_trigger", "deadline"}
                if left.family == "PARAMETER" and "parameter" in left.slots:
                    required.difference_update({"actor", "action", "modality_negation", "beneficiary"})
                    required.add("parameter")
                elif left.family == "DEFINITION":
                    required = {"parameter", "definition", "object_scope", "condition", "exception", "temporal_trigger"}
                if left.family == "REMEDY":
                    required.add("qualifier")
                if left.family in {"REMEDY", "PARAMETER"} or any(
                        f.slots.get("amount") and f.slots["amount"].value is not None or
                        f.slots.get("action") and f.slots["action"].value in {"PAY", "COMPENSATE", "PENALTY"}
                        for f in (left, right)):
                    required.update({"amount", "unit", "currency", "base", "period"})
                required.update(name for f in (left, right) for name, slot in f.slots.items()
                                if slot.state in {"GROUNDED", "ABSENT"})
                if (left.key.certainty != "DEFINITE" or right.key.certainty != "DEFINITE" or left.key.key != right.key.key
                        or left.family != right.family or left.profile != right.profile
                        or any(name not in f.slots or f.slots[name].state in {"UNKNOWN", "UNSUPPORTED"}
                               for f in (left, right) for name in required)
                        or any(e.citation.validation_status != "VALID" for f in (left, right) for e in f.evidence)):
                    raise ValueError("DUPLICATE requires assessed grounded evidence")
                key_fields = {"qualifier"} if left.family == "REMEDY" else set()
                if left.family != "DEFINITION" and not (left.family == "PARAMETER" and "parameter" in left.slots):
                    key_fields.add("action")
                for name in required - key_fields:
                    a, b = left.slots[name], right.slots[name]
                    values = (Decimal(a.value), Decimal(b.value)) if a.value_type == b.value_type == "DECIMAL" else (a.value, b.value)
                    if a.state != b.state or a.value_type != b.value_type or values[0] != values[1]:
                        raise ValueError("DUPLICATE cannot hide assessed slot differences")
        if len({p.pair_id for p in self.pairs}) != len(self.pairs):
            raise ValueError("duplicate semantic pair")
        for edge in self.timeline:
            if edge.source_id not in frames:
                raise ValueError("semantic timeline source missing")
            allowed = {(frames[x].document_id, frames[x].snapshot_id) for x in (edge.source_id, edge.target_id) if x in frames}
            evidence = [*edge.evidence, *(edge.acceptance.evidence if edge.acceptance else []),
                        *(edge.proposed_value.evidence if edge.proposed_value else [])]
            if any((e.document_id, e.snapshot_id) not in allowed for e in evidence):
                raise ValueError("semantic timeline evidence scope mismatch")
            if edge.target_id not in frames and "missing_target" not in edge.reasons:
                raise ValueError("missing timeline target must remain visible")
            if edge.proposed_value and any(e.citation.validation_status != "VALID" for e in evidence):
                raise ValueError("amendment proposal citations must verify")
        if len({e.edge_id for e in self.timeline}) != len(self.timeline):
            raise ValueError("duplicate timeline edge")
        if self.coverage.frames != len(frames):
            raise ValueError("semantic frame coverage mismatch")
        return self


class IndexContribution(BaseModel):
    facts: list[Fact] = Field(default_factory=list)
    chunks: list[Chunk] = Field(default_factory=list)
    candidates: list[Candidate] = Field(default_factory=list)
    evidence_issues: list[EvidenceIssue] = Field(default_factory=list)
    contract_context: ContractContext | None = None
    events: list[ContractEvent] = Field(default_factory=list)
    coverage: dict[str, Any] = Field(default_factory=dict)
    payment_schedules: list[PaymentScheduleProjection] = Field(default_factory=list)
    boq_checks: list[BoqCheckProjection] = Field(default_factory=list)
    semantic_extension: SemanticExtension | None = None
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
