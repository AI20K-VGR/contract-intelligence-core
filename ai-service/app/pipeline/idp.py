from __future__ import annotations

from uuid import uuid4

from app.contracts.models import (
    ContractEvent,
    EvidenceIssue,
    HandoffIssue,
    JobResult,
    JobStatus,
    ModelDisposition,
    ObjectRoute,
    ReviewItem,
    ReviewState,
    ToolEnvelope,
    ValidatedHandoff,
    ContractContext,
)
from app.llm.client import NineRouterClient
from app.pipeline.ai1_snapshot_adapter import fold_for_match
from app.pipeline.candidate import CandidatePairer
from app.pipeline.compare import annex_keys_from_labels
from app.pipeline.contract_context import build_contract_context
from app.pipeline.contract_events import extract_contract_events
from app.pipeline.clause import ClauseChunker
from app.pipeline.fact import FactExtractor
from app.pipeline.handoff import HandoffValidator
from app.pipeline.index import IndexStore
from app.pipeline.router import ObjectRouter
from app.pipeline.citations import CitationResolver
from app.pipeline.table import TableExtractionError, TablePipeline
from app.pipeline.units import plan_units
from app.pipeline.runtime import ProcessingRuntime, ProcessingTimeout
from app.reasoning.relations import build_relation_graph
from app.tools.gateway import ToolBlocked, ToolGateway
from app.tools.store import DossierRecord, InMemorySnapshotStore


def run_idp(
    record: DossierRecord,
    envelope: ToolEnvelope,
    *,
    llm: NineRouterClient | None = None,
    store: InMemorySnapshotStore | None = None,
    index: IndexStore | None = None,
    job_id: str | None = None,
    runtime: ProcessingRuntime | None = None,
) -> JobResult:
    job_id = job_id or f"job_{uuid4().hex[:10]}"
    runtime = runtime or ProcessingRuntime(
        egress_allowed=record.egress_approved,
        max_llm_calls=20 if llm is not None else 0,
    )
    try:
        runtime.checkpoint()
    except ProcessingTimeout:
        return _failed_result(job_id, [], "PROCESSING_TIMEOUT", "processing time budget exceeded")
    policy_issues: list[HandoffIssue] = []
    if record.index_status == "LEASED":
        policy_issues.append(
            HandoffIssue(code="INDEX_LEASED", message="index lease is not owned by this job", review_state=ReviewState.BLOCKED)
        )
    # Deterministic local extraction may still produce a bounded partial
    # proposal for operator review. External LLM work is fail-closed when the
    # budget is exhausted; vector recall has its own equivalent gate. Keep the
    # issue on the result, but downgrade extraction to local-only instead of
    # failing the whole handoff.
    if record.processing_budget_hit() and llm is not None:
        policy_issues.append(
            HandoffIssue(code="BUDGET_EXCEEDED", message="processing budget exceeded; local partial extraction only", review_state=ReviewState.NEEDS_REVIEW)
        )
        llm = None
    if not record.egress_approved and llm is not None:
        policy_issues.append(
            HandoffIssue(code="EGRESS_DENIED", message="external model access is not approved", review_state=ReviewState.BLOCKED)
        )
    if any(issue.review_state == ReviewState.BLOCKED for issue in policy_issues):
        return JobResult(
            job_id=job_id,
            status=JobStatus.FAILED,
            review_state=ReviewState.BLOCKED,
            handoff_issues=policy_issues,
        )
    validator = HandoffValidator()
    handoff: ValidatedHandoff = validator.validate(
        tenant_id=record.tenant_id,
        dossier_id=record.dossier_id,
        pins=record.pins,
        pages=record.pages,
        nodes=record.evidence_nodes(),
        tables=record.tables,
        profile=record.profile,
        lifecycle=record.lifecycle,
    )
    if policy_issues:
        handoff.issues = [*policy_issues, *handoff.issues]
    if record.handoff_issues:
        handoff.issues = [*record.handoff_issues, *handoff.issues]
        handoff.blocked = handoff.blocked or any(
            issue.review_state == ReviewState.BLOCKED for issue in record.handoff_issues
        )
    if handoff.blocked:
        return JobResult(
            job_id=job_id,
            status=JobStatus.FAILED,
            review_state=ReviewState.BLOCKED,
            handoff_issues=handoff.issues,
        )

    record.relation_graph = build_relation_graph(record)

    mem = store or InMemorySnapshotStore()
    mem.put(record)
    gateway = ToolGateway(mem)
    try:
        router = ObjectRouter(gateway)
        outline = router.scout(envelope)
    except ToolBlocked:
        return JobResult(
            job_id=job_id,
            status=JobStatus.FAILED,
            review_state=ReviewState.BLOCKED,
            handoff_issues=handoff.issues,
        )

    # Keep long-document processing bounded and resumable.  The current demo
    # still runs synchronously, but every extraction item is associated with a
    # deterministic page unit so a worker can checkpoint it later without
    # constructing a dossier-sized prompt.
    units = plan_units(record)
    unit_order = {
        node_id: index
        for index, unit in enumerate(units)
        for node_id in unit.node_ids
    }
    outline = sorted(
        outline,
        key=lambda item: (unit_order.get(item.get("node_id"), len(units)), item.get("node_id", "")),
    )

    if record.input_facts is None:
        record.input_facts = [fact.model_copy(deep=True) for fact in record.facts]
    facts = [fact.model_copy(deep=True) for fact in record.input_facts]
    source_fact_node_ids = {
        fact.citation.node_id
        for fact in facts
        if fact.citation and fact.citation.node_id
    }
    fact_ex = FactExtractor(gateway, llm, runtime=runtime)
    table_ex = TablePipeline(gateway, llm, runtime=runtime)
    unit_failures: list[HandoffIssue] = []
    extraction_units = 0
    successful_extractions = 0
    for node in outline:
        try:
            runtime.checkpoint()
            route = router.route_node(node)
            if route == ObjectRoute.FIELD:
                extraction_units += 1
                if node["node_id"] not in source_fact_node_ids:
                    facts.append(fact_ex.extract(envelope, node["node_id"], record.profile))
                successful_extractions += 1
            elif route == ObjectRoute.TABLE:
                extraction_units += 1
                facts.extend(table_ex.extract(envelope, _table_id_for(record, node["node_id"])))
                successful_extractions += 1
        except ProcessingTimeout:
            return _failed_result(job_id, handoff.issues, "PROCESSING_TIMEOUT", "processing time budget exceeded")
        except ToolBlocked:
            unit_failures.append(HandoffIssue(
                code="TOOL_BLOCKED",
                message=f"unit for node {node.get('node_id')}: snapshot tool access was blocked",
                review_state=ReviewState.NEEDS_REVIEW,
                stage="EXTRACT",
                location=str(node.get("node_id") or ""),
                retryable=True,
            ))
            continue
        except TableExtractionError as exc:
            unit_failures.append(HandoffIssue(
                code="TABLE_EXTRACTION_FAILED",
                message=f"unit for node {node.get('node_id')}: {exc}",
                review_state=ReviewState.NEEDS_REVIEW,
                stage="EXTRACT",
                location=str(node.get("node_id") or ""),
                retryable=True,
            ))
            continue
        except Exception as exc:
            unit_failures.append(HandoffIssue(
                code="EXTRACTION_FAILED",
                message=f"unit for node {node.get('node_id')}: {type(exc).__name__}: {exc}",
                review_state=ReviewState.NEEDS_REVIEW,
                stage="EXTRACT",
                location=str(node.get("node_id") or ""),
                retryable=False,
            ))
            continue
    handoff.issues.extend(unit_failures)
    if extraction_units and not successful_extractions and unit_failures:
        first = unit_failures[0]
        return _failed_result(job_id, handoff.issues, first.code, first.message)
    chunks = ClauseChunker().chunk(handoff)
    events: list[ContractEvent] = extract_contract_events(record)
    _downgrade_unreliable_outputs(facts, chunks, handoff)
    annex_labels = annex_keys_from_labels(
        {
            (n.get("raw_label") or "").strip()
            for n in outline
            if fold_for_match(n.get("raw_label") or "").startswith("phu luc")
        }
    )
    # OCR-lab may keep an embedded annex heading only in page lines, while
    # the reconstructed outline attaches its text to the preceding clause.
    # Carry that explicit page-level label into candidate missing-annex checks.
    for page in record.pages:
        for line in page.line_texts.values():
            if fold_for_match(line).lstrip().startswith("phu luc"):
                annex_labels.update(annex_keys_from_labels({line}))
    relation_pairs = {
        tuple(sorted((edge.from_node_id, edge.to_node_id)))
        for edge in (record.relation_graph.edges if record.relation_graph else [])
        if edge.relation_type.value in {"SAME_CLAUSE", "REFERENCES", "AMENDS"}
    }
    pairer = CandidatePairer()
    candidates, issues = pairer.pair_with_issues(
        facts,
        annex_labels=annex_labels,
        relation_pairs=relation_pairs,
    )
    issues = [*record.relation_graph.issues, *issues] if record.relation_graph else issues
    issues.extend(_runtime_issues(runtime))
    issues.extend(_validate_output_citations(record, facts, candidates, events))
    context_tables = set()
    for fact in facts:
        table_id = fact.citation.table_id
        if table_id and not fact.item_key and table_id not in context_tables:
            context_tables.add(table_id)
            issues.append(EvidenceIssue(
                issue_id=f"table-context:{table_id}",
                missing="TABLE_COMPARISON_CONTEXT",
                reason="Table amounts are extracted, but no authoritative item/context mapping supports cross-source comparison; zero findings does not mean consistency.",
                citation=fact.citation,
                review_state=ReviewState.NEEDS_REVIEW,
            ))
    _downgrade_uncertain_candidates(candidates, facts)
    contract_context: ContractContext = build_contract_context(record, candidates=candidates, facts=facts)
    context_issues = [
        EvidenceIssue(
            issue_id=f"contract-context:{finding.finding_id}",
            missing=f"CONTRACT_CONTEXT_{finding.kind}",
            reason=finding.reason,
            citation=finding.citations[0] if finding.citations else None,
            review_state=finding.review_state,
        )
        for finding in contract_context.findings
        if finding.review_state != ReviewState.PASS
    ]
    issues.extend(context_issues)
    store_idx = index or IndexStore()
    contrib = store_idx.propose(
        facts=facts,
        chunks=chunks,
        candidates=candidates,
        evidence_issues=issues,
        contract_context=contract_context,
        events=events,
        coverage={
            "n_facts": len(facts),
            "n_findings": len(candidates) + len(contract_context.findings),
            "n_candidate_findings": len(candidates),
            "n_context_findings": len(contract_context.findings),
            "n_events": len(events),
            "n_evidence_issues": len(issues),
            "n_units": len(units),
            "unit_ids": [unit.unit_id for unit in units],
            "annex_labels": sorted(annex_labels),
            "runtime": runtime.snapshot(),
        },
        extraction_version=record.pins.extraction_version,
        proposed_index_version=f"idx_{record.pins.extraction_version}",
    )
    record.facts = facts
    record.chunks = chunks
    record.events = events
    record.review_items = _review_items_for_result(record, issues, candidates)
    existing_review_ids = {item.review_item_id for item in record.review_items}
    for fact in facts:
        item_id = f"review:fact:{fact.fact_id}"
        if fact.review_state != ReviewState.PASS and item_id not in existing_review_ids:
            record.review_items.append(ReviewItem(
                review_item_id=item_id, kind="FACT", reason="Verify missing/uncertain value and its source context",
                review_state=fact.review_state, proposed_action="VERIFY_EVIDENCE",
                citation_ids=[fact.citation.citation_id] if fact.citation.citation_id else [],
            ))
            existing_review_ids.add(item_id)
    mem.put(record)

    worst = ReviewState.PASS
    for issue in handoff.issues:
        if issue.review_state == ReviewState.NEEDS_REVIEW:
            worst = ReviewState.NEEDS_REVIEW
    for f in facts:
        if f.review_state in {ReviewState.NEEDS_REVIEW, ReviewState.INSUFFICIENT_EVIDENCE}:
            worst = ReviewState.NEEDS_REVIEW
    if issues:
        worst = ReviewState.NEEDS_REVIEW
    return JobResult(
        job_id=job_id,
        status=JobStatus.SUCCEEDED,
        review_state=worst,
        handoff_issues=handoff.issues,
        contribution=contrib,
    )


def _table_id_for(record: DossierRecord, node_id: str) -> str:
    for t in record.tables:
        if t.node_id == node_id or t.table_id == node_id:
            return t.table_id
    return node_id


def _runtime_issues(runtime: ProcessingRuntime) -> list[EvidenceIssue]:
    return [
        EvidenceIssue(
            issue_id=f"runtime:{code}",
            missing=code,
            reason=message,
            review_state=ReviewState.NEEDS_REVIEW,
        )
        for code, message in runtime.issues
    ]


def _validate_output_citations(record: DossierRecord, facts, candidates, events=None) -> list[EvidenceIssue]:
    """Verify emitted evidence without inventing or repairing source geometry."""

    resolver = CitationResolver(record.pages, record.tables)
    issues: list[EvidenceIssue] = []
    seen: set[tuple[str, str]] = set()

    def check(owner: str, citation) -> None:
        result = resolver.verify(citation)
        citation.validation_status = result.status
        if result.valid:
            return
        dedupe_owner = str(citation.citation_id or citation.node_id)
        if citation.node_id.startswith("table-node:") and result.status == "UNVERIFIED" and not citation.line_ids:
            # One review item per table is enough when AI1 supplied table cells
            # but no OCR line text/offsets. Keep every fact citation attached;
            # only the operator queue is deduplicated.
            dedupe_owner = citation.node_id
        key = (dedupe_owner, result.status)
        if key in seen:
            return
        seen.add(key)
        issue_id = f"citation:{citation.citation_id or citation.node_id}:{result.status}"
        issues.append(
            EvidenceIssue(
                issue_id=issue_id,
                missing="CITATION_VERIFICATION",
                reason=f"{owner}: {result.reason}",
                citation=citation,
                review_state=ReviewState.NEEDS_REVIEW,
            )
        )

    for fact in facts:
        check(f"fact:{fact.fact_id}", fact.citation)
        if fact.citation.validation_status != "VALID":
            fact.review_state = ReviewState.NEEDS_REVIEW
    for candidate in candidates:
        for citation in [*candidate.evidence_left, *candidate.evidence_right]:
            check(f"finding:{candidate.candidate_id}", citation)
            if citation.validation_status != "VALID":
                candidate.review_state = ReviewState.NEEDS_REVIEW
    for event in events or []:
        check(f"event:{event.event_id}", event.citation)
        if event.citation.validation_status != "VALID":
            event.review_state = ReviewState.NEEDS_REVIEW
    return issues


def _failed_result(
    job_id: str,
    existing: list[HandoffIssue],
    code: str,
    message: str,
) -> JobResult:
    return JobResult(
        job_id=job_id,
        status=JobStatus.FAILED,
        review_state=ReviewState.NEEDS_REVIEW,
        handoff_issues=[
            *existing,
            HandoffIssue(code=code, message=message, review_state=ReviewState.NEEDS_REVIEW),
        ],
    )


def _review_items_for_result(record: DossierRecord, issues, candidates) -> list[ReviewItem]:
    """Materialize an explicit HITL queue from pipeline uncertainty.

    A zero-length queue is meaningful only after this function has run. The
    API exposes the job state separately so the UI can distinguish NOT_RUN
    from EMPTY_QUEUE.
    """

    items = list(record.review_items)
    seen = {item.review_item_id for item in items}
    for index, issue in enumerate([*record.handoff_issues, *issues], start=1):
        code = str(getattr(issue, "code", None) or getattr(issue, "issue_id", None) or "EVIDENCE_ISSUE")
        message = str(getattr(issue, "message", None) or getattr(issue, "reason", None) or getattr(issue, "missing", None) or code)
        review_state = getattr(issue, "review_state", ReviewState.NEEDS_REVIEW)
        citation = getattr(issue, "citation", None)
        item_id = f"review:{code}:{index}"
        if item_id in seen:
            continue
        items.append(
            ReviewItem(
                review_item_id=item_id,
                kind=code,
                reason=message,
                review_state=review_state,
                proposed_action="VERIFY_EVIDENCE" if review_state != ReviewState.BLOCKED else "FIX_INPUT",
                citation_ids=[citation.citation_id] if citation and citation.citation_id else [],
            )
        )
        seen.add(item_id)
    for candidate in candidates:
        if candidate.review_state not in {ReviewState.NEEDS_REVIEW, ReviewState.INSUFFICIENT_EVIDENCE, ReviewState.BLOCKED}:
            continue
        item_id = f"review:candidate:{candidate.candidate_id}"
        if item_id in seen:
            continue
        citation_ids = [
            citation.citation_id
            for citation in [*candidate.evidence_left, *candidate.evidence_right]
            if citation.citation_id
        ]
        items.append(
            ReviewItem(
                review_item_id=item_id,
                kind="CANDIDATE",
                reason=candidate.reason or candidate.finding_type.value,
                review_state=candidate.review_state,
                candidate_id=candidate.candidate_id,
                citation_ids=citation_ids,
                proposed_action="REVIEW_COMPARISON",
            )
        )
    return items


def _downgrade_unreliable_outputs(facts, chunks, handoff: ValidatedHandoff) -> None:
    bad_revisions = {
        page.page_revision_id
        for page in handoff.pages
        if page.quality != "OK"
    }
    bad_page_numbers = {
        page.page_number
        for page in handoff.pages
        if page.quality != "OK"
    }
    uncertain_nodes = {
        node.node_id
        for node in handoff.nodes
        if node.status != "CONFIRMED"
    }
    for fact in facts:
        if fact.review_state == ReviewState.BLOCKED:
            continue
        if (
            not fact.citation.page_revision_id
            or fact.citation.page_revision_id in bad_revisions
            or fact.citation.node_id in uncertain_nodes
        ):
            fact.review_state = ReviewState.NEEDS_REVIEW
    by_id = {node.node_id: node for node in handoff.nodes}
    for chunk in chunks:
        node = by_id.get(chunk.parent_node_id)
        if (
            node is None
            or node.status != "CONFIRMED"
            or node.page_revision_id in bad_revisions
            or any(page in bad_page_numbers for page in chunk.page_range)
        ):
            chunk.review_state = ReviewState.NEEDS_REVIEW


def _downgrade_uncertain_candidates(candidates, facts) -> None:
    by_id = {fact.fact_id: fact for fact in facts}
    for candidate in candidates:
        left = by_id.get(candidate.left_id)
        right = by_id.get(candidate.right_id)
        if not left or not right:
            continue
        if left.review_state == ReviewState.INSUFFICIENT_EVIDENCE or right.review_state == ReviewState.INSUFFICIENT_EVIDENCE:
            candidate.review_state = ReviewState.INSUFFICIENT_EVIDENCE
            candidate.model_disposition = ModelDisposition.INCOMPLETE
        elif left.review_state != ReviewState.PASS or right.review_state != ReviewState.PASS:
            candidate.review_state = ReviewState.NEEDS_REVIEW
            candidate.model_disposition = ModelDisposition.INCOMPLETE
