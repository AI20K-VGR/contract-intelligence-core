from __future__ import annotations

import os
from typing import TYPE_CHECKING
from uuid import uuid4

from app.contracts.models import (
    ContractContext,
    ContractEvent,
    Disposition,
    EvidenceIssue,
    FindingType,
    HandoffIssue,
    JobResult,
    JobStatus,
    ModelDisposition,
    ObjectRoute,
    ReviewItem,
    ReviewState,
    ToolEnvelope,
    ValidatedHandoff,
)
from app.llm.client import NineRouterClient

if TYPE_CHECKING:
    from app.contracts.contract_graph import PairResult
from app.pipeline.ai1_snapshot_adapter import fold_for_match
from app.pipeline.candidate import CandidatePairer
from app.pipeline.citations import CitationResolver
from app.pipeline.clause import ClauseChunker
from app.pipeline.clause_compare import compare_clauses_across_files
from app.pipeline.compare import annex_keys_from_labels
from app.pipeline.contract_context import build_contract_context
from app.pipeline.contract_events import extract_contract_events
from app.pipeline.edge_flags import dossier_edge_issues
from app.pipeline.fact import FactExtractor
from app.pipeline.frame_context import build_semantic_extension, effective_context_bounds
from app.pipeline.handoff import HandoffValidator
from app.pipeline.index import IndexStore
from app.pipeline.router import ObjectRouter
from app.pipeline.runtime import (
    ISSUE_MESSAGES_VI,
    TERMINATION_CODES,
    ProcessingRuntime,
    ProcessingTimeout,
)
from app.pipeline.table import TableExtractionError, TablePipeline
from app.pipeline.units import plan_units
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
    trace_writer=None,
) -> JobResult:
    job_id = job_id or f"job_{uuid4().hex[:10]}"
    runtime = runtime or ProcessingRuntime(
        egress_allowed=record.egress_approved,
        max_llm_calls=20 if llm is not None else 0,
    )
    # Past the deadline the job ends here, wherever it was: a run nobody waits for must
    # not keep its memory (#113).
    try:
        return _run_idp(
            record,
            envelope,
            llm=llm,
            store=store,
            index=index,
            job_id=job_id,
            runtime=runtime,
            trace_writer=trace_writer,
        )
    except ProcessingTimeout:
        return _failed_result(
            job_id, [], "PROCESSING_TIMEOUT", ISSUE_MESSAGES_VI["PROCESSING_TIMEOUT"]
        )


def _run_idp(
    record: DossierRecord,
    envelope: ToolEnvelope,
    *,
    llm: NineRouterClient | None,
    store: InMemorySnapshotStore | None,
    index: IndexStore | None,
    job_id: str,
    runtime: ProcessingRuntime,
    trace_writer,
) -> JobResult:
    try:
        runtime.checkpoint()
    except ProcessingTimeout:
        return _failed_result(
            job_id, [], "PROCESSING_TIMEOUT", ISSUE_MESSAGES_VI["PROCESSING_TIMEOUT"]
        )
    policy_issues: list[HandoffIssue] = []
    if record.index_status == "LEASED":
        policy_issues.append(
            HandoffIssue(
                code="INDEX_LEASED",
                message="index lease is not owned by this job",
                review_state=ReviewState.BLOCKED,
            )
        )
    # Deterministic local extraction may still produce a bounded partial
    # proposal for operator review. External LLM work is fail-closed when the
    # budget is exhausted; vector recall has its own equivalent gate. Keep the
    # issue on the result, but downgrade extraction to local-only instead of
    # failing the whole handoff.
    if record.processing_budget_hit():
        policy_issues.append(
            HandoffIssue(
                code="BUDGET_EXCEEDED",
                message="processing budget exceeded; local partial extraction only",
                review_state=ReviewState.NEEDS_REVIEW,
            )
        )
        llm = None
    # Embedding quota and missing egress stop external calls. Local extraction
    # still runs, so these are not in the abort list below.
    deferred_blocks: list[HandoffIssue] = []
    if record.embedding_budget_hit():
        deferred_blocks.append(
            HandoffIssue(
                code="EMBEDDING_BUDGET_EXCEEDED",
                message="embedding quota exceeded; vector recall stays off",
                review_state=ReviewState.BLOCKED,
            )
        )
    if not record.egress_approved:
        # Local-only extraction is a complete, reviewable result (D-4), not a
        # block: with B5 a BLOCKED review state fails the whole Backend run.
        deferred_blocks.append(
            HandoffIssue(
                code="EGRESS_DENIED",
                message=ISSUE_MESSAGES_VI["EGRESS_DENIED"],
                review_state=ReviewState.NEEDS_REVIEW,
            )
        )
        llm = None
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
    if policy_issues or deferred_blocks:
        handoff.issues = [*deferred_blocks, *policy_issues, *handoff.issues]
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
    unit_order = {node_id: index for index, unit in enumerate(units) for node_id in unit.node_ids}
    outline = sorted(
        outline,
        key=lambda item: (unit_order.get(item.get("node_id"), len(units)), item.get("node_id", "")),
    )

    if record.input_facts is None:
        record.input_facts = [fact.model_copy(deep=True) for fact in record.facts]
    facts = [fact.model_copy(deep=True) for fact in record.input_facts]
    source_fact_node_ids = {
        fact.citation.node_id for fact in facts if fact.citation and fact.citation.node_id
    }
    runtime.report_progress("S6", 1, 1, "document")
    if trace_writer is not None:
        trace_writer.start("extraction")
    fact_ex = FactExtractor(
        gateway,
        llm,
        runtime=runtime,
        contract_unit_scopes={
            node.node_id: node.scope_id
            for node in record.evidence_nodes()
            if node.scope_id and node.scope_id.startswith("contract-unit:")
        },
    )
    table_ex = TablePipeline(gateway, llm, runtime=runtime)
    payment_schedules = []
    boq_checks = []
    unit_failures: list[HandoffIssue] = []
    extraction_units = 0
    successful_extractions = 0
    for done, node in enumerate(outline):
        runtime.report_progress("S7", done, len(outline), "clause")
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
                table_result = table_ex.extract_with_projection(
                    envelope, _table_id_for(record, node["node_id"])
                )
                facts.extend(table_result.facts)
                if table_result.payment_schedule is not None:
                    payment_schedules.append(table_result.payment_schedule)
                if table_result.boq_check is not None:
                    boq_checks.append(table_result.boq_check)
                successful_extractions += 1
        except ProcessingTimeout:
            # Keep every unit finished so far; the rest of the pipeline is local.
            handoff.issues.append(
                HandoffIssue(
                    code="PROCESSING_TIMEOUT",
                    message=ISSUE_MESSAGES_VI["PROCESSING_TIMEOUT"],
                    review_state=ReviewState.NEEDS_REVIEW,
                    stage="EXTRACT",
                    location=str(node.get("node_id") or ""),
                    retryable=True,
                )
            )
            break
        except ToolBlocked:
            unit_failures.append(
                HandoffIssue(
                    code="TOOL_BLOCKED",
                    message=f"unit for node {node.get('node_id')}: snapshot tool access was blocked",
                    review_state=ReviewState.NEEDS_REVIEW,
                    stage="EXTRACT",
                    location=str(node.get("node_id") or ""),
                    retryable=True,
                )
            )
            continue
        except TableExtractionError as exc:
            unit_failures.append(
                HandoffIssue(
                    code="TABLE_EXTRACTION_FAILED",
                    message=f"unit for node {node.get('node_id')}: {exc}",
                    review_state=ReviewState.NEEDS_REVIEW,
                    stage="EXTRACT",
                    location=str(node.get("node_id") or ""),
                    retryable=True,
                )
            )
            continue
        except Exception as exc:
            unit_failures.append(
                HandoffIssue(
                    code="EXTRACTION_FAILED",
                    message=f"unit for node {node.get('node_id')}: {type(exc).__name__}: {exc}",
                    review_state=ReviewState.NEEDS_REVIEW,
                    stage="EXTRACT",
                    location=str(node.get("node_id") or ""),
                    retryable=False,
                )
            )
            continue
    handoff.issues.extend(unit_failures)
    handoff.issues.extend(
        HandoffIssue(
            code=code,
            message=ISSUE_MESSAGES_VI[code],
            review_state=ReviewState.NEEDS_REVIEW,
            stage="EXTRACT",
            retryable=code != "LLM_BUDGET_EXCEEDED",
        )
        for code in dict.fromkeys(code for code, _ in runtime.issues)
        if code in TERMINATION_CODES
    )
    if extraction_units and not successful_extractions and unit_failures:
        first = unit_failures[0]
        if trace_writer is not None:
            trace_writer.finish("extraction", "FAILED", item_count=0, reason_code=first.code)
        return _failed_result(job_id, handoff.issues, first.code, first.message)
    facts = _dedupe_same_published_key(facts)
    if trace_writer is not None:
        trace_writer.finish("extraction", "COMPLETED", item_count=len(facts))
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
    # Contract graph (flow 1) only behind its flag: off ⇒ no import, no call, no new value.
    graph = None  # ContractGraphResult when the builder ran (P4 projects it)
    graph_enabled = (
        _contract_graph_enabled()
    )  # read once: a mid-run env flip must not split the run
    pairs_on = graph_enabled and _contract_graph_pairs_enabled()
    graph_issues: list[EvidenceIssue] = []
    contract_graph_stage_status = "SKIPPED"
    if graph_enabled and not _past_deadline(
        runtime, trace_writer, "contract_graph_operation", handoff
    ):
        if trace_writer is not None:
            trace_writer.start("contract_graph_operation")
        try:
            from app.pipeline.contract_graph.builder import (
                build_contract_graph,
                known_documents_for_record,
            )

            graph = build_contract_graph(
                record,
                facts,
                known_documents=known_documents_for_record(record),
            )
        except Exception as exc:  # enrichment only: never fail the job (D11)
            contract_graph_stage_status = "FAILED"
            if trace_writer is not None:
                trace_writer.finish(
                    "contract_graph_operation",
                    "FAILED",
                    item_count=0,
                    reason_code="GRAPH_BUILD_FAILED",
                )
            graph_issues.append(
                EvidenceIssue(
                    issue_id="contract-graph:CONTRACT_GRAPH_FAILED",
                    missing="CONTRACT_GRAPH_FAILED",
                    reason=f"Không dựng được đồ thị sửa đổi ({type(exc).__name__}); không có cạnh sửa đổi.",
                    review_state=ReviewState.NEEDS_REVIEW,
                )
            )
        else:
            contract_graph_stage_status = "COMPLETED"
            if trace_writer is not None:
                trace_writer.finish(
                    "contract_graph_operation", "COMPLETED", item_count=len(graph.edges)
                )
            relation_pairs |= {
                tuple(sorted((edge.source_node_id, edge.target_node_id))) for edge in graph.edges
            }
            graph_issues.extend(graph.issues)
    elif trace_writer is not None and not graph_enabled:
        trace_writer.skip("contract_graph_operation", "FEATURE_DISABLED")
    pairer = CandidatePairer()
    candidates, issues = pairer.pair_with_issues(
        facts,
        annex_labels=annex_labels,
        relation_pairs=relation_pairs if pairs_on else set(),
        require_relation_for_cross_document=not pairs_on,
        split_installments=pairs_on,
    )
    if graph is not None and pairs_on:
        amendment_pairs = {
            tuple(sorted((edge.source_node_id, edge.target_node_id))) for edge in graph.edges
        }
        for candidate_index, candidate in enumerate(candidates):
            if not candidate.evidence_left or not candidate.evidence_right:
                continue
            pair = tuple(
                sorted((candidate.evidence_left[0].node_id, candidate.evidence_right[0].node_id))
            )
            if pair in amendment_pairs:
                candidates[candidate_index] = candidate.model_copy(
                    update={
                        "finding_type": FindingType.CANDIDATE_AMENDMENT,
                        "disposition": Disposition.CANDIDATE_AMENDMENT,
                        "review_state": ReviewState.NEEDS_REVIEW,
                        "model_disposition": ModelDisposition.UNCLEAR,
                    }
                )
    # Free-form clause prose never gets an ``item_key``; compare aligned
    # clauses between the contract body and separately uploaded annex files.
    known_pairs = {(c.left_id, c.right_id) for c in candidates}
    candidates.extend(
        c
        for c in compare_clauses_across_files(record)
        if (c.left_id, c.right_id) not in known_pairs
    )
    issues = [*record.relation_graph.issues, *issues] if record.relation_graph else issues
    issues.extend(_runtime_issues(runtime))
    issues.extend(_validate_output_citations(record, facts, candidates, events))
    context_tables = set()
    for fact in facts:
        table_id = fact.citation.table_id
        if table_id and not fact.item_key and table_id not in context_tables:
            context_tables.add(table_id)
            issues.append(
                EvidenceIssue(
                    issue_id=f"table-context:{table_id}",
                    missing="TABLE_COMPARISON_CONTEXT",
                    reason="Table amounts are extracted, but no authoritative item/context mapping supports cross-source comparison; zero findings does not mean consistency.",
                    citation=fact.citation,
                    review_state=ReviewState.NEEDS_REVIEW,
                )
            )
    _downgrade_uncertain_candidates(candidates, facts)
    # Keep typed table projections available to the semantic bridge for this run;
    # raw OCR tables remain immutable and are never appended to here.
    record.payment_schedules = list(payment_schedules)
    record.boq_checks = list(boq_checks)
    # Q3: the graph's per-edge findings replace the annex-level signal only when it ran.
    contract_context: ContractContext = build_contract_context(
        record, candidates=candidates, facts=facts, suppress_amendment_signal=graph is not None
    )
    graph_coverage_value: dict | None = None
    if graph_enabled:
        from app.pipeline.contract_graph.projection import (
            deduped_with_legacy,
            edge_findings,
            graph_coverage,
        )

        if graph is None:
            graph_coverage_value = graph_coverage(None, failed=True)
        else:
            # D5: before ``context_issues`` so each edge gets its issue/review item like the old signal
            contract_context.findings.extend(edge_findings(graph.edges, candidates))
            graph_coverage_value = graph_coverage(
                graph, deduped_with_legacy=deduped_with_legacy(graph.edges, candidates)
            )
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
    # D4: after every pre-existing issue, so their positional review ids do not move
    issues.extend(graph_issues)
    pair_result = None
    pair_relations_stage_status = "SKIPPED"
    if pairs_on:
        from app.pipeline.contract_graph.pair_projection import (
            limited_coverage_issue,
            pair_conflict_candidates,
            pair_coverage,
        )

        pairs_status = "SKIPPED_GRAPH_FAILED" if graph is None else "OK"
        conflict_stats = {}
        pairs_timed_out = graph is not None and _past_deadline(
            runtime, trace_writer, "contract_graph_pairs", handoff
        )
        if graph is not None and not pairs_timed_out:
            if trace_writer is not None:
                trace_writer.start("contract_graph_pairs")
            try:
                from app.pipeline.contract_graph.pair_builder import build_pair_relations

                pair_result = build_pair_relations(record, graph.edges, llm=llm, runtime=runtime)
                pair_relations_stage_status = "COMPLETED"
                conflicts, conflict_stats = pair_conflict_candidates(
                    pair_result, candidates, record
                )
                candidates.extend(conflicts)
                if trace_writer is not None:
                    trace_writer.finish(
                        "contract_graph_pairs",
                        "COMPLETED",
                        item_count=len(pair_result.relations),
                        reason_code=_pairs_reason_code(pair_result),
                    )
                if pair_result.mode == "rule_only":
                    issues.append(limited_coverage_issue(pair_result))
            except Exception as exc:
                pair_result = None
                pair_relations_stage_status = "FAILED"
                pairs_status = "FAILED"
                if trace_writer is not None:
                    trace_writer.finish(
                        "contract_graph_pairs",
                        "FAILED",
                        item_count=0,
                        reason_code="PAIR_BUILD_FAILED",
                    )
                issues.append(
                    EvidenceIssue(
                        issue_id="contract-graph:CONTRACT_GRAPH_PAIRS_FAILED",
                        missing="CONTRACT_GRAPH_PAIRS_FAILED",
                        reason=f"Không phân loại được quan hệ giữa các khoản ({type(exc).__name__}); "
                        "không có quan hệ luồng 2.",
                        review_state=ReviewState.NEEDS_REVIEW,
                    )
                )
        elif trace_writer is not None and not pairs_timed_out:
            trace_writer.skip("contract_graph_pairs", "GRAPH_UNAVAILABLE")
        graph_coverage_value.update(
            pair_coverage(
                pair_result,
                status=pairs_status,
                conflict_stats=conflict_stats,
            )
        )
    elif trace_writer is not None:
        trace_writer.skip("contract_graph_pairs", "FEATURE_DISABLED")
    coverage = {
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
    }
    if graph_coverage_value is not None:  # D6: the only new key, flag on only
        coverage["contract_graph"] = graph_coverage_value
    store_idx = index or IndexStore()
    record.semantic_extension = None
    if record.semantic_profile is not None:
        if os.getenv("AI2_SEMANTIC_ENABLED", "true").strip().casefold() == "true":
            bounds = effective_context_bounds(record.semantic_profile.context_bounds)
            # Spend the capped semantic budget on clauses already known to be related.
            related = [
                node_id
                for source, target in (
                    *((e.source_node_id, e.target_node_id) for e in (graph.edges if graph else ())),
                    *(
                        (r.node_a_id, r.node_b_id)
                        for r in (pair_result.relations if pair_result else ())
                    ),
                )
                for node_id in (source, target)
            ]
            if not _past_deadline(runtime, trace_writer, "semantic", handoff):
                if trace_writer is not None:
                    trace_writer.start("semantic")
                record.semantic_extension = build_semantic_extension(
                    record, runtime, llm, bounds, priority_nodes=tuple(related)
                )
                if trace_writer is not None:
                    trace_writer.finish(
                        "semantic", "COMPLETED", item_count=len(record.semantic_extension.frames)
                    )
            issues.append(
                EvidenceIssue(
                    issue_id="semantic:review",
                    missing="SEMANTIC_REVIEW",
                    reason="Semantic projections require independent review; timeline remains a proposal.",
                    review_state=ReviewState.NEEDS_REVIEW,
                )
            )
        else:
            if trace_writer is not None:
                trace_writer.skip("semantic", "FEATURE_DISABLED")
            issues.append(
                EvidenceIssue(
                    issue_id="semantic:disabled",
                    missing="SEMANTIC_PRODUCER_DISABLED",
                    reason="Semantic profile is pinned; producer rollout has not been enabled.",
                    review_state=ReviewState.NEEDS_REVIEW,
                )
            )
    runtime.report_progress("S10", 0, 1, "document")
    # Only jobs that sent a request carry llm_timing, so LLM-free goldens stay byte-identical.
    llm_timing = runtime.llm_timing()
    contrib = store_idx.propose(
        facts=facts,
        chunks=chunks,
        candidates=candidates,
        evidence_issues=issues,
        contract_context=contract_context,
        events=events,
        semantic_extension=record.semantic_extension,
        coverage={
            **coverage,
            **({"semantic_requested": True} if record.semantic_profile else {}),
            **({"llm_timing": llm_timing} if llm_timing else {}),
        },
        extraction_version=record.pins.extraction_version,
        proposed_index_version=f"idx_{record.pins.extraction_version}",
    )
    contrib = contrib.model_copy(
        update={"payment_schedules": payment_schedules, "boq_checks": boq_checks}
    )
    record.facts = facts
    record.chunks = chunks
    record.events = events
    # D8: what this run produced. An empty list is authoritative for this
    # snapshot; the job store clears any older persisted edges (BL-001).
    record.contract_edges = list(graph.edges) if graph is not None else []
    record.contract_graph_ran = graph is not None
    record.contract_graph_stage_status = contract_graph_stage_status
    record.pair_relations = list(pair_result.relations) if pair_result else []
    record.pair_relations_ran = bool(
        pair_result
        and (
            (pair_result.mode == "llm" and pair_result.batches_completed >= 1)
            or pair_result.rule_only_reason == "NO_CONSENT"
        )
    )
    record.pair_relations_stage_status = pair_relations_stage_status
    record.review_items = _review_items_for_result(record, issues, candidates)
    existing_review_ids = {item.review_item_id for item in record.review_items}
    for fact in facts:
        item_id = f"review:fact:{fact.fact_id}"
        if fact.review_state != ReviewState.PASS and item_id not in existing_review_ids:
            record.review_items.append(
                ReviewItem(
                    review_item_id=item_id,
                    kind="FACT",
                    reason="Verify missing/uncertain value and its source context",
                    review_state=fact.review_state,
                    proposed_action="VERIFY_EVIDENCE",
                    citation_ids=[fact.citation.citation_id] if fact.citation.citation_id else [],
                )
            )
            existing_review_ids.add(item_id)
    mem.put(record)

    handoff.issues = [*handoff.issues, *dossier_edge_issues(record)]

    worst = ReviewState.PASS
    if any(issue.review_state == ReviewState.BLOCKED for issue in handoff.issues):
        worst = ReviewState.BLOCKED
    else:
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


def _past_deadline(runtime: ProcessingRuntime, trace_writer, stage_id: str, handoff) -> bool:
    """Past the processing deadline: skip ``stage_id`` and keep what is already done (#113)."""
    if runtime.remaining() > 0:
        return False
    if not any(issue.code == "PROCESSING_TIMEOUT" for issue in handoff.issues):
        handoff.issues.append(
            HandoffIssue(
                code="PROCESSING_TIMEOUT",
                message=ISSUE_MESSAGES_VI["PROCESSING_TIMEOUT"],
                review_state=ReviewState.NEEDS_REVIEW,
                retryable=True,
            )
        )
    if trace_writer is not None:
        trace_writer.skip(stage_id, "PROCESSING_TIMEOUT")
    return True


def _contract_graph_enabled() -> bool:
    # Same rule as ``contract_graph.builder.contract_graph_enabled``; read here so the flag-off
    # path never imports the builder package.
    return os.getenv("AI2_CONTRACT_GRAPH_ENABLED", "true").strip().casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _pairs_reason_code(pair_result: PairResult) -> str | None:
    if pair_result.mode == "rule_only":
        reason = pair_result.rule_only_reason
        return f"RULE_ONLY_{reason}" if reason else "RULE_ONLY"
    # An LLM run that stopped early (provider failure, deadline, call cap) classified
    # only part of the candidates; COMPLETED alone read as full coverage.
    stopped = pair_result.stats.get("stopped_reason")
    return f"PARTIAL_{stopped}" if stopped else None


def _contract_graph_pairs_enabled() -> bool:
    return os.getenv("AI2_CONTRACT_GRAPH_PAIRS_ENABLED", "true").strip().casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _dedupe_same_published_key(facts: list) -> list:
    """One published fact per item key and value. Source nodes stay on the record."""

    seen: set[tuple[str, str, str | None]] = set()
    kept = []
    for fact in facts:
        if not fact.item_key:
            kept.append(fact)
            continue
        value = fact.normalized_value if fact.normalized_value is not None else fact.raw_value
        unit_scope = fact.scope if fact.scope and fact.scope.startswith("contract-unit:") else None
        key = (fact.item_key, str(value), unit_scope)
        if key in seen:
            continue
        seen.add(key)
        kept.append(fact)
    return kept


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


def _validate_output_citations(
    record: DossierRecord, facts, candidates, events=None
) -> list[EvidenceIssue]:
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
        if (
            citation.node_id.startswith("table-node:")
            and result.status == "UNVERIFIED"
            and not citation.line_ids
        ):
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
        code = str(
            getattr(issue, "code", None) or getattr(issue, "issue_id", None) or "EVIDENCE_ISSUE"
        )
        message = str(
            getattr(issue, "message", None)
            or getattr(issue, "reason", None)
            or getattr(issue, "missing", None)
            or code
        )
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
                proposed_action="VERIFY_EVIDENCE"
                if review_state != ReviewState.BLOCKED
                else "FIX_INPUT",
                citation_ids=[citation.citation_id] if citation and citation.citation_id else [],
            )
        )
        seen.add(item_id)
    for candidate in candidates:
        if candidate.review_state not in {
            ReviewState.NEEDS_REVIEW,
            ReviewState.INSUFFICIENT_EVIDENCE,
            ReviewState.BLOCKED,
        }:
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
    bad_revisions = {page.page_revision_id for page in handoff.pages if page.quality != "OK"}
    bad_page_numbers = {page.page_number for page in handoff.pages if page.quality != "OK"}
    uncertain_nodes = {node.node_id for node in handoff.nodes if node.status != "CONFIRMED"}
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
        if (
            left.review_state == ReviewState.INSUFFICIENT_EVIDENCE
            or right.review_state == ReviewState.INSUFFICIENT_EVIDENCE
        ):
            candidate.review_state = ReviewState.INSUFFICIENT_EVIDENCE
            candidate.model_disposition = ModelDisposition.INCOMPLETE
        elif left.review_state != ReviewState.PASS or right.review_state != ReviewState.PASS:
            candidate.review_state = ReviewState.NEEDS_REVIEW
            candidate.model_disposition = ModelDisposition.INCOMPLETE
