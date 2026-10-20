"""Deterministic mapping from AI1/AI2 JSON into the canonical P1 domain."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from app.contracts.canonical import (
    AI2Run,
    Boundary,
    BoundaryStatus,
    CanonicalCitation,
    Clause,
    DependencyArtifact,
    DependencyGraph,
    DocumentRole,
    EvidenceState,
    Fact,
    Generation,
    InputSnapshot,
    LogicalDocument,
    Party,
    Relation,
    ReviewState,
    clone_source,
)


def build_canonical_run(
    payload: Mapping[str, Any],
    *,
    segmentation_version: str = "segmentation.v1",
    state_version: int | None = None,
    reviewer_decisions: Mapping[str, str] | None = None,
    user_context: Mapping[str, Any] | None = None,
) -> AI2Run:
    """Map one input JSON, including an optional multi-document envelope.

    The mapper is intentionally tolerant of legacy-compatible shapes.  It
    never treats an unresolved ref as evidence and never serializes
    ``user_context`` into any evidence-bearing object.
    """

    if not isinstance(payload, Mapping):
        raise TypeError("canonical input must be an object")
    raw_payload = clone_source(dict(payload))
    snapshot_id = str(payload.get("input_snapshot_id") or payload.get("snapshot_id") or _digest(payload)[:24])
    schema_version = str(payload.get("schema_version") or "ai2.canonical.input.v1")
    effective_state_version = int(state_version if state_version is not None else payload.get("state_version", 0))
    documents_payload = _documents_payload(payload)
    documents: list[LogicalDocument] = []
    all_refs: set[str] = set()
    ref_text: dict[str, str] = {}
    quality_flags: set[str] = set()

    manifest_roles = _manifest_roles(payload)
    for index, source in enumerate(documents_payload):
        document_id = str(source.get("document_id") or source.get("id") or f"document-{index + 1}")
        role = _role(source.get("role") or source.get("document_role") or manifest_roles.get(document_id))
        source_refs, source_text, document_flags = _source_index(source)
        all_refs.update(source_refs)
        ref_text.update(source_text)
        quality_flags.update(document_flags)

        boundaries = _boundaries(source, document_id, source_refs, document_flags)
        quality_flags.update(flag for boundary in boundaries for flag in boundary.quality_flags)
        local_parties = [_party(item) for item in _list(source.get("parties"))]
        local_clauses = [_clause(item, document_id) for item in _list(source.get("clauses"))]
        documents.append(
            LogicalDocument(
                document_id=document_id,
                role=role,
                raw_source=clone_source(source.get("raw_source") or source.get("source") or source),
                source_refs=sorted(source_refs),
                boundaries=boundaries,
                parties=local_parties,
                clauses=local_clauses,
            )
        )

    boundaries = [boundary for document in documents for boundary in document.boundaries]
    parties = [party for document in documents for party in document.parties]
    clauses = [clause for document in documents for clause in document.clauses]
    if documents:
        # Clauses/parties may be supplied at envelope scope by compatibility
        # inputs. Attach them to the first logical document without changing
        # the raw source or inventing cross-document ownership.
        documents[0].clauses.extend(
            _clause(item, documents[0].document_id)
            for item in _list(payload.get("clauses"))
            if isinstance(item, Mapping)
        )
        documents[0].parties.extend(
            _party(item)
            for item in _list(payload.get("parties"))
            if isinstance(item, Mapping)
        )
        clauses = [clause for document in documents for clause in document.clauses]
        parties = [party for document in documents for party in document.parties]
    fact_payloads = [item for item in _list(payload.get("facts")) if isinstance(item, Mapping)]
    fact_payloads.extend(
        item
        for source in documents_payload
        for item in _list(source.get("facts"))
        if isinstance(item, Mapping)
    )
    facts = [_fact(item, all_refs, ref_text) for item in fact_payloads]
    relations = [
        _relation(item, all_refs, reviewer_decisions or {}, payload.get("review_decisions"))
        for item in _list(payload.get("relations"))
    ]
    quality_flags.update(_clause_flags(clauses))
    quality_flags.update(_relation_flags(relations))
    if any(fact.evidence_state != EvidenceState.VERIFIED for fact in facts):
        quality_flags.add("MISSING_EVIDENCE")
    if any(relation.evidence_state != EvidenceState.VERIFIED for relation in relations):
        quality_flags.add("UNVERIFIED_RELATION")

    generation = Generation(
        generation_id=str(
            payload.get("generation_id")
            or f"generation:{snapshot_id}:{segmentation_version}:{effective_state_version}"
        ),
        input_snapshot_id=snapshot_id,
        segmentation_version=segmentation_version,
        state_version=effective_state_version,
    )
    dependencies = _dependencies(snapshot_id, boundaries, facts, relations, generation)
    review_state = (
        ReviewState.NEEDS_REVIEW
        if quality_flags or any(boundary.status == BoundaryStatus.AMBIGUOUS for boundary in boundaries)
        else ReviewState.PASS
    )
    return AI2Run(
        run_id=str(payload.get("run_id") or f"run:{snapshot_id}"),
        input_snapshot=InputSnapshot(
            snapshot_id=snapshot_id,
            schema_version=schema_version,
            raw_source=raw_payload,
        ),
        documents=documents,
        boundaries=boundaries,
        parties=parties,
        clauses=clauses,
        facts=facts,
        relations=relations,
        generation=generation,
        dependencies=dependencies,
        quality_flags=sorted(quality_flags),
        review_state=review_state,
        user_context=clone_source(dict(user_context)) if user_context is not None else None,
    )


def _documents_payload(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    logical = payload.get("logical_documents")
    if isinstance(logical, list) and logical:
        return [item for item in logical if isinstance(item, Mapping)]
    snapshots = payload.get("snapshots")
    if isinstance(snapshots, list) and snapshots:
        return [item for item in snapshots if isinstance(item, Mapping)]
    documents = payload.get("documents")
    if isinstance(documents, list) and documents:
        return [item for item in documents if isinstance(item, Mapping)]
    return [payload]


def _manifest_roles(payload: Mapping[str, Any]) -> dict[str, str]:
    manifest = payload.get("manifest")
    if not isinstance(manifest, Mapping):
        return {}
    return {
        str(item.get("document_id")): str(item.get("role"))
        for item in _list(manifest.get("documents"))
        if isinstance(item, Mapping) and item.get("document_id")
    }


def _role(value: Any) -> DocumentRole:
    normalized = str(value or "unknown").strip().casefold()
    if normalized in {"body", "contract", "main"}:
        return DocumentRole.BODY
    if normalized in {"annex", "appendix", "phụ lục", "phu luc"}:
        return DocumentRole.ANNEX
    return DocumentRole.UNKNOWN


def _source_index(source: Mapping[str, Any]) -> tuple[set[str], dict[str, str], set[str]]:
    refs: set[str] = set()
    text_by_ref: dict[str, str] = {}
    flags: set[str] = set()
    pages = _list(source.get("pages"))
    for page_index, page in enumerate(pages, start=1):
        if not isinstance(page, Mapping):
            continue
        page_id = str(page.get("page_id") or page.get("page_revision_id") or f"page-{page_index}")
        refs.add(page_id)
        text_by_ref[page_id] = str(page.get("text") or page.get("raw_text") or "")
        language = page.get("language") or page.get("languages")
        if isinstance(language, (list, tuple)) and len(language) > 1:
            flags.add("BILINGUAL")
        elif isinstance(language, str) and ("/" in language or "," in language or " and " in language.casefold()):
            flags.add("BILINGUAL")
        for block_index, block in enumerate(_list(page.get("blocks") or page.get("lines")), start=1):
            if not isinstance(block, Mapping):
                continue
            block_id = str(block.get("block_id") or block.get("line_id") or f"{page_id}:block-{block_index}")
            refs.add(block_id)
            text_by_ref[block_id] = str(block.get("text") or block.get("raw_text") or "")
        for table_index, table in enumerate(_list(page.get("tables")), start=1):
            if not isinstance(table, Mapping):
                continue
            table_id = str(table.get("table_id") or f"{page_id}:table-{table_index}")
            refs.add(table_id)
            if table.get("continuation") or table.get("is_continuation"):
                flags.add("TABLE_CONTINUATION")
    for table in _list(source.get("tables")):
        if isinstance(table, Mapping) and (table.get("continuation") or table.get("is_continuation")):
            flags.add("TABLE_CONTINUATION")
    return refs, text_by_ref, flags


def _boundaries(
    source: Mapping[str, Any],
    document_id: str,
    source_refs: set[str],
    document_flags: set[str],
) -> list[Boundary]:
    supplied = _list(source.get("boundaries"))
    if not supplied and source_refs:
        supplied = [
            {
                "boundary_id": f"boundary:{document_id}:1",
                "evidence_refs": sorted(source_refs),
                "confidence": 1.0,
                "status": "PROPOSED",
            }
        ]
    result: list[Boundary] = []
    for index, item in enumerate(supplied, start=1):
        if not isinstance(item, Mapping):
            continue
        evidence_refs = [str(ref) for ref in _list(item.get("evidence_refs"))]
        confidence = float(item.get("confidence", 0.0))
        flags = [str(flag) for flag in _list(item.get("quality_flags"))]
        if any(ref not in source_refs for ref in evidence_refs):
            flags.append("MISSING_EVIDENCE")
        if confidence < 0.8 or str(item.get("status", "")).upper() == "AMBIGUOUS":
            flags.append("LOW_CONFIDENCE_BOUNDARY")
        requested_status = str(item.get("status", "PROPOSED")).upper()
        if "MISSING_EVIDENCE" in flags and requested_status == "CONFIRMED":
            requested_status = "AMBIGUOUS"
        result.append(
            Boundary(
                boundary_id=str(item.get("boundary_id") or f"boundary:{document_id}:{index}"),
                document_id=document_id,
                start_ref=str(item["start_ref"]) if item.get("start_ref") is not None else None,
                end_ref=str(item["end_ref"]) if item.get("end_ref") is not None else None,
                evidence_refs=evidence_refs,
                confidence=max(0.0, min(1.0, confidence)),
                status=BoundaryStatus(requested_status),
                quality_flags=sorted(set(flags)),
            )
        )
    return result


def _party(item: Mapping[str, Any]) -> Party:
    return Party(
        party_id=str(item.get("party_id") or item.get("id") or "party:unknown"),
        name=str(item.get("name") or item.get("label") or ""),
        role=str(item["role"]) if item.get("role") is not None else None,
        evidence_refs=[str(ref) for ref in _list(item.get("evidence_refs"))],
    )


def _clause(item: Mapping[str, Any], document_id: str) -> Clause:
    flags = ["TRUNCATED"] if item.get("truncated") else []
    text = str(item.get("text") or item.get("raw_text") or "")
    if text.rstrip().endswith(("…", "...")) and "TRUNCATED" not in flags:
        flags.append("TRUNCATED")
    return Clause(
        clause_id=str(item.get("clause_id") or item.get("id") or f"clause:{document_id}:unknown"),
        document_id=document_id,
        text=text,
        evidence_refs=[str(ref) for ref in _list(item.get("evidence_refs"))],
        quality_flags=flags,
    )


def _fact(item: Mapping[str, Any], refs: set[str], text_by_ref: dict[str, str]) -> Fact:
    evidence_refs = [str(ref) for ref in _list(item.get("evidence_refs"))]
    citations = [_citation(citation, refs, text_by_ref) for citation in _list(item.get("citations")) if isinstance(citation, Mapping)]
    all_refs_valid = bool(evidence_refs) and all(ref in refs for ref in evidence_refs)
    citations_valid = all(citation.status == "VALID" for citation in citations)
    verified = all_refs_valid and citations_valid
    if not evidence_refs or not any(ref in refs for ref in evidence_refs):
        evidence_state = EvidenceState.UNVERIFIABLE
    elif not all_refs_valid or not citations_valid:
        evidence_state = EvidenceState.INSUFFICIENT_EVIDENCE
    else:
        evidence_state = EvidenceState.VERIFIED
    return Fact(
        fact_id=str(item.get("fact_id") or item.get("id") or "fact:unknown"),
        value=str(item.get("value") if item.get("value") is not None else item.get("raw_value") or ""),
        evidence_refs=evidence_refs,
        citations=citations,
        evidence_state=evidence_state,
        review_state=ReviewState.PASS if verified else ReviewState.NEEDS_REVIEW,
    )


def _citation(item: Mapping[str, Any], refs: set[str], text_by_ref: dict[str, str]) -> CanonicalCitation:
    evidence_ref = str(item.get("evidence_ref") or item.get("ref") or "")
    quote = str(item.get("text") or item.get("quote") or "")
    status = "VALID" if evidence_ref in refs and (not quote or quote in text_by_ref.get(evidence_ref, "")) else "MISMATCH" if evidence_ref in refs else "MISSING"
    return CanonicalCitation(evidence_ref=evidence_ref, text=quote, status=status)


def _relation(
    item: Mapping[str, Any],
    refs: set[str],
    reviewer_decisions: Mapping[str, str],
    inline_decisions: Any,
) -> Relation:
    relation_id = str(item.get("relation_id") or item.get("id") or "relation:unknown")
    decision = str(reviewer_decisions.get(relation_id) or item.get("review_decision") or _inline_decision(inline_decisions, relation_id) or "").upper()
    evidence_refs = [str(ref) for ref in _list(item.get("evidence_refs"))]
    evidence_valid = bool(evidence_refs) and all(ref in refs for ref in evidence_refs)
    confirmed = evidence_valid or decision in {"CONFIRMED", "APPROVED", "ACCEPTED", "CONFIRM"}
    return Relation(
        relation_id=relation_id,
        relation_type=str(item.get("type") or item.get("relation_type") or "UNKNOWN"),
        from_ref=str(item["from_ref"]) if item.get("from_ref") is not None else None,
        to_ref=str(item["to_ref"]) if item.get("to_ref") is not None else None,
        from_document_id=str(item["from_document_id"]) if item.get("from_document_id") is not None else None,
        to_document_id=str(item["to_document_id"]) if item.get("to_document_id") is not None else None,
        evidence_refs=evidence_refs,
        evidence_state=EvidenceState.VERIFIED if confirmed else EvidenceState.INSUFFICIENT_EVIDENCE,
        review_state=ReviewState.PASS if confirmed else ReviewState.NEEDS_REVIEW,
    )


def _dependencies(
    snapshot_id: str,
    boundaries: list[Boundary],
    facts: list[Fact],
    relations: list[Relation],
    generation: Generation,
) -> DependencyGraph:
    artifacts: dict[str, DependencyArtifact] = {
        f"input:{snapshot_id}": DependencyArtifact(artifact_id=f"input:{snapshot_id}", kind="input"),
    }
    for boundary in boundaries:
        artifacts[f"boundary:{boundary.boundary_id}"] = DependencyArtifact(
            artifact_id=f"boundary:{boundary.boundary_id}", kind="boundary", depends_on=[f"input:{snapshot_id}"]
        )
    for fact in facts:
        artifacts[f"fact:{fact.fact_id}"] = DependencyArtifact(
            artifact_id=f"fact:{fact.fact_id}", kind="fact", depends_on=[f"input:{snapshot_id}"]
        )
    for relation in relations:
        artifacts[f"relation:{relation.relation_id}"] = DependencyArtifact(
            artifact_id=f"relation:{relation.relation_id}", kind="relation", depends_on=[f"input:{snapshot_id}"]
        )
    derived = [
        artifact_id
        for artifact_id, artifact in artifacts.items()
        if artifact.kind in {"boundary", "fact", "relation"}
    ]
    artifacts[f"generation:{snapshot_id}"] = DependencyArtifact(
        artifact_id=f"generation:{snapshot_id}", kind="generation", depends_on=derived or [f"input:{snapshot_id}"]
    )
    return DependencyGraph(artifacts=artifacts)


def _relation_flags(relations: list[Relation]) -> set[str]:
    return {"UNVERIFIED_RELATION"} if any(item.review_state != ReviewState.PASS for item in relations) else set()


def _clause_flags(clauses: list[Clause]) -> set[str]:
    return {"TRUNCATED_CLAUSE"} if any("TRUNCATED" in item.quality_flags for item in clauses) else set()


def _inline_decision(value: Any, relation_id: str) -> str | None:
    if isinstance(value, Mapping):
        candidate = value.get(relation_id)
        return str(candidate) if candidate is not None else None
    return None


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _digest(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = ["build_canonical_run"]
