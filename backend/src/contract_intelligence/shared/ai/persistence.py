"""Persist canonical AI service payloads xuống Postgres.

Module này là CẦU NỐI giữa:

    AI Service (DOC-05c canonical JSON)
        ↓ JobStatusReport.result (dict)
    Backend dispatcher
        ↓ Ai1SnapshotPayload / Ai2ExtractionPayload / Ai2ComparisonPayload
    Persistence handlers dưới đây
        ↓ SQLAlchemy ORM (page, ocr_line, clause_node, fact, citation, doc_table...)
    PostgreSQL

Mỗi handler validate schema trước khi ghi — đây chính là **Semantic Gate**
(ADR-05). Backend là nơi DUY NHẤT chịu trách nhiệm đảm bảo dữ liệu lưu
xuống DB là canonical và đầy đủ.

Bounded retry (DOC-05c §7.3):
    - max_attempts = 3 (từ settings.ai_dispatcher_max_attempts)
    - Sau 3 lần fail, dispatcher chuyển task sang ``dead`` và thông báo reviewer
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import structlog
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.extraction.infrastructure.persistence.orm import (
    CitationORM,
    ClauseNodeORM,
    DocTableORM,
    FactORM,
    OcrLineORM,
    PageORM,
    PipelineRunORM,
    PipelineStepORM,
)
from contract_intelligence.shared.ai.citation_guard import verify_citation
from contract_intelligence.shared.ai.schemas import (
    Ai1SnapshotPayload,
    Ai2ComparisonPayload,
    Ai2ExtractionPayload,
    CitationItem,
    CitationSegmentItem,
    FactItem,
    FindingItem,
    FindingSideItem,
    UsageLedgerReport,
)
from contract_intelligence.shared.base import new_ulid
from contract_intelligence.shared.utils import normalize_text

logger = structlog.get_logger(__name__)

# HITL thresholds — facts/findings below these create review_item rows.
_FACT_REVIEW_CONFIDENCE = 0.85
_FINDING_REVIEW_CONFIDENCE = 0.80
_FINDING_REVIEW_DISPOSITIONS = frozenset({"conflict", "needs_review", "uncertain", "ambiguous"})


class Ai2PersistenceConflict(ValueError):
    """The same idempotency key was reused with a different result digest."""


@dataclass(frozen=True)
class Ai2ReadModel:
    """Process-reloadable AI2 projection exposed to Backend callers."""

    payload: dict[str, Any]
    job_status: str
    review_state: str
    completeness_state: str
    reason_code: str | None
    evidence_ready: bool
    input_counts: dict[str, int]
    output_counts: dict[str, int]
    coverage: dict[str, Any]
    dropped_records: int
    evidence_issue_count: int


def _result_digest(result: dict[str, Any]) -> str:
    canonical = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _result_body(result: dict[str, Any]) -> dict[str, Any]:
    body = result.get("result")
    return body if isinstance(body, dict) else {}


def _as_dict_list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def evaluate_ai2_completeness(result: dict[str, Any]) -> dict[str, Any]:
    """Evaluate evidence readiness independently from the wire job status."""
    body = _result_body(result)
    facts = _as_dict_list(body.get("facts"))
    findings = _as_dict_list(body.get("findings"))
    context_findings = _as_dict_list(body.get("context_findings"))
    citations = _as_dict_list(body.get("citations"))
    events = _as_dict_list(body.get("events"))
    index = body.get("index_contribution")
    index = index if isinstance(index, dict) else {}
    chunks = _as_dict_list(index.get("chunks"))
    evidence_issues = _as_dict_list(index.get("evidence_issues"))
    citation_ids = {str(item.get("citation_id")) for item in citations if item.get("citation_id")}
    invalid_records = 0
    invalid_record_ids: list[tuple[str, str, str, str]] = []
    for fact in facts:
        refs = [str(item) for item in fact.get("citation_ids") or []]
        if not refs or any(ref not in citation_ids for ref in refs):
            invalid_records += 1
            invalid_record_ids.append(
                (
                    "fact",
                    str(fact.get("fact_id") or fact.get("item_key") or "unknown"),
                    "INVALID_CITATION_REFERENCE",
                    "P1",
                )
            )
    for finding in findings:
        refs = [
            str(item)
            for item in (finding.get("evidence_left_citation_ids") or [])
            + (finding.get("evidence_right_citation_ids") or [])
        ]
        if not refs or any(ref not in citation_ids for ref in refs):
            invalid_records += 1
            invalid_record_ids.append(
                (
                    "finding",
                    str(finding.get("finding_id") or finding.get("item_key") or "unknown"),
                    "INVALID_CITATION_REFERENCE",
                    "P1",
                )
            )

    if not (facts or findings or context_findings or citations or chunks or events):
        reason_code = "NO_ELIGIBLE_DATA"
        state = "NO_ELIGIBLE_DATA"
    elif invalid_records:
        reason_code = "INVALID_CITATION_REFERENCE"
        state = "NEEDS_REVIEW"
    elif not facts and not findings:
        reason_code = "NO_FACTS_OR_FINDINGS"
        state = "CONTEXT_ONLY"
    elif result.get("status") != "SUCCEEDED":
        reason_code = "JOB_NOT_SUCCEEDED"
        state = "INCOMPLETE"
    elif str(result.get("review_state") or "").upper() != "PASS":
        reason_code = "REVIEW_REQUIRED"
        state = "NEEDS_REVIEW"
    else:
        reason_code = None
        state = "COMPLETE"

    evidence_ready = state == "COMPLETE" and not evidence_issues
    input_counts = {
        str(key): int(value)
        for key, value in (index.get("coverage", {}).get("input", {}) or {}).items()
        if isinstance(value, (int, float))
    }
    output_counts = {
        "chunks": len(chunks),
        "citations": len(citations),
        "facts": len(facts),
        "findings": len(findings),
        "context_findings": len(context_findings),
        "events": len(events),
        "evidence_issues": len(evidence_issues),
        "annex_links": len(_as_dict_list(body.get("annex_links"))),
    }
    return {
        "state": state,
        "reason_code": reason_code,
        "evidence_ready": evidence_ready,
        "input_counts": input_counts,
        "output_counts": output_counts,
        "dropped_records": invalid_records,
        "invalid_record_ids": invalid_record_ids,
        "evidence_issue_count": len(evidence_issues),
        "coverage": index.get("coverage") if isinstance(index.get("coverage"), dict) else {},
    }


# ──────────────────────────────────────────────────────────────────────────────
# PipelineRun status helpers
# ──────────────────────────────────────────────────────────────────────────────


async def update_pipeline_run_status(
    session: AsyncSession,
    *,
    tenant_id: str,
    run_id: str,
    status: str,
    error_code: str | None = None,
    error_detail: str | None = None,
) -> None:
    """Cập nhật trạng thái pipeline_run + finished_at nếu terminal state."""
    from sqlalchemy import select

    stmt = select(PipelineRunORM).where(
        PipelineRunORM.id == run_id,
        PipelineRunORM.tenant_id == tenant_id,
    )
    result = await session.execute(stmt)
    run = result.scalar_one_or_none()
    if run is None:
        logger.warning("pipeline_run.not_found", run_id=run_id)
        return
    run.status = status
    run.error_code = error_code
    if error_detail:
        run.error_detail = error_detail
    if status in ("succeeded", "failed", "cancelled", "dead"):
        run.finished_at = datetime.utcnow()
    await session.flush()


async def update_pipeline_step(
    session: AsyncSession,
    *,
    tenant_id: str,
    run_id: str,
    step: str,
    status: str,
    pages: int | None = None,
    duration_ms: int | None = None,
    metrics: dict[str, Any] | None = None,
) -> None:
    """Cập nhật trạng thái 1 bước S0..S10 trong pipeline."""
    from sqlalchemy import select

    stmt = select(PipelineStepORM).where(
        PipelineStepORM.run_id == run_id,
        PipelineStepORM.tenant_id == tenant_id,
        PipelineStepORM.step == step,
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        # Tự tạo nếu chưa có (defensive)
        row = PipelineStepORM(
            tenant_id=tenant_id,
            run_id=run_id,
            step=step,
            status=status,
            attempt=1,
            pages=pages,
            duration_ms=duration_ms,
            metrics=json.dumps(metrics) if metrics else None,
        )
        session.add(row)
    else:
        row.status = status
        if pages is not None:
            row.pages = pages
        if duration_ms is not None:
            row.duration_ms = duration_ms
        if metrics is not None:
            row.metrics = json.dumps(metrics)
    await session.flush()


# ──────────────────────────────────────────────────────────────────────────────
# AI1 snapshot — OCR + Layout + Clauses + Tables
# ──────────────────────────────────────────────────────────────────────────────


async def persist_ai1_snapshot(
    session: AsyncSession,
    *,
    tenant_id: str,
    snapshot: dict[str, Any] | Ai1SnapshotPayload,
    run_id: str | None = None,
) -> int:
    """Ghi canonical snapshot (DOC-05c §5.1) xuống DB.

    Returns:
        Số rows inserted (page + ocr_line + clause_node + doc_table).
    """
    # Validate schema — semantic gate (ADR-05)
    if isinstance(snapshot, dict):
        try:
            payload = Ai1SnapshotPayload.model_validate(snapshot)
        except Exception as exc:
            logger.error("ai1_snapshot.invalid", error=str(exc))
            raise
    else:
        payload = snapshot

    document_id = payload.document_id
    inserted = 0

    # OCR lại: trang/dòng/điều khoản cũ phải được thay, không insert chồng.
    # Unique (document_id, page_no) sẽ chặn bản SUCCESS và để lại lỗi cũ.
    await session.execute(delete(DocTableORM).where(DocTableORM.document_id == document_id))
    await session.execute(delete(ClauseNodeORM).where(ClauseNodeORM.document_id == document_id))
    await session.execute(delete(OcrLineORM).where(OcrLineORM.document_id == document_id))
    await session.execute(delete(PageORM).where(PageORM.document_id == document_id))
    await session.flush()

    # ── Pages ──────────────────────────────────────────────────────────────
    for page in payload.pages:
        page_id = new_ulid("pg_")
        page_orm = PageORM(
            id=page_id,
            tenant_id=tenant_id,
            document_id=document_id,
            page_no=page.page_no,
            width_pt=str(page.width_pt),
            height_pt=str(page.height_pt),
            rotation=page.rotation,
            kind=page.kind.value,
            render_blob_uri=page.render_blob_uri,
            preview_blob_uri=page.preview_blob_uri,
            features=json.dumps(page.features) if page.features else None,
        )
        session.add(page_orm)
        inserted += 1

    # ── OCR Lines ──────────────────────────────────────────────────────────
    for line in payload.lines:
        line_id = new_ulid("ln_")
        line_orm = OcrLineORM(
            id=line_id,
            tenant_id=tenant_id,
            document_id=document_id,
            page_no=line.page_no,
            line_no=line.line_no,
            text=line.text,
            bbox=json.dumps(list(line.bbox)),
            confidence=str(line.confidence),
            doc_char_start=line.doc_char_start,
            doc_char_end=line.doc_char_end,
        )
        session.add(line_orm)
        inserted += 1

    # ── Clauses ────────────────────────────────────────────────────────────
    # AI1 parent_id is a snapshot node id, not a DB id. Map source → row id first.
    source_to_row: dict[str, str] = {}
    clause_rows: list[tuple[ClauseNodeORM, str | None]] = []
    for clause in payload.clauses:
        clause_id = new_ulid("cl_")
        if clause.source_id:
            source_to_row[clause.source_id] = clause_id
        clause_orm = ClauseNodeORM(
            id=clause_id,
            tenant_id=tenant_id,
            document_id=document_id,
            parent_id=None,
            node_type=clause.node_type,
            label=clause.label,
            number=clause.number,
            title=clause.title,
            text=clause.text,
            page_start=clause.page_start,
            page_end=clause.page_end,
            confidence=str(clause.confidence),
            doc_char_start=clause.doc_char_start,
            doc_char_end=clause.doc_char_end,
            regions=json.dumps(
                [
                    {"page_no": r.page_no, "bbox": list(r.bbox), "bbox_source": r.bbox_source}
                    for r in clause.regions
                ]
            )
            if clause.regions
            else None,
        )
        session.add(clause_orm)
        clause_rows.append((clause_orm, clause.parent_source_id))
        inserted += 1

    for clause_orm, parent_source_id in clause_rows:
        if parent_source_id and parent_source_id in source_to_row:
            clause_orm.parent_id = source_to_row[parent_source_id]

    # ── Tables ─────────────────────────────────────────────────────────────
    table_ids: dict[str, str] = {}
    for index, tbl in enumerate(payload.tables):
        source_id = tbl.source_id or f"page:{tbl.page_no}:table:{index}"
        table_ids[source_id] = new_ulid("tb_")

    for index, tbl in enumerate(payload.tables):
        source_id = tbl.source_id or f"page:{tbl.page_no}:table:{index}"
        tbl_id = table_ids[source_id]
        tbl_orm = DocTableORM(
            id=tbl_id,
            tenant_id=tenant_id,
            document_id=document_id,
            page_no=tbl.page_no,
            bbox=json.dumps(list(tbl.bbox)),
            rows_count=tbl.rows_count,
            cols_count=tbl.cols_count,
            has_borders="true" if tbl.has_borders else "false",
            is_multi_page=tbl.is_multi_page or bool(tbl.continued_from_source_id),
            continued_from=table_ids.get(tbl.continued_from_source_id or ""),
            cells=json.dumps(
                [
                    {
                        "row_idx": c.row_idx,
                        "col_idx": c.col_idx,
                        "row_span": c.row_span,
                        "col_span": c.col_span,
                        "text": c.text,
                        "bbox": list(c.bbox),
                        "is_header": c.is_header,
                        "confidence": c.confidence,
                    }
                    for c in tbl.cells
                ]
            ),
        )
        session.add(tbl_orm)
        inserted += 1

    await session.flush()
    logger.info(
        "ai1_snapshot.persisted",
        document_id=document_id,
        tenant_id=tenant_id,
        run_id=run_id,
        pages=len(payload.pages),
        lines=len(payload.lines),
        clauses=len(payload.clauses),
        tables=len(payload.tables),
    )
    return inserted


# ──────────────────────────────────────────────────────────────────────────────
# AI2 extraction — Facts + Citations + Evidence Gaps
# ──────────────────────────────────────────────────────────────────────────────


async def persist_ai2_extraction(
    session: AsyncSession,
    *,
    tenant_id: str,
    extraction: dict[str, Any] | Ai2ExtractionPayload,
    run_id: str | None = None,
) -> int:
    """Ghi canonical extraction (DOC-05c §5.2) xuống DB.

    Returns:
        Số facts đã ghi.
    """
    if isinstance(extraction, dict):
        try:
            payload = Ai2ExtractionPayload.model_validate(extraction)
        except Exception as exc:
            logger.error("ai2_extraction.invalid", error=str(exc))
            raise
    else:
        payload = extraction

    document_id = payload.document_id
    inserted = 0
    # (target_type, target_id, reason, priority)
    review_targets: list[tuple[str, str, str, str]] = []

    dossier_id = await _lookup_dossier_id(session, document_id)

    for fact in payload.facts:
        fact_id = new_ulid("fct_")
        citation_id = new_ulid("cit_")

        citation_orm = await _build_citation_orm(
            session, citation_id, tenant_id, document_id, fact.citation
        )
        if citation_orm is None:
            # Persist rejected quote for audit; force HITL review.
            citation_orm = CitationORM(
                id=citation_id,
                tenant_id=tenant_id,
                document_id=document_id,
                quote=normalize_text(fact.citation.quote or ""),
                quote_sha256="",
                doc_char_start=fact.citation.doc_char_start,
                doc_char_end=fact.citation.doc_char_end,
                segments=_segments_json(fact.citation),
            )
            review_targets.append(("fact", fact_id, f"citation_guard_rejected:{fact.key}", "P1"))

        session.add(citation_orm)
        session.add(
            FactORM(
                id=fact_id,
                tenant_id=tenant_id,
                document_id=document_id,
                key=fact.key,
                fact_type=fact.fact_type,
                raw_text=fact.raw_text,
                normalized_value=json.dumps(fact.normalized_value),
                confidence=str(fact.confidence),
                extractor=fact.extractor,
                context_text=fact.context_text,
                citation_id=citation_id,
            )
        )
        inserted += 1

        if float(fact.confidence) < _FACT_REVIEW_CONFIDENCE:
            priority = "P1" if float(fact.confidence) < 0.6 else "P2"
            # Avoid duplicate if already queued for citation failure
            if not any(t[1] == fact_id for t in review_targets):
                review_targets.append(("fact", fact_id, f"low_confidence:{fact.key}", priority))

    for gap in payload.evidence_gaps:
        review_targets.append(
            (
                "citation",
                new_ulid("gap_"),
                f"evidence_gap:p{gap.page_no}:{gap.reason}",
                "P1" if gap.severity == "high" else "P2",
            )
        )

    await session.flush()

    if dossier_id and run_id and review_targets:
        await _create_review_items(
            session,
            tenant_id=tenant_id,
            dossier_id=dossier_id,
            run_id=run_id,
            targets=review_targets,
        )

    logger.info(
        "ai2_extraction.persisted",
        document_id=document_id,
        tenant_id=tenant_id,
        run_id=run_id,
        facts=inserted,
        evidence_gaps=len(payload.evidence_gaps),
        review_items=len(review_targets),
    )
    return inserted


# ──────────────────────────────────────────────────────────────────────────────
# AI2 comparison — Annex Links + Findings
# ──────────────────────────────────────────────────────────────────────────────


async def persist_ai2_comparison(
    session: AsyncSession,
    *,
    tenant_id: str,
    comparison: dict[str, Any] | Ai2ComparisonPayload,
    run_id: str | None = None,
) -> int:
    """Ghi canonical comparison (DOC-05c §5.3) xuống DB.

    Comparison writes to ``finding`` and ``annex_link`` tables (conflict BC).
    Dùng raw SQL ``text()`` để tránh import ORM từ ``conflict.infrastructure``
    (vi phạm import-linter layer rule: shared/ai KHÔNG được phép import BC infra).

    Returns số findings written.
    """
    if isinstance(comparison, dict):
        try:
            payload = Ai2ComparisonPayload.model_validate(comparison)
        except Exception as exc:
            logger.error("ai2_comparison.invalid", error=str(exc))
            raise
    else:
        payload = comparison

    dossier_id = payload.dossier_id
    inserted = 0
    finding_review_targets: list[tuple[str, str, str, str]] = []

    # ── Annex Links ────────────────────────────────────────────────────────
    for link in payload.annex_links:
        link_id = new_ulid("al_")
        await session.execute(
            text(
                """
                INSERT INTO annex_link (
                    id, tenant_id, dossier_id, annex_document_id, contract_document_id,
                    score, annex_sequence, effective_date, status, citation_id
                ) VALUES (
                    :id, :tenant_id, :dossier_id, :annex_document_id, :contract_document_id,
                    :score, :annex_sequence, :effective_date, :status, NULL
                )
                """
            ),
            {
                "id": link_id,
                "tenant_id": tenant_id,
                "dossier_id": dossier_id,
                "annex_document_id": link.annex_document_id,
                "contract_document_id": link.contract_document_id,
                "score": str(link.score),
                "annex_sequence": link.annex_sequence,
                "effective_date": link.effective_date,
                "status": link.status,
            },
        )

    # ── Findings ───────────────────────────────────────────────────────────
    for finding in payload.findings:
        finding_id = new_ulid("fd_")

        # side_a citation (Citation Guard)
        side_a_cit_id = new_ulid("cit_")
        side_a_doc_id = finding.side_a.document_id
        side_a_cit = await _build_citation_orm(
            session, side_a_cit_id, tenant_id, side_a_doc_id, finding.side_a.citation
        )
        if side_a_cit is None:
            side_a_cit = CitationORM(
                id=side_a_cit_id,
                tenant_id=tenant_id,
                document_id=side_a_doc_id,
                quote=normalize_text(finding.side_a.citation.quote or ""),
                quote_sha256="",
                doc_char_start=finding.side_a.citation.doc_char_start,
                doc_char_end=finding.side_a.citation.doc_char_end,
                segments=_segments_json(finding.side_a.citation),
            )
        session.add(side_a_cit)

        # side_b citation (Citation Guard)
        side_b_cit_id = new_ulid("cit_")
        side_b_doc_id = finding.side_b.document_id
        side_b_cit = await _build_citation_orm(
            session, side_b_cit_id, tenant_id, side_b_doc_id, finding.side_b.citation
        )
        if side_b_cit is None:
            side_b_cit = CitationORM(
                id=side_b_cit_id,
                tenant_id=tenant_id,
                document_id=side_b_doc_id,
                quote=normalize_text(finding.side_b.citation.quote or ""),
                quote_sha256="",
                doc_char_start=finding.side_b.citation.doc_char_start,
                doc_char_end=finding.side_b.citation.doc_char_end,
                segments=_segments_json(finding.side_b.citation),
            )
        session.add(side_b_cit)

        await session.execute(
            text(
                """
                INSERT INTO finding (
                    id, tenant_id, dossier_id, run_id, finding_type, scope, key_or_topic,
                    disposition, severity, confidence, rationale, method
                ) VALUES (
                    :id, :tenant_id, :dossier_id, :run_id, :finding_type, :scope, :key_or_topic,
                    :disposition, :severity, :confidence, :rationale, :method
                )
                """
            ),
            {
                "id": finding_id,
                "tenant_id": tenant_id,
                "dossier_id": dossier_id,
                "run_id": run_id,
                "finding_type": finding.finding_type,
                "scope": finding.scope,
                "key_or_topic": finding.key_or_topic,
                "disposition": finding.disposition,
                "severity": finding.severity,
                "confidence": str(finding.confidence),
                "rationale": finding.rationale,
                "method": finding.method,
            },
        )

        # sides — raw SQL
        await session.execute(
            text(
                """
                INSERT INTO finding_side (
                    id, tenant_id, finding_id, side, document_id, fact_id, clause_node_id,
                    citation_id, value_snapshot
                ) VALUES (
                    :id, :tenant_id, :finding_id, :side, :document_id, :fact_id, :clause_node_id,
                    :citation_id, :value_snapshot
                )
                """
            ),
            {
                "id": new_ulid("fs_"),
                "tenant_id": tenant_id,
                "finding_id": finding_id,
                "side": "a",
                "document_id": finding.side_a.document_id,
                "fact_id": finding.side_a.fact_id,
                "clause_node_id": finding.side_a.clause_node_id,
                "citation_id": side_a_cit_id,
                "value_snapshot": json.dumps(finding.side_a.value_snapshot)
                if finding.side_a.value_snapshot
                else None,
            },
        )
        await session.execute(
            text(
                """
                INSERT INTO finding_side (
                    id, tenant_id, finding_id, side, document_id, fact_id, clause_node_id,
                    citation_id, value_snapshot
                ) VALUES (
                    :id, :tenant_id, :finding_id, :side, :document_id, :fact_id, :clause_node_id,
                    :citation_id, :value_snapshot
                )
                """
            ),
            {
                "id": new_ulid("fs_"),
                "tenant_id": tenant_id,
                "finding_id": finding_id,
                "side": "b",
                "document_id": finding.side_b.document_id,
                "fact_id": finding.side_b.fact_id,
                "clause_node_id": finding.side_b.clause_node_id,
                "citation_id": side_b_cit_id,
                "value_snapshot": json.dumps(finding.side_b.value_snapshot)
                if finding.side_b.value_snapshot
                else None,
            },
        )

        inserted += 1

        needs_review = (
            finding.disposition.lower() in _FINDING_REVIEW_DISPOSITIONS
            or float(finding.confidence) < _FINDING_REVIEW_CONFIDENCE
            or finding.severity.lower() == "high"
        )
        if needs_review:
            finding_review_targets.append(
                (
                    "finding",
                    finding_id,
                    f"finding:{finding.key_or_topic}:{finding.disposition}",
                    "P1" if finding.severity.lower() == "high" else "P2",
                )
            )

    await session.flush()

    if run_id and finding_review_targets:
        await _create_review_items(
            session,
            tenant_id=tenant_id,
            dossier_id=dossier_id,
            run_id=run_id,
            targets=finding_review_targets,
        )

    logger.info(
        "ai2_comparison.persisted",
        dossier_id=dossier_id,
        tenant_id=tenant_id,
        run_id=run_id,
        annex_links=len(payload.annex_links),
        findings=inserted,
        review_items=len(finding_review_targets),
    )
    return inserted


def _context_findings_as_items(
    raw_findings: object,
    citation_by_id: dict[str, dict[str, Any]] | None = None,
) -> list[FindingItem]:
    """Đưa tín hiệu ngữ cảnh (context finding) *liên tài liệu* vào hàng đối soát.

    Chỉ những context finding có bằng chứng trên ít nhất hai tài liệu khác nhau
    mới là xung đột hợp đồng–phụ lục. Tín hiệu nội bộ một tài liệu (phụ lục
    nhúng trong hợp đồng thiếu tham chiếu, ngôn ngữ sửa đổi, ...) và các
    CONTEXT_CONFLICT đã được phát hành như ``findings`` (``metadata.candidate_id``)
    không được nhân đôi ở đây. Mỗi phía trỏ tới citation thật (trang/dòng/bbox)
    thay vì chuỗi lý do.
    """
    if not isinstance(raw_findings, list):
        return []
    citation_by_id = citation_by_id or {}
    items: list[FindingItem] = []
    for raw in raw_findings:
        if not isinstance(raw, dict):
            continue
        if raw.get("review_state") not in {None, "NEEDS_REVIEW", "INSUFFICIENT_EVIDENCE"}:
            continue
        raw_metadata = raw.get("metadata")
        metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
        if metadata.get("candidate_id"):
            continue
        by_document: dict[str, dict[str, Any]] = {}
        for citation_id in raw.get("citation_ids") or []:
            citation = citation_by_id.get(str(citation_id))
            if not isinstance(citation, dict):
                continue
            document_id = str(citation.get("source_file_id") or "")
            if document_id and citation.get("text_span"):
                by_document.setdefault(document_id, citation)
        if len(by_document) < 2:
            continue
        reason = str(raw.get("reason") or "Cần đối chiếu hợp đồng và phụ lục.")
        documents = list(by_document.items())
        left_id, left_citation = documents[0]
        right_id, right_citation = documents[-1]
        kind = str(raw.get("finding_type") or "")
        disposition = (
            "candidate_amendment"
            if kind == "AMENDMENT_SIGNAL" or raw.get("relation_type") == "AMENDS"
            else "insufficient_evidence"
        )

        def side(document_id: str, citation: dict[str, Any]) -> FindingSideItem:
            return FindingSideItem(
                document_id=document_id,
                citation=_canonical_citation_item(citation),
                value_snapshot={"text": str(citation.get("text_span") or "")},
            )

        items.append(
            FindingItem(
                finding_type="semantic",
                scope="contract_annex",
                key_or_topic=str(raw.get("subject_key") or raw.get("finding_id") or kind),
                disposition=disposition,
                severity="high",
                confidence=0.55,
                rationale=reason,
                method="ai2.context",
                side_a=side(left_id, left_citation),
                side_b=side(right_id, right_citation),
            )
        )
    return items


def _canonical_citation_item(raw: dict[str, Any]) -> CitationItem:
    """Map one canonical AI2 citation to the legacy DB persistence DTO."""

    page = int(raw.get("page") or (raw.get("page_range") or [1])[0] or 1)
    line_ids = [str(item) for item in raw.get("line_ids") or []]
    segment = CitationSegmentItem(
        page_no=page,
        line_id=line_ids[0] if line_ids else str(raw.get("node_id") or "ai2"),
        char_start=int(raw.get("char_start") or 0),
        char_end=int(raw.get("char_end") or 0),
        bbox=tuple(float(item) for item in (raw.get("bbox") or [0, 0, 0, 0])),
    )
    return CitationItem(
        quote=str(raw.get("text_span") or ""),
        quote_sha256=str(raw.get("quote_sha256") or ""),
        doc_char_start=int(raw.get("char_start") or 0),
        doc_char_end=int(raw.get("char_end") or 0),
        segments=[segment],
    )


async def persist_ai2_processing_result(
    session: AsyncSession,
    *,
    tenant_id: str,
    dossier_id: str,
    result: dict[str, Any],
    run_id: str | None = None,
) -> dict[str, Any]:
    """Persist canonical ``ai2.be.processing.result.v1`` into Backend tables.

    The wire result remains the source contract. This adapter projects facts and
    findings into the existing extraction/conflict read models used by the UI.
    """

    body = _result_body(result)
    digest = _result_digest(result)
    completeness = evaluate_ai2_completeness(result)
    effective_review_state = (
        "NEEDS_REVIEW"
        if completeness["state"] == "NEEDS_REVIEW"
        else str(result.get("review_state") or completeness["state"])
    )
    run = await session.get(PipelineRunORM, run_id) if run_id else None
    if run is not None and run.tenant_id != tenant_id:
        raise Ai2PersistenceConflict(f"Pipeline run {run_id!r} belongs to another tenant")
    if run is not None and run.ai2_result_digest:
        if run.ai2_result_digest != digest:
            raise Ai2PersistenceConflict(
                f"AI2 result digest conflict for idempotency key {run.ai2_idempotency_key!r}"
            )
        return {
            "facts": completeness["output_counts"]["facts"],
            "findings": completeness["output_counts"]["findings"],
            "chunks": completeness["output_counts"]["chunks"],
            "events": completeness["output_counts"]["events"],
            "evidence_issues": completeness["evidence_issue_count"],
            "annex_links": completeness["output_counts"]["annex_links"],
            "dropped_records": int(run.ai2_dropped_records or 0),
            "reason_code": run.ai2_reason_code,
            "review_state": run.ai2_review_state,
            "evidence_ready": bool(run.ai2_evidence_ready),
            "job_status": run.ai2_job_status,
            "idempotent_replay": True,
        }
    citation_by_id = {
        str(item.get("citation_id")): item
        for item in body.get("citations", [])
        if isinstance(item, dict) and item.get("citation_id")
    }
    facts_by_document: dict[str, list[FactItem]] = {}
    for raw_fact in body.get("facts", []):
        if not isinstance(raw_fact, dict):
            continue
        citation = next(
            (
                citation_by_id[citation_id]
                for citation_id in raw_fact.get("citation_ids", [])
                if citation_id in citation_by_id
            ),
            None,
        )
        document_id = str((citation or {}).get("source_file_id") or "")
        if not document_id:
            continue
        normalized = raw_fact.get("normalized_value")
        if normalized is None:
            normalized = {"value": raw_fact.get("raw_value")}
        elif not isinstance(normalized, dict):
            normalized = {"value": normalized}
        facts_by_document.setdefault(document_id, []).append(
            FactItem(
                key=str(
                    raw_fact.get("item_key") or raw_fact.get("role") or raw_fact.get("fact_id")
                ),
                fact_type=str(raw_fact.get("role") or raw_fact.get("subject") or "unknown"),
                raw_text=str(raw_fact.get("raw_value") or ""),
                normalized_value=normalized,
                confidence=1.0 if raw_fact.get("review_state") == "PASS" else 0.6,
                extractor=str(raw_fact.get("provenance") or "ai2.canonical"),
                context_text=None,
                citation=_canonical_citation_item(citation or {}),
            )
        )

    facts_written = 0
    for document_id, facts in facts_by_document.items():
        facts_written += await persist_ai2_extraction(
            session,
            tenant_id=tenant_id,
            extraction=Ai2ExtractionPayload(document_id=document_id, facts=facts).model_dump(
                mode="json"
            ),
            run_id=run_id,
        )

    finding_items: list[FindingItem] = []
    finding_items.extend(
        _context_findings_as_items(body.get("context_findings") or [], citation_by_id)
    )
    for raw_finding in body.get("findings", []):
        if not isinstance(raw_finding, dict):
            continue
        left = next(
            (
                citation_by_id[item]
                for item in raw_finding.get("evidence_left_citation_ids", [])
                if item in citation_by_id
            ),
            None,
        )
        right = next(
            (
                citation_by_id[item]
                for item in raw_finding.get("evidence_right_citation_ids", [])
                if item in citation_by_id
            ),
            left,
        )
        if (
            not left
            or not right
            or not left.get("source_file_id")
            or not right.get("source_file_id")
        ):
            continue
        finding_items.append(
            FindingItem(
                finding_type="semantic"
                if raw_finding.get("finding_type") != "structured"
                else "structured",
                scope=str(raw_finding.get("scope") or "contract_annex"),
                key_or_topic=str(raw_finding.get("item_key") or raw_finding.get("finding_id")),
                # Repository filters compare lowercase dispositions
                # ("comparable_difference"); the wire carries enum names.
                disposition=str(
                    raw_finding.get("disposition")
                    or raw_finding.get("model_disposition")
                    or "needs_review"
                ).lower(),
                severity="high" if raw_finding.get("review_state") == "NEEDS_REVIEW" else "medium",
                confidence=0.6 if raw_finding.get("review_state") == "NEEDS_REVIEW" else 0.9,
                rationale=str(raw_finding.get("reason") or ""),
                method="ai2.canonical",
                side_a=FindingSideItem(
                    document_id=str(left["source_file_id"]),
                    citation=_canonical_citation_item(left),
                ),
                side_b=FindingSideItem(
                    document_id=str(right["source_file_id"]),
                    citation=_canonical_citation_item(right),
                ),
            )
        )

    findings_written = 0
    if finding_items:
        findings_written = await persist_ai2_comparison(
            session,
            tenant_id=tenant_id,
            comparison=Ai2ComparisonPayload(
                dossier_id=dossier_id,
                annex_links=[],
                findings=finding_items,
            ).model_dump(mode="json"),
            run_id=run_id,
        )
    if run is not None:
        invalid_targets = completeness["invalid_record_ids"]
        if invalid_targets:
            await _create_review_items(
                session,
                tenant_id=tenant_id,
                dossier_id=dossier_id,
                run_id=run_id or "",
                targets=invalid_targets,
            )
        run.ai2_result_json = json.dumps(result, ensure_ascii=False, sort_keys=True)
        run.ai2_result_digest = digest
        run.ai2_idempotency_key = str(result.get("idempotency_key") or "") or None
        run.ai2_job_status = str(result.get("status") or "UNKNOWN")
        run.ai2_review_state = effective_review_state
        run.ai2_completeness_state = str(completeness["state"])
        run.ai2_reason_code = completeness["reason_code"]
        run.ai2_evidence_ready = bool(completeness["evidence_ready"])
        run.ai2_input_counts = json.dumps(completeness["input_counts"], sort_keys=True)
        run.ai2_output_counts = json.dumps(completeness["output_counts"], sort_keys=True)
        run.ai2_dropped_records = int(completeness["dropped_records"])
        run.ai2_evidence_issue_count = int(completeness["evidence_issue_count"])
        if str(result.get("status") or "").upper() == "SUCCEEDED":
            run.status = "succeeded"
        await session.flush()
    return {
        "facts": facts_written,
        "findings": findings_written,
        "chunks": completeness["output_counts"]["chunks"],
        "events": completeness["output_counts"]["events"],
        "evidence_issues": completeness["evidence_issue_count"],
        "annex_links": completeness["output_counts"]["annex_links"],
        "dropped_records": completeness["dropped_records"],
        "reason_code": completeness["reason_code"],
        "review_state": effective_review_state,
        "evidence_ready": completeness["evidence_ready"],
        "job_status": str(result.get("status") or "UNKNOWN"),
        "idempotent_replay": False,
    }


async def load_ai2_read_model(
    session: AsyncSession,
    *,
    tenant_id: str,
    run_id: str,
) -> Ai2ReadModel:
    """Load the complete AI2 projection after a process restart."""
    run = await session.get(PipelineRunORM, run_id)
    if run is None or run.tenant_id != tenant_id or not run.ai2_result_json:
        raise LookupError(f"AI2 read model not found for run {run_id!r}")
    payload = json.loads(run.ai2_result_json)
    return Ai2ReadModel(
        payload=payload,
        job_status=str(run.ai2_job_status or payload.get("status") or "UNKNOWN"),
        review_state=str(run.ai2_review_state or payload.get("review_state") or "UNKNOWN"),
        completeness_state=str(run.ai2_completeness_state or "UNKNOWN"),
        reason_code=run.ai2_reason_code,
        evidence_ready=bool(run.ai2_evidence_ready),
        input_counts=json.loads(run.ai2_input_counts or "{}"),
        output_counts=json.loads(run.ai2_output_counts or "{}"),
        coverage=(
            _result_body(payload).get("index_contribution", {}).get("coverage", {})
            if isinstance(_result_body(payload).get("index_contribution"), dict)
            else {}
        ),
        dropped_records=int(run.ai2_dropped_records or 0),
        evidence_issue_count=int(run.ai2_evidence_issue_count or 0),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Usage ledger — ghi vào usage_ledger table nếu có
# ──────────────────────────────────────────────────────────────────────────────


async def persist_usage_ledger(
    session: AsyncSession,
    *,
    tenant_id: str,
    usage: UsageLedgerReport,
    task_id: int,
    job_kind: str,
) -> None:
    """Ghi UsageLedgerReport vào bảng usage_ledger (Sprint 4 — defensive skip nếu chưa migrate)."""
    try:
        # DAL tránh hard-import để không fail khi chưa có alembic migration
        from sqlalchemy import text

        await session.execute(
            text(
                """
                INSERT INTO usage_ledger (
                    tenant_id, task_id, job_kind, provider, model_requested, model_returned,
                    input_tokens, cached_tokens, output_tokens, reasoning_tokens,
                    pages_processed, cache_hit, latency_ms, cost_usd, price_version
                ) VALUES (
                    :tenant_id, :task_id, :job_kind, :provider, :model_requested, :model_returned,
                    :input_tokens, :cached_tokens, :output_tokens, :reasoning_tokens,
                    :pages_processed, :cache_hit, :latency_ms, :cost_usd, :price_version
                )
                """
            ),
            {
                "tenant_id": tenant_id,
                "task_id": task_id,
                "job_kind": job_kind,
                "provider": usage.provider,
                "model_requested": usage.model_requested,
                "model_returned": usage.model_returned,
                "input_tokens": usage.input_tokens,
                "cached_tokens": usage.cached_tokens,
                "output_tokens": usage.output_tokens,
                "reasoning_tokens": usage.reasoning_tokens,
                "pages_processed": usage.pages_processed,
                "cache_hit": usage.cache_hit,
                "latency_ms": usage.latency_ms,
                "cost_usd": usage.cost_usd,
                "price_version": usage.price_version,
            },
        )
        await session.flush()
        logger.info(
            "usage_ledger.persisted",
            task_id=task_id,
            tenant_id=tenant_id,
            cost_usd=usage.cost_usd,
        )
    except Exception as exc:
        # usage_ledger có thể chưa được migrate ở Sprint 3
        logger.warning("usage_ledger.persist_failed", error=str(exc))


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _segments_json(citation: CitationItem) -> str:
    return json.dumps(
        [
            {
                "page_no": seg.page_no,
                "line_id": seg.line_id,
                "char_start": seg.char_start,
                "char_end": seg.char_end,
                "bbox": list(seg.bbox),
            }
            for seg in citation.segments
        ]
    )


async def _lookup_dossier_id(session: AsyncSession, document_id: str) -> str | None:
    result = await session.execute(
        text("SELECT dossier_id FROM document WHERE id = :id LIMIT 1"),
        {"id": document_id},
    )
    return result.scalar_one_or_none()


async def _create_review_items(
    session: AsyncSession,
    *,
    tenant_id: str,
    dossier_id: str,
    run_id: str,
    targets: list[tuple[str, str, str, str]],
) -> int:
    """Persist ReviewItem rows so the HITL queue is no longer empty after pipeline."""
    created = 0
    for target_type, target_id, reason, priority in targets:
        item_id = new_ulid("ri_")
        await session.execute(
            text(
                """
                INSERT INTO review_item (
                    id, tenant_id, dossier_id, run_id, target_type, target_id,
                    reason, priority, status, version
                ) VALUES (
                    :id, :tenant_id, :dossier_id, :run_id, :target_type, :target_id,
                    :reason, :priority, 'open', 1
                )
                """
            ),
            {
                "id": item_id,
                "tenant_id": tenant_id,
                "dossier_id": dossier_id,
                "run_id": run_id,
                "target_type": target_type,
                "target_id": target_id,
                "reason": reason[:500],
                "priority": priority,
            },
        )
        created += 1
    await session.flush()
    logger.info(
        "review_items.created",
        dossier_id=dossier_id,
        run_id=run_id,
        count=created,
    )
    return created


async def _build_citation_orm(
    session: AsyncSession,
    citation_id: str,
    tenant_id: str,
    document_id: str,
    citation: CitationItem,
) -> CitationORM | None:
    """Build CitationORM only when Citation Guard accepts the OCR span.

    ``quote_sha256`` is ALWAYS derived from the stored OCR span — never from
    blindly hashing the model's quote string.
    """
    guard = await verify_citation(session, document_id=document_id, citation=citation)
    if not guard.accepted:
        logger.warning(
            "citation_guard.rejected",
            document_id=document_id,
            reason=guard.reason,
            citation_id=citation_id,
        )
        return None

    return CitationORM(
        id=citation_id,
        tenant_id=tenant_id,
        document_id=document_id,
        quote=guard.quote,
        quote_sha256=guard.quote_sha256,
        doc_char_start=citation.doc_char_start,
        doc_char_end=citation.doc_char_end,
        segments=_segments_json(citation),
    )


__all__ = [
    "Ai2PersistenceConflict",
    "Ai2ReadModel",
    "evaluate_ai2_completeness",
    "load_ai2_read_model",
    "persist_ai1_snapshot",
    "persist_ai2_processing_result",
    "persist_ai2_comparison",
    "persist_ai2_extraction",
    "persist_usage_ledger",
    "update_pipeline_run_status",
    "update_pipeline_step",
]
