"""Boundary adapter for the official ``ai1.snapshot.v1`` handoff.

The OCR edge-case catalog is guidance, not a second wire contract.  This
module therefore accepts the official snapshot shape and keeps uncertain or
missing evidence explicit while adapting it to the current AI2 record model.
"""

from __future__ import annotations

import re
import hashlib
import json
import unicodedata
from dataclasses import dataclass
from typing import Any, Mapping

from app.contracts.models import (
    AI2IdpRequest,
    AuthContext,
    Citation,
    HandoffIssue,
    Fact,
    LifecycleState,
    PageSnapshot,
    ReviewState,
    ReviewItem,
    SourceFile,
    StructuralNode,
    TableCoverage,
    TableCell,
    TableSnapshot,
    TenantProfile,
    ToolEnvelope,
    VersionPins,
)
from app.contracts.errors import ContractValidationError
from app.contracts.wire import BeAi2ProcessingRequest
from app.contracts.schema_validation import validate_contract
from app.pipeline.citations import CitationResolver, quote_digest
from app.tools.store import DossierRecord


class SnapshotContractError(ValueError):
    """Raised when an AI1 snapshot cannot be safely adapted."""

    def __init__(self, message: str, *, code: str = "SNAPSHOT_CONTRACT_INVALID") -> None:
        super().__init__(message)
        self.code = code


@dataclass
class SnapshotAdapterResult:
    record: DossierRecord
    envelope: ToolEnvelope
    meta: dict[str, Any]


def adapt_be_ai2_processing_request(
    payload: Mapping[str, Any],
    *,
    tenant_id: str = "tenant_a",
    actor_id: str = "user_001",
    profile: TenantProfile | None = None,
    acl_revision: int = 1,
) -> tuple[BeAi2ProcessingRequest, SnapshotAdapterResult]:
    """Validate and adapt the stable Backend → AI2 processing wire request.

    The wire request is deliberately translated into the existing canonical
    dossier adapter so the worker can keep using the current AI2 pipeline
    while the public contract evolves independently from internal models.
    """

    _require_mapping(payload, "Backend → AI2 processing request")
    try:
        validate_contract(
            payload,
            "be.ai2.processing.request.v1.schema.json",
            error_code="PROCESSING_REQUEST_SCHEMA_INVALID",
        )
        request = BeAi2ProcessingRequest.model_validate(payload)
    except ContractValidationError as exc:
        raise SnapshotContractError(str(exc), code=exc.code) from exc
    except Exception as exc:
        if "[SEMANTIC]" in str(exc):
            raise SnapshotContractError(
                f"invalid Backend → AI2 processing request: {exc}",
                code="PROCESSING_REQUEST_SEMANTIC_INVALID",
            ) from exc
        raise SnapshotContractError(
            f"invalid Backend → AI2 processing request: {exc}",
            code="PROCESSING_REQUEST_CONTRACT_INVALID",
        ) from exc

    manifest = {
        "schema_version": "ai1.dossier-manifest.v1",
        "manifest_id": f"manifest:{request.request_id}",
        "dossier_id": request.dossier_id,
        "documents": [
            {
                "document_id": item.document_id,
                "snapshot_id": item.snapshot_id,
                "role": item.role,
                "source_digest": item.source_digest,
            }
            for item in request.dossier_members
        ],
    }
    compatibility_payload = {
        "schema_version": "ai2.idp.request.v1",
        "task_id": request.task_id,
        "attempt_id": f"attempt:{request.attempt}",
        "manifest": manifest,
        "snapshots": request.snapshots,
    }
    result = adapt_ai2_request(
        compatibility_payload,
        tenant_id=tenant_id,
        actor_id=actor_id,
        profile=profile,
        acl_revision=acl_revision,
        member_ids=[item.member_id for item in request.dossier_members],
        member_documents={item.member_id: item.document_id for item in request.dossier_members},
    )
    result.record.egress_approved = request.policy_flags.egress_allowed
    result.meta.update(
        {
            "source": "be.ai2.processing.request.v1",
            "request_id": request.request_id,
            "idempotency_key": request.idempotency_key,
            "attempt": request.attempt,
            "role_relation_map": [item.model_dump() for item in request.role_relation_map],
            "policy_flags": request.policy_flags.model_dump(),
        }
    )
    return request, result


def adapt_ai2_request(
    payload: Mapping[str, Any],
    *,
    tenant_id: str = "tenant_a",
    actor_id: str = "user_001",
    profile: TenantProfile | None = None,
    acl_revision: int = 1,
    member_ids: list[str] | None = None,
    member_documents: dict[str, str] | None = None,
) -> SnapshotAdapterResult:
    """Adapt the official AI2 request envelope.

    This is the only adapter for the canonical path. It requires one
    ``ai1.dossier-manifest.v1`` plus exactly one ``ai1.snapshot.v1`` per
    manifest document. The older ``adapt_ai1_input`` function remains a
    compatibility adapter and is intentionally not called here.
    """

    _require_mapping(payload, "ai2 request")
    try:
        validate_contract(payload, "ai2.idp.request.v1.schema.json", error_code="REQUEST_SCHEMA_INVALID")
        request = AI2IdpRequest.model_validate(payload)
    except ContractValidationError as exc:
        raise SnapshotContractError(str(exc), code=exc.code) from exc
    except Exception as exc:
        raise SnapshotContractError(f"invalid ai2 request: {exc}", code="REQUEST_CONTRACT_INVALID") from exc

    snapshots = {str(item["snapshot_id"]): item for item in request.snapshots}
    results: list[SnapshotAdapterResult] = []
    manifest_docs = {item.snapshot_id: item for item in request.manifest.documents}
    page_revision_ids: set[str] = set()
    for snapshot_id, document in manifest_docs.items():
        snapshot = snapshots.get(snapshot_id)
        if snapshot is None:
            raise SnapshotContractError(
                f"manifest references missing snapshot {snapshot_id}",
                code="REQUEST_MEMBERSHIP_INVALID",
            )
        if snapshot.get("dossier_id") != request.manifest.dossier_id:
            raise SnapshotContractError(
                f"snapshot {snapshot_id} dossier_id does not match manifest",
                code="REQUEST_MEMBERSHIP_INVALID",
            )
        if snapshot.get("document_id") != document.document_id:
            raise SnapshotContractError(
                f"snapshot {snapshot_id} document_id does not match manifest",
                code="REQUEST_MEMBERSHIP_INVALID",
            )
        if snapshot.get("source_digest") != document.source_digest:
            raise SnapshotContractError(
                f"snapshot {snapshot_id} source_digest does not match manifest",
                code="REQUEST_MEMBERSHIP_INVALID",
            )
        for page in snapshot.get("pages", []):
            page_revision_id = str(page.get("page_revision_id"))
            if page_revision_id in page_revision_ids:
                raise SnapshotContractError(
                    f"duplicate page_revision_id across request: {page_revision_id}",
                    code="REQUEST_SEMANTIC_INVALID",
                )
            page_revision_ids.add(page_revision_id)
        result = adapt_snapshot_v1(
            snapshot,
            tenant_id=tenant_id,
            actor_id=actor_id,
            profile=profile,
            acl_revision=acl_revision,
        )
        result.record.source_files[0].role = document.role
        result.record.source_files[0].digest = document.source_digest
        results.append(result)

    if not results:
        raise SnapshotContractError("request must contain at least one snapshot", code="REQUEST_CONTRACT_INVALID")

    first = results[0]
    record = first.record
    request_digest = _canonical_digest(payload)
    record.dossier_id = request.manifest.dossier_id
    record.pins.source_snapshot_digest = request_digest
    record.pins.snapshot_digest = request_digest
    record.source_files = [source for result in results for source in result.record.source_files]
    record.pages = [page for result in results for page in result.record.pages]
    record.nodes = [node for result in results for node in result.record.nodes]
    record.tables = [table for result in results for table in result.record.tables]
    record.handoff_issues = [issue for result in results for issue in result.record.handoff_issues]
    record.case_id = "AI2-IDP-REQUEST"
    record.permissions_by_actor = {actor_id: ["READ_CONTENT"]}
    snapshot_statuses = {str(item.get("status")) for item in snapshots.values()}
    request_status = (
        "FAILED"
        if snapshot_statuses and snapshot_statuses == {"FAILED"}
        else "PARTIAL"
        if snapshot_statuses.intersection({"PARTIAL", "FAILED"})
        else "SUCCESS"
    )
    envelope = ToolEnvelope(
        auth=AuthContext(
            actor_id=actor_id,
            tenant_id=tenant_id,
            dossier_id=request.manifest.dossier_id,
            acl_revision=acl_revision,
            permissions=["READ_CONTENT"],
            member_ids=member_ids or [],
            member_documents=member_documents or {},
        ),
        pins=record.pins.model_copy(),
    )
    return SnapshotAdapterResult(
        record=record,
        envelope=envelope,
        meta={
            "source": "ai2.idp.request.v1",
            "adapter": "canonical-v1",
            "task_id": request.task_id,
            "attempt_id": request.attempt_id,
            "manifest_id": request.manifest.manifest_id,
            "dossier_id": request.manifest.dossier_id,
            "snapshot_ids": list(snapshots),
            "document_roles": {item.document_id: item.role for item in request.manifest.documents},
            "status": request_status,
            "n_pages": len(record.pages),
            "n_nodes": len(record.nodes),
            "n_tables": len(record.tables),
            "n_handoff_issues": len(record.handoff_issues),
        },
    )


def adapt_snapshot_v1(
    snapshot: Mapping[str, Any],
    *,
    tenant_id: str = "tenant_a",
    actor_id: str = "user_001",
    profile: TenantProfile | None = None,
    acl_revision: int = 1,
) -> SnapshotAdapterResult:
    """Strictly validate and adapt one canonical ``ai1.snapshot.v1``."""

    _require_mapping(snapshot, "ai1 snapshot v1")
    try:
        validate_contract(snapshot, "ai1.snapshot.v1.schema.json", error_code="SNAPSHOT_SCHEMA_INVALID")
    except ContractValidationError as exc:
        raise SnapshotContractError(str(exc), code=exc.code) from exc
    if snapshot.get("schema_version") != "ai1.snapshot.v1":
        raise SnapshotContractError(
            "canonical adapter accepts ai1.snapshot.v1 only",
            code="UNSUPPORTED_SNAPSHOT_VERSION",
        )
    _validate_snapshot_semantics(snapshot)
    return adapt_snapshot(
        snapshot,
        tenant_id=tenant_id,
        actor_id=actor_id,
        profile=profile,
        acl_revision=acl_revision,
    )


REQUIRED_ROOT = (
    "schema_version",
    "snapshot_id",
    "dossier_id",
    "document_id",
    "run_id",
    "source_digest",
    "execution",
    "producer",
    "status",
    "pages",
)

SUPPORTED_SNAPSHOT_VERSIONS = {
    "ai1.snapshot.v1",
}


def adapt_ai1_input(
    payload: Mapping[str, Any],
    *,
    tenant_id: str = "tenant_a",
    actor_id: str = "user_001",
    profile: TenantProfile | None = None,
    acl_revision: int = 1,
    dossier_id: str | None = None,
    scope_id: str | None = None,
) -> SnapshotAdapterResult:
    """Dispatch the supported AI1 handoff shapes at the trust boundary.

    The edge-case catalog is deliberately not accepted as document evidence.
    Legacy page-text JSON is accepted only as degraded, text-only evidence.
    """

    _require_mapping(payload, "payload")
    machine = payload.get("machine")
    if isinstance(machine, Mapping) and str(machine.get("schema_version")) == "0.1":
        return adapt_ai1_result_v01(
            payload,
            tenant_id=tenant_id,
            actor_id=actor_id,
            profile=profile,
            acl_revision=acl_revision,
            dossier_id=dossier_id,
            scope_id=scope_id,
        )
    version = payload.get("schema_version")
    if version in SUPPORTED_SNAPSHOT_VERSIONS:
        from app.pipeline.ai1_ocr_lab_adapter import adapt_ocr_lab_snapshot, is_ocr_lab_snapshot

        if is_ocr_lab_snapshot(payload):
            return adapt_ocr_lab_snapshot(
                payload,
                tenant_id=tenant_id,
                actor_id=actor_id,
                profile=profile,
                acl_revision=acl_revision,
                scope_id=scope_id,
            )
        _validate_snapshot_compatibility_semantics(payload)
        return adapt_snapshot(
            payload,
            tenant_id=tenant_id,
            actor_id=actor_id,
            profile=profile,
            acl_revision=acl_revision,
        )
    if version == "ai2.ocr_edge_cases.v1" or isinstance(payload.get("cases"), list):
        raise SnapshotContractError(
            "ai2.ocr_edge_cases.v1 is a policy/test catalog, not an AI1 document snapshot",
            code="UNSUPPORTED_ARTIFACT_KIND",
        )
    if isinstance(payload.get("pages"), list) and ("full_text" in payload or "page_count" in payload):
        return adapt_legacy_ocr(
            payload,
            tenant_id=tenant_id,
            actor_id=actor_id,
            profile=profile,
            acl_revision=acl_revision,
        )
    raise SnapshotContractError(
        "payload is neither ai1.snapshot.v1 nor supported legacy OCR JSON",
        code="UNSUPPORTED_SNAPSHOT_VERSION" if isinstance(version, str) and version.startswith("ai1.snapshot.") else "UNSUPPORTED_ARTIFACT_KIND",
    )


def adapt_ai1_result_v01(
    payload: Mapping[str, Any],
    *,
    tenant_id: str = "tenant_a",
    actor_id: str = "user_001",
    profile: TenantProfile | None = None,
    acl_revision: int = 1,
    dossier_id: str | None = None,
    scope_id: str | None = None,
) -> SnapshotAdapterResult:
    """Adapt the result envelope emitted by the current AI1 service.

    This is intentionally separate from ``ai1.snapshot.v1``.  The result
    envelope contains already extracted clauses, facts, tables and citations;
    treating it as a snapshot loses those objects and makes AI2 rebuild the
    wrong contract tree.
    """

    _require_mapping(payload, "ai1 result")
    machine = payload.get("machine")
    effective = payload.get("effective")
    if not isinstance(machine, Mapping):
        raise SnapshotContractError("ai1.result.v0.1 requires machine", code="RESULT_CONTRACT_INVALID")
    if not isinstance(effective, Mapping):
        effective = machine
    if str(machine.get("schema_version")) != "0.1" or str(effective.get("schema_version")) != "0.1":
        raise SnapshotContractError("ai1 result schema_version must be 0.1", code="RESULT_CONTRACT_INVALID")
    pages_in = effective.get("pages")
    if not isinstance(pages_in, list) or not pages_in:
        raise SnapshotContractError("ai1 result pages must be a non-empty array", code="RESULT_CONTRACT_INVALID")
    for name, key in (("documents", "document_id"), ("clauses", "id"), ("tables", "id"), ("citations", "id"), ("facts", "id")):
        values = effective.get(name) or []
        if not isinstance(values, list) or any(not isinstance(item, Mapping) or not item.get(key) for item in values):
            raise SnapshotContractError(f"invalid {name} inventory", code="RESULT_SEMANTIC_INVALID")
        ids = [str(item[key]) for item in values]
        if len(ids) != len(set(ids)):
            raise SnapshotContractError(f"duplicate {name} ID", code="RESULT_SEMANTIC_INVALID")
    for raw_page in pages_in:
        if not isinstance(raw_page, Mapping):
            raise SnapshotContractError("invalid page", code="RESULT_SEMANTIC_INVALID")
        line_ids = [line.get("id") for line in raw_page.get("lines", []) if isinstance(line, Mapping)]
        if len(line_ids) != len(set(line_ids)) or any(not value for value in line_ids):
            raise SnapshotContractError("invalid/duplicate line ID", code="RESULT_SEMANTIC_INVALID")

    result_hash = str(payload.get("effective_result_hash") or payload.get("result_hash") or "")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", result_hash):
        result_hash = _legacy_digest(effective)
    content_digest = _legacy_digest(effective)
    source_digest = f"sha256:{content_digest}"
    source_dossier = str(machine.get("dossier_id") or "ai1-result")
    effective_dossier = dossier_id or f"ai1-result:{content_digest[:24]}"
    effective_scope = scope_id or effective_dossier
    profile = profile or TenantProfile(version=1)
    pins = VersionPins(
        manifest_version=1,
        source_snapshot_digest=source_digest,
        tenant_profile_version=profile.version,
        policy_version=1,
        ocr_run_version=1,
        reconstruction_version=1,
        extraction_version=1,
    )

    documents = [item for item in (effective.get("documents") or []) if isinstance(item, Mapping)]
    doc_by_id: dict[str, Mapping[str, Any]] = {
        str(item.get("document_id")): item for item in documents if item.get("document_id")
    }
    page_by_key: dict[tuple[str, int], PageSnapshot] = {}
    source_files: list[SourceFile] = []
    for item in documents:
        file_id = str(item.get("document_id"))
        role = _result_role(item.get("role"))
        source_files.append(
            SourceFile(
                file_id=file_id,
                filename=str(item.get("storage_key") or f"ai1:{file_id}.pdf"),
                role=role,
                digest=_hash_digest(item.get("sha256")),
                n_pages=int(item.get("page_count") or 0),
            )
        )
    if not source_files:
        inferred_ids = {str(p.get("document_id")) for p in pages_in if isinstance(p, Mapping) and p.get("document_id")}
        for file_id in sorted(inferred_ids):
            source_files.append(SourceFile(file_id=file_id, filename=f"ai1:{file_id}.pdf", digest="", n_pages=0))

    issues: list[HandoffIssue] = []
    raw_citations = {
        str(item.get("id")): item
        for item in (effective.get("citations") or [])
        if isinstance(item, Mapping) and item.get("id")
    }
    clauses = [item for item in (effective.get("clauses") or []) if isinstance(item, Mapping)]
    tables_in = [item for item in (effective.get("tables") or []) if isinstance(item, Mapping)]
    facts_in = [item for item in (effective.get("facts") or []) if isinstance(item, Mapping)]
    known_node_ids = {str(item.get("id")) for item in clauses if item.get("id")}

    for raw_page in pages_in:
        if not isinstance(raw_page, Mapping):
            raise SnapshotContractError("ai1 result page must be an object", code="RESULT_SEMANTIC_INVALID")
        page = _adapt_result_page(raw_page, doc_by_id, effective_scope, issues)
        page.page_revision_id += f":{content_digest}"
        if (page.source_file_id or "", page.page_number) in page_by_key:
            raise SnapshotContractError("duplicate document/page", code="RESULT_SEMANTIC_INVALID")
        page_by_key[(page.source_file_id or "", page.page_number)] = page

    citation_index: dict[str, Citation] = {}
    nodes: list[StructuralNode] = []
    tables: list[TableSnapshot] = []

    for raw_clause in clauses:
        node_id = str(raw_clause.get("id") or "")
        if not node_id:
            issues.append(_result_issue("CLAUSE_ID_MISSING", "AI1 clause has no id"))
            continue
        refs = [str(x) for x in (raw_clause.get("citation_ids") or [])]
        cite = _result_citation_for_refs(
            refs,
            raw_citations,
            node_id=node_id,
            page_by_key=page_by_key,
            doc_by_id=doc_by_id,
            citation_index=citation_index,
            issues=issues,
        )
        label = str(raw_clause.get("label") or node_id)
        text = label
        if cite and cite.text_span and cite.text_span not in text:
            text = f"{label}\n{cite.text_span}"
        page_number = cite.page if cite else None
        node_type = "UNNUMBERED_BLOCK" if str(raw_clause.get("type", "")).lower() == "fragment" else "CLAUSE"
        nodes.append(
            StructuralNode(
                node_id=node_id,
                type=node_type,
                raw_label=label,
                parent_id=str(raw_clause.get("parent_id")) if raw_clause.get("parent_id") in known_node_ids else None,
                order=len(nodes),
                status="CONFIRMED" if cite and cite.validation_status == "VALID" else "PARTIAL",
                text=text,
                page_range=[page_number] if page_number else [],
                page_revision_id=cite.page_revision_id if cite else None,
                bbox=cite.bbox if cite else [],
                source_file_id=cite.source_file_id if cite else str(raw_clause.get("document_id") or "") or None,
                page_in_file=page_number,
                structure_level="ARTICLE" if str(raw_clause.get("type", "")).lower() == "article" else "BLOCK",
                scope_id=effective_scope,
                source_line_ids=cite.line_ids if cite else [],
            )
        )

    if not clauses:
        issues.append(
            HandoffIssue(
                code="AI1_CLAUSES_ABSENT",
                message="AI1 result has no clauses; AI2 uses degraded page/block reconstruction",
                review_state=ReviewState.NEEDS_REVIEW,
            )
        )
        for page in sorted(page_by_key.values(), key=lambda item: (item.source_file_id or "", item.page_number)):
            if not page.text.strip():
                continue
            node_id = f"ai2-page-block:{page.source_file_id}:{page.page_number}"
            nodes.append(
                StructuralNode(
                    node_id=node_id,
                    type="UNNUMBERED_BLOCK",
                    raw_label=f"Trang {page.page_number}",
                    order=len(nodes),
                    status="PARTIAL",
                    text=page.text,
                    page_range=[page.page_number],
                    page_revision_id=page.page_revision_id,
                    source_file_id=page.source_file_id,
                    page_in_file=page.page_number,
                    structure_level="BLOCK",
                    scope_id=effective_scope,
                    source_line_ids=list(page.line_texts),
                )
            )

    for raw_table in tables_in:
        table, table_node, table_citations, table_issues = _adapt_result_table(
            raw_table, page_by_key=page_by_key, doc_by_id=doc_by_id, scope_id=effective_scope
        )
        if table is not None:
            tables.append(table)
        if table_node is not None:
            nodes.append(table_node)
        citation_index.update({cite.citation_id: cite for cite in table_citations.values()})
        issues.extend(table_issues)

    facts: list[Fact] = []
    for raw_fact in facts_in:
        fact, field_node, fact_citations, fact_issues = _adapt_result_fact(
            raw_fact,
            raw_citations=raw_citations,
            page_by_key=page_by_key,
            doc_by_id=doc_by_id,
            citation_index=citation_index,
            scope_id=effective_scope,
        )
        issues.extend(fact_issues)
        citation_index.update(fact_citations)
        if fact is not None:
            facts.append(fact)
        if field_node is not None:
            nodes.append(field_node)

    derived_facts, derived_nodes, derived_citations, derived_issues = _derive_result_facts(
        pages=list(page_by_key.values()),
        raw_citations=raw_citations,
        existing_facts=facts,
        citation_index=citation_index,
        scope_id=effective_scope,
    )
    input_facts = [fact.model_copy(deep=True) for fact in facts]
    facts.extend(derived_facts)
    nodes.extend(derived_nodes)
    citation_index.update(derived_citations)
    issues.extend(derived_issues)

    # Keep the complete AI1 citation inventory, not only citations currently
    # referenced by a clause/fact. This makes one-click verification useful
    # for the UI and prevents unreferenced source evidence from disappearing.
    for citation_id in raw_citations:
        if citation_id not in citation_index:
            _result_citation_for_refs(
                [citation_id],
                raw_citations,
                node_id=f"source-citation:{citation_id}",
                page_by_key=page_by_key,
                doc_by_id=doc_by_id,
                citation_index=citation_index,
                issues=[],
            )

    review = payload.get("review") if isinstance(payload.get("review"), Mapping) else {}
    if (str(payload.get("status", "")).lower() == "pending_review"
            or bool(machine.get("review_required")) or bool(effective.get("review_required"))
            or bool(review.get("blocked")) or bool(review.get("unresolved")) or bool(review.get("stale"))):
        issues.append(
            HandoffIssue(
                code="AI1_PENDING_REVIEW",
                message="AI1 result is pending review; deterministic AI2 may run but authoritative publish is gated",
                review_state=ReviewState.NEEDS_REVIEW,
            )
        )
    coverage = effective.get("coverage") if isinstance(effective.get("coverage"), Mapping) else {}
    if coverage.get("expected_pages") not in (None, len(page_by_key)):
        issues.append(_result_issue("AI1_PAGE_COUNT_MISMATCH", "expected page count differs from received unique pages"))
    if not bool(coverage.get("coverage_complete", False)):
        issues.append(
            HandoffIssue(
                code="AI1_COVERAGE_INCOMPLETE",
                message="AI1 coverage is incomplete",
                review_state=ReviewState.NEEDS_REVIEW,
            )
        )

    record = DossierRecord(
        tenant_id=tenant_id,
        dossier_id=effective_dossier,
        lifecycle=LifecycleState.ACTIVE,
        pins=pins,
        pages=sorted(page_by_key.values(), key=lambda item: (item.source_file_id or "", item.page_number)),
        nodes=nodes,
        tables=tables,
        profile=profile,
        acl_revision=acl_revision,
        permissions_by_actor={actor_id: ["READ_CONTENT"]},
        source_files=source_files,
        facts=facts,
        input_facts=input_facts,
        case_id="AI1-RESULT-V0.1",
        handoff_issues=issues,
        citation_index=citation_index,
        review_items=_review_items_from_issues(issues),
    )
    from app.pipeline.result_structure import enrich_result_structure
    enrich_result_structure(record)
    envelope = ToolEnvelope(
        auth=AuthContext(
            actor_id=actor_id,
            tenant_id=tenant_id,
            dossier_id=effective_dossier,
            acl_revision=acl_revision,
            permissions=["READ_CONTENT"],
        ),
        pins=pins.model_copy(),
    )
    return SnapshotAdapterResult(
        record=record,
        envelope=envelope,
        meta={
            "source": "ai1.result.v0.1",
            "adapter": "legacy-result-v0.1",
            "run_id": str(machine.get("run_id") or ""),
            "source_dossier_id": source_dossier,
            "dossier_id": effective_dossier,
            "scope_id": effective_scope,
            "result_hash": result_hash,
            "content_digest": content_digest,
            "status": str(payload.get("status") or "unknown"),
            "review_required": bool(machine.get("review_required")) or bool(issues),
            "n_pages": len(record.pages),
            "n_nodes": len(record.nodes),
            "n_clauses": len(clauses),
            "n_tables": len(record.tables),
            "n_facts": len(record.facts),
            "n_citations": len(citation_index),
            "n_handoff_issues": len(issues),
            "table_coverage": _result_table_coverage(record.pages, record.tables, coverage),
            "capabilities": {
                "text": bool(record.pages),
                "line_geometry": any(bool(p.line_bboxes) for p in record.pages),
                "word_geometry": any(bool(line.get("words")) for page in pages_in if isinstance(page, Mapping) for line in (page.get("lines") or []) if isinstance(line, Mapping)),
                "table_structure": bool(record.tables),
                "table_geometry": any(bool(cell.bbox or cell.bbox_fragments) for table in record.tables for cell in table.cells),
            },
        },
    )


def adapt_snapshot(
    snapshot: Mapping[str, Any],
    *,
    tenant_id: str = "tenant_a",
    actor_id: str = "user_001",
    profile: TenantProfile | None = None,
    acl_revision: int = 1,
) -> SnapshotAdapterResult:
    """Normalize a snapshot-shaped workspace input without fabricating evidence.

    The canonical v1 snapshot has no required structural ``blocks`` field. AI2 therefore
    exposes line-level clause/unnumbered nodes with conservative status and
    never claims that a missing table or bbox was reconstructed. Strict schema and
    semantic validation belongs to ``adapt_snapshot_v1`` on the canonical processing
    lane; this lower-level adapter also supports degraded workspace fixtures.
    """

    _require_mapping(snapshot, "snapshot")
    missing = [name for name in REQUIRED_ROOT if name not in snapshot]
    if missing:
        raise SnapshotContractError(f"missing required snapshot fields: {', '.join(missing)}")
    schema_version = snapshot.get("schema_version")
    if schema_version not in SUPPORTED_SNAPSHOT_VERSIONS:
        raise SnapshotContractError(
            "schema_version must be ai1.snapshot.v1"
        )
    pages_in = snapshot.get("pages")
    if not isinstance(pages_in, list) or not pages_in:
        raise SnapshotContractError("pages must be a non-empty array")
    if snapshot.get("status") not in {"SUCCESS", "PARTIAL", "FAILED"}:
        raise SnapshotContractError("snapshot.status must be SUCCESS, PARTIAL, or FAILED")
    profile = profile or TenantProfile(version=1)
    snapshot_id = str(snapshot["snapshot_id"])
    dossier_id = str(snapshot["dossier_id"])
    digest = _snapshot_digest(snapshot["source_digest"])
    pins = VersionPins(
        manifest_version=1,
        source_snapshot_digest=digest,
        tenant_profile_version=profile.version,
        policy_version=1,
        ocr_run_version=1,
        reconstruction_version=1,
        extraction_version=1,
    )
    source_file = SourceFile(
        file_id=str(snapshot["document_id"]),
        filename=f"ai1:{snapshot['document_id']}",
        role="body",
        digest=digest,
        n_pages=len(pages_in),
    )
    pages: list[PageSnapshot] = []
    nodes: list[StructuralNode] = []
    tables: list[TableSnapshot] = []
    issues: list[HandoffIssue] = []

    for page_data in pages_in:
        if not isinstance(page_data, Mapping):
            raise SnapshotContractError("each page must be an object")
        page, page_nodes, page_tables, page_issues = _adapt_page(
            page_data,
            snapshot_id=snapshot_id,
            source_file_id=source_file.file_id,
            source_hash=str(snapshot["source_digest"]),
        )
        pages.append(page)
        nodes.extend(page_nodes)
        tables.extend(page_tables)
        issues.extend(page_issues)

    record = DossierRecord(
        tenant_id=tenant_id,
        dossier_id=dossier_id,
        lifecycle=LifecycleState.ACTIVE,
        pins=pins,
        pages=pages,
        nodes=nodes,
        tables=tables,
        profile=profile,
        acl_revision=acl_revision,
        permissions_by_actor={actor_id: ["READ_CONTENT"]},
        source_files=[source_file],
        case_id="AI1-SNAPSHOT",
        handoff_issues=issues,
    )
    envelope = ToolEnvelope(
        auth=AuthContext(
            actor_id=actor_id,
            tenant_id=tenant_id,
            dossier_id=dossier_id,
            acl_revision=acl_revision,
            permissions=["READ_CONTENT"],
        ),
        pins=pins.model_copy(),
    )
    return SnapshotAdapterResult(
        record=record,
        envelope=envelope,
        meta={
            "source": str(schema_version),
            "adapter": "snapshot-family",
            "snapshot_id": snapshot_id,
            "run_id": str(snapshot["run_id"]),
            "document_id": str(snapshot["document_id"]),
            "status": snapshot["status"],
            "n_pages": len(pages),
            "n_nodes": len(nodes),
            "n_tables": len(tables),
            "n_handoff_issues": len(issues),
            "table_structure_available": bool(tables),
            "table_coverage": _aggregate_table_coverage(pages),
        },
    )


def adapt_legacy_ocr(
    payload: Mapping[str, Any],
    *,
    tenant_id: str = "tenant_a",
    actor_id: str = "user_001",
    profile: TenantProfile | None = None,
    acl_revision: int = 1,
) -> SnapshotAdapterResult:
    """Adapt the currently observed page-text OCR response conservatively.

    The legacy response contains page text and summary counters, not actual
    line/word geometry or table cells.  It is useful for text-level search and
    clause chunking, but it cannot be promoted to confirmed visual evidence.
    """

    pages_in = payload.get("pages")
    if not isinstance(pages_in, list) or not pages_in:
        raise SnapshotContractError("legacy OCR payload must contain non-empty pages[]")
    document_id = str(payload.get("document_id") or "legacy-document")
    filename = str(payload.get("filename") or f"legacy:{document_id}")
    digest = _legacy_digest(payload)
    snapshot_id = f"legacy:{document_id}:{digest[:16]}"
    run_id = str(payload.get("run_id") or f"legacy-run:{digest[:16]}")
    dossier_id = str(payload.get("dossier_id") or f"legacy-dossier:{document_id}")
    expected_pages = payload.get("page_count")
    source_issues: list[HandoffIssue] = []
    if isinstance(expected_pages, int) and expected_pages != len(pages_in):
        source_issues.append(
            HandoffIssue(
                code="PAGE_COUNT_MISMATCH",
                message=f"legacy page_count={expected_pages}, received={len(pages_in)}",
                review_state=ReviewState.NEEDS_REVIEW,
            )
        )

    profile = profile or TenantProfile(version=1)
    pins = VersionPins(
        manifest_version=1,
        source_snapshot_digest=f"sha256:{digest}",
        tenant_profile_version=profile.version,
        policy_version=1,
        ocr_run_version=1,
        reconstruction_version=1,
        extraction_version=1,
    )
    source_file = SourceFile(
        file_id=document_id,
        filename=filename,
        role="body",
        digest=f"sha256:{digest}",
        n_pages=len(pages_in),
    )
    pages: list[PageSnapshot] = []
    nodes: list[StructuralNode] = []
    issues = [*source_issues]

    for index, raw_page in enumerate(pages_in, start=1):
        if not isinstance(raw_page, Mapping):
            raise SnapshotContractError(f"legacy page {index} must be an object")
        page_no = _legacy_page_number(raw_page, index)
        text = str(raw_page.get("text") or "")
        raw_status = str(raw_page.get("status") or "SUCCESS").upper()
        status = raw_status if raw_status in {"SUCCESS", "PARTIAL", "FAILED"} else "PARTIAL"
        error_code = _error_code(raw_page.get("error"))
        warning_codes = {"missing_line_geometry", "table_detection_unavailable"}
        if raw_page.get("geometry_available") is True:
            warning_codes.add("geometry_unverified")
        if error_code:
            warning_codes.add(error_code)
        lines = _legacy_lines(text, page_no)
        table_coverage = TableCoverage.UNKNOWN
        quality = _page_quality(
            status,
            text=text,
            lines=lines,
            warnings=warning_codes,
            data={"tables": [], "quality": {}},
        )
        page_revision_id = f"{snapshot_id}:p{page_no}"
        page = PageSnapshot(
            page_revision_id=page_revision_id,
            page_number=page_no,
            quality=quality,
            coverage=0.0 if quality in {"FAILED", "EMPTY"} else 0.5,
            rotation=0,
            source_block_ids=[str(line["line_id"]) for line in lines],
            text=text,
            source_file_id=document_id,
            page_in_file=page_no,
            table_coverage=table_coverage,
        )
        pages.append(page)
        if quality == "FAILED":
            issues.append(
                HandoffIssue(
                    code=error_code or "LEGACY_PAGE_FAILED",
                    message=f"legacy page {page_no}: OCR failed",
                    review_state=ReviewState.BLOCKED,
                )
            )
        elif quality == "EMPTY":
            issues.append(
                HandoffIssue(
                    code="PAGE_BLANK_UNVERIFIED",
                    message=f"legacy page {page_no}: no text was returned",
                    review_state=ReviewState.NEEDS_REVIEW,
                )
            )
        else:
            issues.append(
                HandoffIssue(
                    code="LEGACY_TEXT_ONLY",
                    message=f"legacy page {page_no}: text is available without line/word geometry",
                    review_state=ReviewState.NEEDS_REVIEW,
                )
            )
        issues.append(
            HandoffIssue(
                code="TABLE_DETECTION_UNKNOWN",
                message=f"legacy page {page_no}: tables were not reported by the source",
                review_state=ReviewState.NEEDS_REVIEW,
            )
        )
        nodes.extend(_line_nodes(page, lines, page_no=page_no))

    record = DossierRecord(
        tenant_id=tenant_id,
        dossier_id=dossier_id,
        lifecycle=LifecycleState.ACTIVE,
        pins=pins,
        pages=pages,
        nodes=nodes,
        tables=[],
        profile=profile,
        acl_revision=acl_revision,
        permissions_by_actor={actor_id: ["READ_CONTENT"]},
        source_files=[source_file],
        case_id="AI1-LEGACY-OCR",
        handoff_issues=issues,
    )
    envelope = ToolEnvelope(
        auth=AuthContext(
            actor_id=actor_id,
            tenant_id=tenant_id,
            dossier_id=dossier_id,
            acl_revision=acl_revision,
            permissions=["READ_CONTENT"],
        ),
        pins=pins.model_copy(),
    )
    return SnapshotAdapterResult(
        record=record,
        envelope=envelope,
        meta={
            "source": "legacy_ocr_json",
            "adapter": "legacy-text-only",
            "snapshot_id": snapshot_id,
            "run_id": run_id,
            "document_id": document_id,
            "status": "PARTIAL" if any(p.quality != "OK" for p in pages) else "SUCCESS",
            "n_pages": len(pages),
            "n_nodes": len(nodes),
            "n_tables": 0,
            "n_handoff_issues": len(issues),
            "table_structure_available": False,
            "table_coverage": _aggregate_table_coverage(pages),
            "capabilities": {
                "text": True,
                "line_geometry": False,
                "word_geometry": False,
                "table_structure": False,
                "table_geometry": False,
            },
        },
    )


def _adapt_result_page(
    raw_page: Mapping[str, Any],
    doc_by_id: Mapping[str, Mapping[str, Any]],
    scope_id: str,
    issues: list[HandoffIssue],
) -> PageSnapshot:
    try:
        page_number = int(raw_page.get("page_number"))
    except (TypeError, ValueError) as exc:
        raise SnapshotContractError("ai1 result page_number must be an integer", code="RESULT_SEMANTIC_INVALID") from exc
    if page_number < 1:
        raise SnapshotContractError("ai1 result page_number must be >= 1", code="RESULT_SEMANTIC_INVALID")
    document_id = str(raw_page.get("document_id") or "")
    if not document_id:
        raise SnapshotContractError("ai1 result page requires document_id", code="RESULT_SEMANTIC_INVALID")
    lines = [line for line in (raw_page.get("lines") or []) if isinstance(line, Mapping)]
    line_texts = {str(line.get("id")): str(line.get("text") or "") for line in lines if line.get("id")}
    line_bboxes = {
        str(line.get("id")): bbox
        for line in lines
        if line.get("id") and (bbox := _bbox(line.get("bbox")))
    }
    text = "\n".join(value for value in line_texts.values() if value)
    status = str(raw_page.get("status") or "completed").lower()
    quality = "OK" if status in {"completed", "success", "succeeded"} and text.strip() else "EMPTY" if not text.strip() else "LOW"
    if status in {"failed", "error"}:
        quality = "FAILED"
        issues.append(
            HandoffIssue(
                code="AI1_PAGE_FAILED",
                message=f"page {page_number}: {raw_page.get('issue') or status}",
                review_state=ReviewState.BLOCKED,
            )
        )
    elif quality == "EMPTY":
        issues.append(
            HandoffIssue(
                code="AI1_PAGE_EMPTY",
                message=f"page {page_number}: AI1 returned no text",
                review_state=ReviewState.NEEDS_REVIEW,
            )
        )
    page_revision_id = f"ai1:{document_id}:p{page_number}"
    source_hash = str(raw_page.get("sha256") or (doc_by_id.get(document_id) or {}).get("sha256") or "")
    table_values = raw_page.get("tables") if isinstance(raw_page.get("tables"), list) else []
    page = PageSnapshot(
        page_revision_id=page_revision_id,
        page_number=page_number,
        quality=quality,  # type: ignore[arg-type]
        coverage=0.0 if quality in {"FAILED", "EMPTY"} else 1.0,
        rotation=int(raw_page.get("rotation") or 0),
        source_block_ids=list(line_texts),
        text=text,
        source_file_id=document_id,
        page_in_file=page_number,
        table_coverage=TableCoverage.DETECTED if table_values else TableCoverage.UNKNOWN,
        width=int(raw_page.get("width") or 0) or None,
        height=int(raw_page.get("height") or 0) or None,
        image_key=str(raw_page.get("image_key") or "") or None,
        line_texts=line_texts,
        line_bboxes=line_bboxes,
        source_hash=source_hash,
    )
    return page


def _adapt_result_table(
    raw_table: Mapping[str, Any],
    *,
    page_by_key: Mapping[tuple[str, int], PageSnapshot],
    doc_by_id: Mapping[str, Mapping[str, Any]],
    scope_id: str,
) -> tuple[TableSnapshot | None, StructuralNode | None, dict[str, Citation], list[HandoffIssue]]:
    table_id = str(raw_table.get("id") or "")
    document_id = str(raw_table.get("document_id") or "")
    try:
        page_number = int(raw_table.get("page_number"))
    except (TypeError, ValueError):
        page_number = 0
    page = page_by_key.get((document_id, page_number))
    if not table_id or page is None:
        return None, None, {}, [_result_issue("TABLE_SOURCE_UNRESOLVED", f"table {table_id or '<missing>'} has no source page")]
    cells: list[TableCell] = []
    citations: dict[str, Citation] = {}
    raw_rows = raw_table.get("rows") if isinstance(raw_table.get("rows"), list) else []
    max_col = -1
    cell_positions: set[tuple[int, int]] = set()
    for row_index, raw_row in enumerate(raw_rows):
        if not isinstance(raw_row, Mapping):
            continue
        try:
            row_no = int(raw_row.get("row_index", row_index))
        except (TypeError, ValueError):
            row_no = row_index
        raw_cells = raw_row.get("cells") if isinstance(raw_row.get("cells"), list) else []
        for fallback_col, raw_cell in enumerate(raw_cells):
            if not isinstance(raw_cell, Mapping):
                continue
            try:
                col_no = int(raw_cell.get("col_index", fallback_col))
            except (TypeError, ValueError):
                col_no = fallback_col
            max_col = max(max_col, col_no)
            if row_no < 0 or col_no < 0 or (row_no, col_no) in cell_positions:
                raise SnapshotContractError("invalid/duplicate cell coordinate", code="RESULT_SEMANTIC_INVALID")
            cell_positions.add((row_no, col_no))
            bbox = _bbox(raw_cell.get("bbox"))
            cell_id = f"{table_id}:r{row_no}:c{col_no}"
            cell = TableCell(
                cell_id=cell_id,
                row_index=row_no,
                column_index=col_no,
                text=str(raw_cell.get("text") or ""),
                bbox=bbox,
                line_ids=_unique_line_ids_for_text(page, str(raw_cell.get("text") or "")),
            )
            cells.append(cell)
    rows = _rows_from_cells(cells) if cells else []
    node_id = f"table-node:{table_id}"
    source_hash = str(raw_table.get("source_hash") or page.source_hash or (doc_by_id.get(document_id) or {}).get("sha256") or "")
    for cell in cells:
        citation_id = f"{table_id}:{cell.row_index}:{cell.column_index}"
        cite = Citation(
            citation_id=citation_id,
            node_id=node_id,
            page_revision_id=page.page_revision_id,
            bbox=cell.bbox,
            text_span=cell.text,
            source_file_id=document_id,
            page=page_number,
            page_range=[page_number],
            line_ids=list(cell.line_ids),
            source_hash=source_hash,
            quote_sha256=_quote_digest(cell.text),
            coordinate_system="normalized_top_left_rendered_page",
            geometry_source="ai1.result.table_cell" if cell.bbox else None,
            precision="cell" if cell.bbox else "text",
            table_id=table_id,
            cell_id=cell.cell_id,
            geometry_available=bool(cell.bbox),
            validation_status="UNVERIFIED",
        )
        cite.char_start = _char_offset(page, cell.text, cell.line_ids[0] if len(cell.line_ids) == 1 else None)
        cite.char_end = cite.char_start + len(cell.text) if cite.char_start is not None else None
        cite.validation_status = CitationResolver([page]).verify(cite).status
        citations[f"{cell.row_index}:{cell.column_index}"] = cite
    continuation = bool(raw_table.get("continues_table_id") or raw_table.get("continued_by_table_id"))
    low_confidence = bool(raw_table.get("low_confidence")) or continuation
    issues: list[HandoffIssue] = []
    if continuation:
        issues.append(
            HandoffIssue(
                code="TABLE_CONTINUATION_REVIEW",
                message=f"table {table_id}: continuation kept separate; AI2 did not merge it",
                review_state=ReviewState.NEEDS_REVIEW,
            )
        )
    if cells and not any(cell.bbox for cell in cells):
        issues.append(
            HandoffIssue(
                code="TABLE_GEOMETRY_UNAVAILABLE",
                message=f"table {table_id}: cells have text but no geometry",
                review_state=ReviewState.NEEDS_REVIEW,
            )
        )
    table = TableSnapshot(
        table_id=table_id,
        title=f"Bảng {table_id}",
        header=["" for _ in range(max_col + 1)] if max_col >= 0 else [],
        rows=rows,
        continuation=continuation,
        node_id=node_id,
        page_revision_id=page.page_revision_id,
        cell_citations=citations,
        cells=cells,
    )
    from app.pipeline.table_headers import identify_header
    header, header_rows = identify_header(rows)
    table.header = header or table.header
    table.header_row_indices = header_rows
    if not header:
        table.continuation = True
        issues.append(_result_issue("TABLE_HEADER_UNRESOLVED", f"table {table_id}: header absent; possible continuation requires review"))
    for cite in citations.values():
        cite.validation_status = CitationResolver([page], [table]).verify(cite).status
    node = StructuralNode(
        node_id=node_id,
        type="TABLE",
        raw_label=f"Bảng {table_id}",
        order=10_000 + page_number,
        status="PARTIAL" if low_confidence else "CONFIRMED",
        text="\n".join(cell.text for cell in cells if cell.text)[:3000],
        page_range=[page_number],
        page_revision_id=page.page_revision_id,
        bbox=_bbox(raw_table.get("bbox")),
        source_file_id=document_id,
        page_in_file=page_number,
        structure_level="TABLE",
        scope_id=scope_id,
        source_line_ids=sorted({line_id for cell in cells for line_id in cell.line_ids}),
    )
    return table, node, citations, issues


def _adapt_result_fact(
    raw_fact: Mapping[str, Any],
    *,
    raw_citations: Mapping[str, Mapping[str, Any]],
    page_by_key: Mapping[tuple[str, int], PageSnapshot],
    doc_by_id: Mapping[str, Mapping[str, Any]],
    citation_index: dict[str, Citation],
    scope_id: str,
) -> tuple[Fact | None, StructuralNode | None, dict[str, Citation], list[HandoffIssue]]:
    fact_id = str(raw_fact.get("id") or "")
    if not fact_id:
        return None, None, {}, [_result_issue("FACT_ID_MISSING", "AI1 fact has no id")]
    raw_value = str(raw_fact.get("raw") or "")
    if not raw_value:
        return None, None, {}, [_result_issue("FACT_VALUE_MISSING", f"fact {fact_id} has no raw value")]
    refs = [str(x) for x in (raw_fact.get("citation_ids") or [])]
    node_id = f"fact-node:{fact_id}"
    local_citations: dict[str, Citation] = {}
    issues: list[HandoffIssue] = []
    cite = _result_citation_for_refs(
        refs,
        raw_citations,
        node_id=node_id,
        page_by_key=page_by_key,
        doc_by_id=doc_by_id,
        citation_index=local_citations,
        issues=issues,
    )
    normalized = raw_fact.get("normalized")
    if isinstance(normalized, Mapping):
        normalized_value = next((str(normalized[key]) for key in ("name", "value", "date", "amount", "mst") if normalized.get(key) is not None), json.dumps(normalized, ensure_ascii=False, sort_keys=True))
    elif normalized is None:
        normalized_value = None
    else:
        normalized_value = str(normalized)
    fact_type = str(raw_fact.get("type") or "field")
    source_role = _result_role(raw_fact.get("source_role"))
    context = raw_fact.get("context") if isinstance(raw_fact.get("context"), Mapping) else {}
    field_node = StructuralNode(
        node_id=node_id,
        type="FIELD",
        raw_label=f"{fact_type}: {raw_value}",
        status="CONFIRMED" if cite and cite.validation_status == "VALID" else "PARTIAL",
        text=str(context.get("source_line") or raw_value),
        page_range=cite.page_range if cite else [],
        page_revision_id=cite.page_revision_id if cite else None,
        bbox=cite.bbox if cite else [],
        structured_key=_fact_key(fact_type),
        structured_value=raw_value,
        source_file_id=cite.source_file_id if cite else str(raw_fact.get("document_id") or "") or None,
        page_in_file=cite.page if cite else None,
        structure_level="FIELD",
        scope_id=scope_id,
        source_line_ids=cite.line_ids if cite else [],
    )
    if cite is None:
        issues.append(_result_issue("FACT_CITATION_MISSING", f"fact {fact_id} has no resolvable citation"))
        cite = Citation(
            citation_id=fact_id,
            node_id=node_id,
            page_revision_id="",
            text_span=raw_value,
            validation_status="INVALID",
        )
    else:
        citation_index.update(local_citations)
    confidence = raw_fact.get("confidence") if isinstance(raw_fact.get("confidence"), Mapping) else {}
    state = ReviewState.PASS if cite.validation_status == "VALID" else ReviewState.NEEDS_REVIEW
    fact = Fact(
        fact_id=fact_id,
        raw_value=raw_value,
        normalized_value=normalized_value,
        subject=str(context.get("clause_label") or fact_type),
        role=fact_type,
        source_role=source_role,
        scope=str(context.get("clause_ref") or scope_id),
        citation=cite,
        provenance="AI1_RESULT_V0.1",
        review_state=state,
    )
    if confidence.get("signals", {}).get("source_resolved") is False:
        fact.review_state = ReviewState.NEEDS_REVIEW
    return fact, field_node, local_citations, issues


def _derive_result_facts(
    *,
    pages: list[PageSnapshot],
    raw_citations: Mapping[str, Mapping[str, Any]],
    existing_facts: list[Fact],
    citation_index: dict[str, Citation],
    scope_id: str,
) -> tuple[list[Fact], list[StructuralNode], dict[str, Citation], list[HandoffIssue]]:
    """Recover high-signal fields when AI1 only emitted OCR lines.

    This is deliberately limited to deterministic labels (party, tax id and
    explicit totals). It never treats an arbitrary number as a business fact.
    """

    existing_keys = {_fact_key(f.role or "") for f in existing_facts}
    existing_values = {" ".join(f.raw_value.split()).casefold() for f in existing_facts}
    facts: list[Fact] = []
    nodes: list[StructuralNode] = []
    citations: dict[str, Citation] = {}
    issues: list[HandoffIssue] = []

    def emit_derived(
        *,
        fact_type: str,
        raw_value: str,
        page: PageSnapshot,
        line_id: str,
        source_text: str,
    ) -> None:
        role = _fact_key(fact_type)
        normalized_raw = " ".join(raw_value.split()).casefold()
        if role in existing_keys or normalized_raw in existing_values:
            return
        fact, node, local, local_issues = _make_derived_fact(
            fact_type=fact_type,
            raw_value=raw_value,
            page=page,
            line_id=line_id,
            source_text=source_text,
            raw_citations=raw_citations,
            citation_index=citation_index,
            scope_id=scope_id,
        )
        if fact and node:
            facts.append(fact)
            nodes.append(node)
            citations.update(local)
            issues.extend(local_issues)
            existing_keys.add(role)
            existing_values.add(normalized_raw)

    current_party: str | None = None
    ordered_pages = sorted(pages, key=lambda item: (item.source_file_id or "", item.page_number))
    for page in ordered_pages:
        for line_id, text in page.line_texts.items():
            value = str(text or "").strip()
            if not value:
                continue
            folded = fold_for_match(value)
            party_match = re.search(r"\bben\s+([abcy])(?:\s*\([^)]*\))?\s*[:：]\s*(.+)$", folded, re.I)
            if party_match:
                party = party_match.group(1).lower()
                current_party = party
                party_value = value.split(":", 1)[1].strip() if ":" in value or "：" in value else party_match.group(2).strip()
                if "party_" + party not in existing_keys and party_value.casefold() not in existing_values:
                    fact, node, local, local_issues = _make_derived_fact(
                        fact_type=f"party_{party}",
                        raw_value=party_value,
                        page=page,
                        line_id=line_id,
                        source_text=value,
                        raw_citations=raw_citations,
                        citation_index=citation_index,
                        scope_id=scope_id,
                    )
                    if fact and node:
                        facts.append(fact)
                        nodes.append(node)
                        citations.update(local)
                        issues.extend(local_issues)
                        existing_keys.add("party_" + party)
                        existing_values.add(party_value.casefold())
                continue

            tax_match = re.search(r"(?:ma\s+so\s+thue|mst)\s*[:：]?\s*([0-9]{8,14})", folded, re.I)
            if tax_match:
                role = f"mst_party_{current_party}" if current_party else "mst"
                if role not in existing_keys and tax_match.group(1) not in existing_values:
                    fact, node, local, local_issues = _make_derived_fact(
                        fact_type=role,
                        raw_value=tax_match.group(1),
                        page=page,
                        line_id=line_id,
                        source_text=value,
                        raw_citations=raw_citations,
                        citation_index=citation_index,
                        scope_id=scope_id,
                    )
                    if fact and node:
                        facts.append(fact)
                        nodes.append(node)
                        citations.update(local)
                        issues.extend(local_issues)
                        existing_keys.add(role)
                        existing_values.add(tax_match.group(1))

            contract_match = re.search(r"\bso\s*[:ï¼š]\s*([0-9][a-z0-9./_-]{3,})", folded, re.I)
            if contract_match:
                contract_value = contract_match.group(1)
                if ":" in value:
                    contract_value = value.split(":", 1)[1].strip().split()[0]
                emit_derived(
                    fact_type="contract_number",
                    raw_value=contract_value,
                    page=page,
                    line_id=line_id,
                    source_text=value,
                )

            amount_match = re.search(
                r"(?:tong\s+gia\s+tri(?:\s+tam\s+tinh)?|gia\s+tri\s+hop\s+dong|tong\s+cong)"
                r"[^0-9]{0,100}([0-9][0-9.,]*)\s*(?:dong|vnd)\b",
                folded,
                re.I,
            )
            if amount_match:
                emit_derived(
                    fact_type="contract_value",
                    raw_value=amount_match.group(1),
                    page=page,
                    line_id=line_id,
                    source_text=value,
                )

            payment_match = re.search(r"(?:tien\s+do\s+thanh\s+toan|thanh\s+toan)\s*[:ï¼š]\s*(.+)$", folded, re.I)
            if payment_match:
                separator = ":" if ":" in value else "："
                payment_value = value.split(separator, 1)[1].strip() if separator in value else payment_match.group(1).strip()
                emit_derived(
                    fact_type="payment_schedule",
                    raw_value=payment_value,
                    page=page,
                    line_id=line_id,
                    source_text=value,
                )

    return facts, nodes, citations, issues


def _make_derived_fact(
    *,
    fact_type: str,
    raw_value: str,
    page: PageSnapshot,
    line_id: str,
    source_text: str,
    raw_citations: Mapping[str, Mapping[str, Any]],
    citation_index: dict[str, Citation],
    scope_id: str,
) -> tuple[Fact | None, StructuralNode | None, dict[str, Citation], list[HandoffIssue]]:
    base_ref = next(
        (
            ref
            for ref, raw in raw_citations.items()
            if str(raw.get("document_id") or "") == str(page.source_file_id or "")
            and int(raw.get("page_number") or 0) == page.page_number
            and str(raw.get("line_id") or "") == line_id
        ),
        None,
    )
    node_id = f"derived-fact-node:{page.source_file_id}:{page.page_number}:{line_id}:{fact_type}"
    local: dict[str, Citation] = {}
    issues: list[HandoffIssue] = []
    cite: Citation | None = None
    if base_ref:
        raw = dict(raw_citations[base_ref])
        derived_ref = f"{base_ref}:{fact_type}"
        raw["id"] = derived_ref
        cite = _result_citation_for_refs(
            [derived_ref],
            {derived_ref: raw},
            node_id=node_id,
            page_by_key={(p.source_file_id or "", p.page_number): p for p in [page]},
            doc_by_id={},
            citation_index=local,
            issues=issues,
        )
    if cite is None:
        char_start = _char_offset(page, source_text, line_id)
        cite = Citation(
            citation_id=f"derived:{node_id}",
            node_id=node_id,
            page_revision_id=page.page_revision_id,
            bbox=page.line_bboxes.get(line_id, []),
            text_span=source_text,
            source_file_id=page.source_file_id,
            page=page.page_number,
            page_range=[page.page_number],
            line_ids=[line_id],
            source_hash=page.source_hash,
            char_start=char_start,
            char_end=(char_start + len(source_text)) if char_start is not None else None,
            quote_sha256=_quote_digest(source_text),
            coordinate_system="normalized_top_left_rendered_page",
            geometry_source="ai1.result.line",
            precision="line",
            geometry_available=bool(page.line_bboxes.get(line_id)),
            validation_status="UNVERIFIED",
        )
        cite.validation_status = CitationResolver([page]).verify(cite).status
        local[cite.citation_id or node_id] = cite
    citation_index.update(local)
    fact = Fact(
        fact_id=f"derived-fact:{page.source_file_id}:{page.page_number}:{line_id}:{fact_type}",
        raw_value=raw_value,
        normalized_value=raw_value,
        subject=fact_type,
        role=fact_type,
        source_role="body",
        scope=scope_id,
        item_key=_fact_key(fact_type),
        citation=cite,
        provenance="AI2_DETERMINISTIC_LINE_RECOVERY",
        review_state=ReviewState.PASS if cite.validation_status == "VALID" else ReviewState.NEEDS_REVIEW,
    )
    node = StructuralNode(
        node_id=node_id,
        type="FIELD",
        raw_label=f"{fact_type}: {raw_value}",
        status="CONFIRMED" if cite.validation_status == "VALID" else "PARTIAL",
        text=source_text,
        page_range=[page.page_number],
        page_revision_id=page.page_revision_id,
        bbox=cite.bbox,
        structured_key=_fact_key(fact_type),
        structured_value=raw_value,
        source_file_id=page.source_file_id,
        page_in_file=page.page_number,
        structure_level="FIELD",
        scope_id=scope_id,
        source_line_ids=[line_id],
    )
    return fact, node, local, issues


def _result_citation_for_refs(
    refs: list[str],
    raw_citations: Mapping[str, Mapping[str, Any]],
    *,
    node_id: str,
    page_by_key: Mapping[tuple[str, int], PageSnapshot],
    doc_by_id: Mapping[str, Mapping[str, Any]],
    citation_index: dict[str, Citation],
    issues: list[HandoffIssue],
) -> Citation | None:
    for ref in refs:
        raw = raw_citations.get(ref)
        if raw is None:
            continue
        try:
            page_number = int(raw.get("page_number"))
        except (TypeError, ValueError):
            page_number = 0
        document_id = str(raw.get("document_id") or "")
        page = page_by_key.get((document_id, page_number))
        if page is None:
            continue
        line_id = str(raw.get("line_id") or "")
        quote = str(raw.get("quote") or "")
        source_hash = str(raw.get("source_hash") or page.source_hash or (doc_by_id.get(document_id) or {}).get("sha256") or "")
        char_start = _char_offset(page, quote, line_id)
        cite = Citation(
            citation_id=ref,
            node_id=node_id,
            page_revision_id=page.page_revision_id,
            bbox=_bbox(raw.get("bbox")) or page.line_bboxes.get(line_id, []),
            text_span=quote,
            source_file_id=document_id,
            page=page_number,
            page_range=[page_number],
            line_ids=[line_id] if line_id else [],
            char_start=char_start,
            char_end=(char_start + len(quote)) if char_start is not None else None,
            source_hash=source_hash,
            quote_sha256=_quote_digest(quote),
            coordinate_system=str(raw.get("coordinate_system") or "normalized_top_left_rendered_page"),
            geometry_source=str(raw.get("geometry_source") or "") or None,
            precision=str(raw.get("precision") or "line"),
            geometry_available=bool(raw.get("bbox")),
            validation_status="UNVERIFIED",
        )
        cite.validation_status = CitationResolver([page]).verify(cite).status
        citation_index[ref] = cite
        if cite.validation_status != "VALID":
            issues.append(_result_issue("CITATION_UNRESOLVED", f"citation {ref} could not be verified against AI1 page text", citation=cite))
        return cite
    if refs:
        issues.append(_result_issue("CITATION_UNRESOLVED", f"none of citation_ids resolved: {refs[:3]}"))
    return None


def _review_items_from_issues(issues: list[HandoffIssue]) -> list[ReviewItem]:
    return [
        ReviewItem(
            review_item_id=f"review:{index}:{issue.code}",
            kind=issue.code,
            reason=issue.message,
            review_state=issue.review_state,
            proposed_action="VERIFY_EVIDENCE" if issue.review_state != ReviewState.BLOCKED else "FIX_INPUT",
            citation_ids=[issue.citation.citation_id] if issue.citation and issue.citation.citation_id else [],
        )
        for index, issue in enumerate(issues, start=1)
        if issue.review_state in {ReviewState.NEEDS_REVIEW, ReviewState.INSUFFICIENT_EVIDENCE, ReviewState.BLOCKED}
    ]


def _result_issue(code: str, message: str, *, citation: Citation | None = None) -> HandoffIssue:
    return HandoffIssue(code=code, message=message, review_state=ReviewState.NEEDS_REVIEW, citation=citation)


def _result_role(value: Any) -> str:
    return "annex" if str(value or "").casefold() in {"annex", "appendix", "phu_luc", "phụ lục"} else "body"


def _hash_digest(value: Any) -> str:
    text = str(value or "")
    return text if not text or text.startswith("sha256:") else f"sha256:{text}"


def _fact_key(value: str) -> str:
    key = value.casefold().replace("-", "_").replace(" ", "_")
    aliases = {
        "party_a": "party_a",
        "party_b": "party_b",
        "mst_a": "mst_party_a",
        "mst_b": "mst_party_b",
        "tax_id": "mst",
        "amount": "amount",
    }
    return aliases.get(key, key)


def _quote_digest(value: str) -> str:
    return quote_digest(str(value))


def _char_offset(page: PageSnapshot, quote: str, line_id: str | None = None) -> int | None:
    if not quote:
        return None
    if line_id:
        line_text = page.line_texts.get(line_id)
        if line_text is not None:
            cursor = 0
            for current_id, current_text in page.line_texts.items():
                if current_id == line_id:
                    local = line_text.find(quote)
                    if local >= 0:
                        return cursor + local
                    break
                cursor += len(current_text) + 1
    index = page.text.find(quote)
    if index >= 0:
        return index
    return None


def _unique_line_ids_for_text(page: PageSnapshot, text: str) -> list[str]:
    """Return line provenance only when a table cell maps unambiguously to OCR text."""

    needle = str(text or "").strip()
    if not needle or len(needle) < 3:
        return []
    matches = [line_id for line_id, line_text in page.line_texts.items() if needle in line_text]
    return matches if len(matches) == 1 else []


def _text_in_page(page: PageSnapshot, quote: str) -> bool:
    if not quote.strip():
        return False
    return quote in page.text


def _result_table_coverage(pages: list[PageSnapshot], tables: list[TableSnapshot], coverage: Mapping[str, Any]) -> str:
    if tables:
        return TableCoverage.DETECTED.value
    if bool(coverage.get("coverage_complete")):
        return TableCoverage.NOT_PRESENT.value
    return TableCoverage.UNKNOWN.value


def _validate_snapshot_semantics(snapshot: Mapping[str, Any]) -> None:
    """Run canonical v1 semantic checks that JSON Schema cannot express safely."""

    digest = snapshot.get("source_digest")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
        raise SnapshotContractError(
            "source_digest must be a full 64-character SHA-256 hex digest",
            code="SNAPSHOT_SEMANTIC_INVALID",
        )
    pages = snapshot.get("pages")
    if not isinstance(pages, list):
        raise SnapshotContractError("pages must be an array", code="SNAPSHOT_SEMANTIC_INVALID")
    page_numbers: set[int] = set()
    page_revision_ids: set[str] = set()
    table_ids: set[str] = set()
    cell_ids: set[str] = set()
    for raw_page in pages:
        if not isinstance(raw_page, Mapping):
            raise SnapshotContractError("page must be an object", code="SNAPSHOT_SEMANTIC_INVALID")
        try:
            page_no = int(raw_page.get("page_no"))
        except (TypeError, ValueError) as exc:
            raise SnapshotContractError("page_no must be an integer", code="SNAPSHOT_SEMANTIC_INVALID") from exc
        if page_no in page_numbers:
            raise SnapshotContractError(
                f"duplicate page_no={page_no}", code="SNAPSHOT_SEMANTIC_INVALID"
            )
        page_numbers.add(page_no)
        page_revision_id = str(raw_page.get("page_revision_id") or "")
        if page_revision_id and page_revision_id in page_revision_ids:
            raise SnapshotContractError(
                f"duplicate page_revision_id={page_revision_id}", code="SNAPSHOT_SEMANTIC_INVALID"
            )
        if page_revision_id:
            page_revision_ids.add(page_revision_id)
        coverage = raw_page.get("table_coverage")
        coverage_status = coverage.get("status") if isinstance(coverage, Mapping) else None
        if coverage is not None and isinstance(coverage, Mapping) and coverage_status not in {
            item.value for item in TableCoverage
        }:
            raise SnapshotContractError(
                f"page {page_no}: invalid table_coverage.status",
                code="SNAPSHOT_SEMANTIC_INVALID",
            )
        tables = raw_page.get("tables") if isinstance(raw_page.get("tables"), list) else []
        if coverage_status == TableCoverage.NOT_PRESENT.value and tables:
            raise SnapshotContractError(
                f"page {page_no}: NOT_PRESENT cannot contain tables",
                code="SNAPSHOT_SEMANTIC_INVALID",
            )
        lines = raw_page.get("lines") if isinstance(raw_page.get("lines"), list) else []
        line_ids: set[str] = set()
        for raw_line in lines:
            if not isinstance(raw_line, Mapping):
                raise SnapshotContractError(
                    f"page {page_no}: line must be an object", code="SNAPSHOT_SEMANTIC_INVALID"
                )
            line_id = str(raw_line.get("line_id") or "")
            if not line_id or line_id in line_ids:
                raise SnapshotContractError(
                    f"page {page_no}: duplicate or missing line_id",
                    code="SNAPSHOT_SEMANTIC_INVALID",
                )
            line_ids.add(line_id)
            _validate_bbox_value(raw_line.get("bbox"), f"page {page_no} line {line_id}")
            raw_text = str(raw_line.get("raw_text") or "")
            words = raw_line.get("words") if isinstance(raw_line.get("words"), list) else []
            word_ids: set[str] = set()
            for raw_word in words:
                if not isinstance(raw_word, Mapping):
                    raise SnapshotContractError(
                        f"line {line_id}: word must be an object", code="SNAPSHOT_SEMANTIC_INVALID"
                    )
                word_id = str(raw_word.get("word_id") or "")
                if not word_id or word_id in word_ids:
                    raise SnapshotContractError(
                        f"line {line_id}: duplicate or missing word_id",
                        code="SNAPSHOT_SEMANTIC_INVALID",
                    )
                word_ids.add(word_id)
                try:
                    start = int(raw_word.get("char_start"))
                    end = int(raw_word.get("char_end"))
                except (TypeError, ValueError) as exc:
                    raise SnapshotContractError(
                        f"word {word_id}: invalid char offsets", code="SNAPSHOT_SEMANTIC_INVALID"
                    ) from exc
                if start < 0 or end <= start or end > len(raw_text):
                    raise SnapshotContractError(
                        f"word {word_id}: char offsets outside line text",
                        code="SNAPSHOT_SEMANTIC_INVALID",
                    )
                _validate_bbox_value(raw_word.get("bbox"), f"word {word_id}")
        for raw_table in tables:
            if not isinstance(raw_table, Mapping):
                raise SnapshotContractError(
                    f"page {page_no}: table must be an object", code="SNAPSHOT_SEMANTIC_INVALID"
                )
            table_id = str(raw_table.get("table_id") or "")
            cells = raw_table.get("cells") if isinstance(raw_table.get("cells"), list) else []
            if not table_id or table_id in table_ids or not cells:
                raise SnapshotContractError(
                    f"page {page_no}: table requires unique table_id and cells",
                    code="SNAPSHOT_SEMANTIC_INVALID",
                )
            table_ids.add(table_id)
            _validate_bbox_value(raw_table.get("bbox"), f"table {table_id}")
            for raw_cell in cells:
                if not isinstance(raw_cell, Mapping):
                    raise SnapshotContractError(
                        f"table {table_id}: cell must be an object",
                        code="SNAPSHOT_SEMANTIC_INVALID",
                    )
                cell_id = str(raw_cell.get("cell_id") or "")
                if not cell_id or cell_id in cell_ids:
                    raise SnapshotContractError(
                        f"table {table_id}: duplicate or missing cell_id",
                        code="SNAPSHOT_SEMANTIC_INVALID",
                    )
                cell_ids.add(cell_id)
                _validate_bbox_value(raw_cell.get("bbox"), f"table {table_id} cell {cell_id}")
                for fragment in raw_cell.get("bbox_fragments") or []:
                    _validate_bbox_value(fragment, f"table {table_id} cell")
                unknown_lines = set(str(x) for x in (raw_cell.get("line_ids") or [])) - line_ids
                if unknown_lines:
                    raise SnapshotContractError(
                        f"table {table_id}: unknown line_ids={sorted(unknown_lines)}",
                        code="SNAPSHOT_SEMANTIC_INVALID",
                    )


def _validate_snapshot_compatibility_semantics(snapshot: Mapping[str, Any]) -> None:
    """Check high-value invariants without rejecting degraded workspace fixtures."""

    digest = snapshot.get("source_digest")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
        raise SnapshotContractError(
            "source_digest must be a full 64-character SHA-256 hex digest",
            code="SNAPSHOT_SEMANTIC_INVALID",
        )
    pages = snapshot.get("pages")
    if not isinstance(pages, list):
        raise SnapshotContractError("pages must be an array", code="SNAPSHOT_SEMANTIC_INVALID")

    page_numbers: set[int] = set()
    page_revision_ids: set[str] = set()
    for raw_page in pages:
        if not isinstance(raw_page, Mapping):
            raise SnapshotContractError("page must be an object", code="SNAPSHOT_SEMANTIC_INVALID")
        try:
            page_no = int(raw_page.get("page_no"))
        except (TypeError, ValueError) as exc:
            raise SnapshotContractError("page_no must be an integer", code="SNAPSHOT_SEMANTIC_INVALID") from exc
        if page_no in page_numbers:
            raise SnapshotContractError(
                f"duplicate page_no={page_no}", code="SNAPSHOT_SEMANTIC_INVALID"
            )
        page_numbers.add(page_no)

        page_revision_id = str(raw_page.get("page_revision_id") or "")
        if page_revision_id and page_revision_id in page_revision_ids:
            raise SnapshotContractError(
                f"duplicate page_revision_id={page_revision_id}", code="SNAPSHOT_SEMANTIC_INVALID"
            )
        if page_revision_id:
            page_revision_ids.add(page_revision_id)

        lines = raw_page.get("lines") if isinstance(raw_page.get("lines"), list) else []
        line_ids: set[str] = set()
        for raw_line in lines:
            if not isinstance(raw_line, Mapping):
                raise SnapshotContractError(
                    f"page {page_no}: line must be an object", code="SNAPSHOT_SEMANTIC_INVALID"
                )
            line_id = str(raw_line.get("line_id") or "")
            if line_id and line_id in line_ids:
                raise SnapshotContractError(
                    f"page {page_no}: duplicate line_id={line_id}",
                    code="SNAPSHOT_SEMANTIC_INVALID",
                )
            if line_id:
                line_ids.add(line_id)

            raw_text = str(raw_line.get("raw_text") or "")
            words = raw_line.get("words") if isinstance(raw_line.get("words"), list) else []
            for raw_word in words:
                if not isinstance(raw_word, Mapping):
                    continue
                if raw_word.get("char_start") is None or raw_word.get("char_end") is None:
                    continue
                try:
                    start = int(raw_word["char_start"])
                    end = int(raw_word["char_end"])
                except (TypeError, ValueError) as exc:
                    raise SnapshotContractError(
                        f"line {line_id or page_no}: invalid char offsets",
                        code="SNAPSHOT_SEMANTIC_INVALID",
                    ) from exc
                if start < 0 or end <= start or end > len(raw_text):
                    raise SnapshotContractError(
                        f"line {line_id or page_no}: word char offsets outside line text",
                        code="SNAPSHOT_SEMANTIC_INVALID",
                    )


def _validate_bbox_value(value: Any, label: str) -> None:
    if value is None:
        return
    box = _bbox(value)
    if len(box) != 4 or not all(0 <= number <= 1 for number in box) or box[2] <= box[0] or box[3] <= box[1]:
        raise SnapshotContractError(f"{label}: invalid bbox", code="SNAPSHOT_SEMANTIC_INVALID")


def _adapt_page(
    data: Mapping[str, Any],
    *,
    snapshot_id: str,
    source_file_id: str,
    source_hash: str | None = None,
) -> tuple[PageSnapshot, list[StructuralNode], list[TableSnapshot], list[HandoffIssue]]:
    try:
        page_no = int(data["page_no"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SnapshotContractError("page.page_no must be an integer") from exc
    if page_no < 1:
        raise SnapshotContractError("page.page_no must be >= 1")

    status = str(data.get("status", "PARTIAL")).upper()
    if status not in {"SUCCESS", "PARTIAL", "FAILED"}:
        raise SnapshotContractError(f"page {page_no}: invalid status {status}")
    warnings = _warning_codes(data.get("warnings"))
    error_code = _error_code(data.get("error"))
    warning_set = set(warnings)
    if error_code:
        warning_set.add(error_code)

    lines = data.get("lines") if isinstance(data.get("lines"), list) else []
    text = _page_text(data, lines)
    line_texts = {
        str(line.get("line_id")): str(line.get("raw_text", line.get("text", "")))
        for line in lines
        if isinstance(line, Mapping) and line.get("line_id")
    }
    line_bboxes = {
        str(line.get("line_id")): _bbox(line.get("bbox"))
        for line in lines
        if isinstance(line, Mapping) and line.get("line_id") and _has_geometry(line)
    }
    table_coverage = _table_coverage(data, warning_set)
    page_revision_id = str(data.get("page_revision_id") or f"{snapshot_id}:p{page_no}")
    if table_coverage == TableCoverage.DETECTED:
        raw_tables = data.get("tables") if isinstance(data.get("tables"), list) else []
        if not _has_usable_table_cells(raw_tables):
            warning_set.add("table_cells_unavailable")
        elif not _has_table_geometry(raw_tables):
            warning_set.add("table_geometry_unavailable")
    quality = _page_quality(status, text=text, lines=lines, warnings=warning_set, data=data)
    transform = data.get("transform") if isinstance(data.get("transform"), Mapping) else {}
    rotation = int(transform.get("rotation_degrees", 0) or 0)
    page = PageSnapshot(
        page_revision_id=page_revision_id,
        page_number=page_no,
        quality=quality,
        coverage=0.0 if quality in {"FAILED", "EMPTY"} else (0.5 if quality == "LOW" else 1.0),
        rotation=rotation,
        source_block_ids=[str(x.get("line_id")) for x in lines if isinstance(x, Mapping) and x.get("line_id")],
        text=text,
        source_file_id=source_file_id,
        page_in_file=page_no,
        table_coverage=table_coverage,
        line_texts=line_texts,
        line_bboxes=line_bboxes,
        source_hash=source_hash,
    )

    issues: list[HandoffIssue] = []
    if quality == "FAILED":
        code = error_code or "AI1_PAGE_FAILED"
        issues.append(HandoffIssue(code=code, message=f"page {page_no}: {code}", review_state=ReviewState.BLOCKED))
    elif quality == "EMPTY":
        issues.append(
            HandoffIssue(
                code="PAGE_BLANK_VERIFIED",
                message=f"page {page_no}: no OCR content",
                review_state=ReviewState.NEEDS_REVIEW,
            )
        )
    elif quality == "LOW":
        issues.append(
            HandoffIssue(
                code="PAGE_PARTIAL",
                message=f"page {page_no}: {', '.join(sorted(warning_set)) or status}",
                review_state=ReviewState.NEEDS_REVIEW,
            )
        )
    if table_coverage == TableCoverage.UNAVAILABLE:
        issues.append(
            HandoffIssue(
                code="TABLE_STRUCTURE_UNAVAILABLE",
                message=f"page {page_no}: AI1 did not provide tables[]",
                review_state=ReviewState.NEEDS_REVIEW,
            )
        )
    elif table_coverage == TableCoverage.UNKNOWN:
        issues.append(
            HandoffIssue(
                code="TABLE_DETECTION_UNKNOWN",
                message=f"page {page_no}: tables[] is empty without a NOT_PRESENT declaration",
                review_state=ReviewState.NEEDS_REVIEW,
            )
        )
    elif table_coverage == TableCoverage.FAILED:
        issues.append(
            HandoffIssue(
                code="TABLE_DETECTION_FAILED",
                message=f"page {page_no}: table detection failed",
                review_state=ReviewState.NEEDS_REVIEW,
            )
        )
    if "table_cells_unavailable" in warning_set:
        issues.append(
            HandoffIssue(
                code="TABLE_CELLS_UNAVAILABLE",
                message=f"page {page_no}: table detected but usable cells were not provided",
                review_state=ReviewState.NEEDS_REVIEW,
            )
        )
    elif "table_geometry_unavailable" in warning_set:
        issues.append(
            HandoffIssue(
                code="TABLE_GEOMETRY_UNAVAILABLE",
                message=f"page {page_no}: table cells have no measurable geometry",
                review_state=ReviewState.NEEDS_REVIEW,
            )
        )

    nodes = _line_nodes(page, lines, page_no=page_no)
    if not nodes and text:
        nodes = [
            StructuralNode(
                node_id=f"page_{page_no}_text",
                type="UNNUMBERED_BLOCK",
                raw_label=text[:120],
                text=text,
                page_range=[page_no],
                page_revision_id=page_revision_id,
                source_file_id=source_file_id,
                page_in_file=page_no,
                status="PARTIAL" if quality != "OK" else "CONFIRMED",
            )
        ]
    tables = _adapt_tables(data.get("tables"), page, page_no=page_no, source_file_id=source_file_id)
    return page, nodes, tables, issues


def _line_nodes(page: PageSnapshot, lines: list[Any], *, page_no: int) -> list[StructuralNode]:
    nodes: list[StructuralNode] = []
    for order, line in enumerate(lines):
        if not isinstance(line, Mapping):
            continue
        raw = str(line.get("raw_text", line.get("text", "")))
        if not raw.strip():
            continue
        line_id = str(line.get("line_id") or f"p{page_no}:line{order}")
        bbox = _bbox(line.get("bbox")) if _has_geometry(line) else []
        normalized = fold_for_match(raw)
        is_clause = bool(re.match(r"^(?:dieu|khoan|diem)\s+\d", normalized))
        nodes.append(
            StructuralNode(
                node_id=f"line:{page_no}:{line_id}",
                type="CLAUSE" if is_clause else "UNNUMBERED_BLOCK",
                raw_label=raw[:160],
                text=raw,
                page_range=[page_no],
                page_revision_id=page.page_revision_id,
                bbox=bbox,
                source_file_id=page.source_file_id,
                page_in_file=page.page_in_file,
                status="PARTIAL" if page.quality != "OK" else "CONFIRMED",
                order=order,
            )
        )
    return nodes


def _adapt_tables(value: Any, page: PageSnapshot, *, page_no: int, source_file_id: str) -> list[TableSnapshot]:
    if not isinstance(value, list):
        return []
    out: list[TableSnapshot] = []
    for table_index, raw_table in enumerate(value):
        if not isinstance(raw_table, Mapping):
            continue
        table_id = str(raw_table.get("table_id") or f"table:p{page_no}:{table_index}")
        raw_cells = raw_table.get("cells") if isinstance(raw_table.get("cells"), list) else []
        cells: list[TableCell] = []
        for cell_index, raw_cell in enumerate(raw_cells):
            if not isinstance(raw_cell, Mapping):
                continue
            try:
                row_index = int(raw_cell.get("row_index", 0))
                column_index = int(raw_cell.get("column_index", raw_cell.get("col_index", 0)))
            except (TypeError, ValueError):
                continue
            if row_index < 0 or column_index < 0:
                continue
            bboxes = _bboxes(raw_cell.get("bbox_fragments", raw_cell.get("bboxes")))
            bbox = _bbox(raw_cell.get("bbox")) or (bboxes[0] if bboxes else [])
            cells.append(
                TableCell(
                    cell_id=str(raw_cell.get("cell_id") or f"{table_id}:cell{cell_index}"),
                    row_index=row_index,
                    column_index=column_index,
                    text=str(raw_cell.get("text", "")),
                    bbox=bbox,
                    bbox_fragments=bboxes,
                    line_ids=[str(x) for x in (raw_cell.get("line_ids") or [])],
                    row_span=int(raw_cell.get("rowspan", 1) or 1),
                    column_span=int(raw_cell.get("colspan", 1) or 1),
                )
            )
        if not cells:
            continue
        rows = _rows_from_cells(cells)
        resolver = CitationResolver([page])
        citations: dict[str, Citation] = {}
        for cell in cells:
            start = page.text.find(cell.text) if cell.text else -1
            citation = Citation(
                citation_id=f"table:{table_id}:{cell.row_index}:{cell.column_index}",
                node_id=table_id,
                page_revision_id=page.page_revision_id,
                bbox=cell.bbox,
                bbox_fragments=cell.bbox_fragments,
                text_span=cell.text,
                source_file_id=page.source_file_id,
                page=page.page_number,
                page_range=[page.page_number],
                line_ids=cell.line_ids,
                char_start=start if start >= 0 else None,
                char_end=(start + len(cell.text)) if start >= 0 else None,
                source_hash=page.source_hash,
                quote_sha256=quote_digest(cell.text),
                geometry_available=bool(cell.bbox or cell.bbox_fragments),
            )
            citation.validation_status = resolver.verify(citation).status
            citations[f"{cell.row_index}:{cell.column_index}"] = citation
        node_id = f"table-node:{page_no}:{table_id}"
        out.append(
            TableSnapshot(
                table_id=table_id,
                title=str(raw_table.get("title", "")),
                header=[str(x) for x in (raw_table.get("header") or [])],
                rows=rows,
                continuation=False,
                node_id=node_id,
                page_revision_id=page.page_revision_id,
                cell_citations=citations,
                cells=cells,
            )
        )
    return out


def _rows_from_cells(cells: list[TableCell]) -> list[list[str | None]]:
    max_row = max(cell.row_index for cell in cells)
    max_col = max(cell.column_index for cell in cells)
    rows: list[list[str | None]] = [[None] * (max_col + 1) for _ in range(max_row + 1)]
    for cell in cells:
        rows[cell.row_index][cell.column_index] = cell.text
    return rows


def fold_for_match(value: str) -> str:
    """Fold case/diacritics for routing while leaving stored raw text intact."""

    text = unicodedata.normalize("NFD", value.casefold())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text.replace("đ", "d")


def _page_quality(status: str, *, text: str, lines: list[Any], warnings: set[str], data: Mapping[str, Any]) -> str:
    if status == "FAILED" or "OCR_ENGINE_UNAVAILABLE" in warnings:
        return "FAILED"
    coverage = data.get("quality", {}).get("coverage_status") if isinstance(data.get("quality"), Mapping) else None
    if coverage == "BLANK_VERIFIED" or (not text.strip() and not lines and not data.get("tables")):
        return "EMPTY"
    if status == "PARTIAL" or warnings.intersection(
        {
            "missing_line_geometry",
            "missing_word_geometry",
            "geometry_unverified",
            "table_cells_unavailable",
            "table_geometry_unavailable",
        }
    ):
        return "LOW"
    return "OK"


def _has_usable_table_cells(tables: list[Any]) -> bool:
    return any(
        isinstance(table, Mapping)
        and isinstance(table.get("cells"), list)
        and any(isinstance(cell, Mapping) and str(cell.get("text", "")).strip() for cell in table["cells"])
        for table in tables
    )


def _has_table_geometry(tables: list[Any]) -> bool:
    for table in tables:
        if not isinstance(table, Mapping):
            continue
        for cell in table.get("cells") or []:
            if not isinstance(cell, Mapping):
                continue
            if _bbox(cell.get("bbox")) or _bboxes(cell.get("bbox_fragments", cell.get("bboxes"))):
                return True
    return False


def _table_coverage(data: Mapping[str, Any], warnings: set[str]) -> TableCoverage:
    raw = data.get("table_coverage", data.get("table_detection"))
    if isinstance(raw, Mapping):
        raw = raw.get("status")
    if isinstance(raw, str):
        try:
            explicit = TableCoverage(raw.upper())
        except ValueError:
            explicit = None
        if explicit is not None:
            if explicit == TableCoverage.NOT_PRESENT and data.get("tables"):
                return TableCoverage.UNKNOWN
            return explicit
    tables = data.get("tables")
    if isinstance(tables, list) and tables:
        return TableCoverage.DETECTED
    if "table_structure_unavailable" in warnings:
        return TableCoverage.UNAVAILABLE
    if "table_detection_failed" in warnings:
        return TableCoverage.FAILED
    return TableCoverage.UNKNOWN


def _aggregate_table_coverage(pages: list[PageSnapshot]) -> str:
    statuses = {page.table_coverage for page in pages}
    if not statuses:
        return TableCoverage.UNKNOWN.value
    if statuses == {TableCoverage.NOT_PRESENT}:
        return TableCoverage.NOT_PRESENT.value
    if TableCoverage.FAILED in statuses:
        return TableCoverage.FAILED.value
    if TableCoverage.UNAVAILABLE in statuses:
        return TableCoverage.UNAVAILABLE.value
    if TableCoverage.DETECTED in statuses:
        return TableCoverage.DETECTED.value
    return TableCoverage.UNKNOWN.value


def _legacy_digest(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _canonical_digest(payload: Mapping[str, Any]) -> str:
    """Return the full bare SHA-256 digest used by the canonical request."""

    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _legacy_page_number(page: Mapping[str, Any], fallback: int) -> int:
    value = page.get("page_number", page.get("page_no", fallback))
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise SnapshotContractError(f"legacy page {fallback}: invalid page_number") from exc
    if number < 1:
        raise SnapshotContractError(f"legacy page {fallback}: page_number must be >= 1")
    return number


def _legacy_lines(text: str, page_no: int) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for index, value in enumerate(text.splitlines(), start=1):
        if not value.strip():
            continue
        lines.append(
            {
                "line_id": f"legacy:p{page_no}:l{index}",
                "raw_text": value,
                "bbox_source": "absent",
                "geometry_status": "absent",
                "words": [],
            }
        )
    return lines


def _page_text(data: Mapping[str, Any], lines: list[Any]) -> str:
    direct = data.get("text", data.get("raw_text"))
    if isinstance(direct, str):
        return direct
    parts = []
    for line in lines:
        if isinstance(line, Mapping):
            raw = line.get("raw_text", line.get("text", ""))
            if raw:
                parts.append(str(raw))
    return "\n".join(parts)


def _warning_codes(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, Mapping) and item.get("code"):
            out.append(str(item["code"]))
        elif isinstance(item, str) and item:
            out.append(item)
    return out


def _error_code(value: Any) -> str:
    if isinstance(value, Mapping):
        return str(value.get("code") or "")
    return str(value or "")


def _snapshot_digest(value: Any) -> str:
    text = str(value)
    return text if text.startswith("sha256:") else f"sha256:{text}"


def _require_mapping(value: Any, name: str) -> None:
    if not isinstance(value, Mapping):
        raise SnapshotContractError(f"{name} must be an object")


def _has_geometry(value: Mapping[str, Any]) -> bool:
    source = value.get("geometry_status")
    return source in {"measured", "derived", "line_only"} and bool(_bbox(value.get("bbox")))


def _bbox(value: Any) -> list[float]:
    if not isinstance(value, list) or len(value) != 4:
        return []
    try:
        return [float(x) for x in value]
    except (TypeError, ValueError):
        return []


def _bboxes(value: Any) -> list[list[float]]:
    if not isinstance(value, list):
        return []
    return [box for item in value if (box := _bbox(item))]


def adapt_to_canonical_ai2_run(
    payload: Mapping[str, Any],
    *,
    segmentation_version: str = "segmentation.v1",
    state_version: int | None = None,
    reviewer_decisions: Mapping[str, str] | None = None,
    user_context: Mapping[str, Any] | None = None,
):
    """Project accepted AI1/AI2 JSON into the P1 domain model.

    This is deliberately a read-only compatibility seam. Existing adapter
    functions and legacy outputs remain unchanged; the import is lazy to keep
    the canonical mapper independent from this boundary module.
    """

    from app.pipeline.canonical import build_canonical_run

    return build_canonical_run(
        payload,
        segmentation_version=segmentation_version,
        state_version=state_version,
        reviewer_decisions=reviewer_decisions,
        user_context=user_context,
    )
