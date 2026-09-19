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
from datetime import datetime
from typing import Any

import structlog
from sqlalchemy import text
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
from contract_intelligence.shared.ai.schemas import (
    Ai1SnapshotPayload,
    Ai2ComparisonPayload,
    Ai2ExtractionPayload,
    CitationItem,
    UsageLedgerReport,
)
from contract_intelligence.shared.base import new_ulid

logger = structlog.get_logger(__name__)


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
    # Map clause_text_offset_to_id để gắn parent_id
    clause_id_map: dict[str, str] = {}
    for clause in payload.clauses:
        clause_id = new_ulid("cl_")
        clause_id_map[id(clause)] = clause_id  # type: ignore[arg-type]
        clause_orm = ClauseNodeORM(
            id=clause_id,
            tenant_id=tenant_id,
            document_id=document_id,
            parent_id=None,  # Sẽ set sau khi đã có đầy đủ
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
                [{"page_no": r.page_no, "bbox": list(r.bbox), "bbox_source": r.bbox_source}
                 for r in clause.regions]
            )
            if clause.regions
            else None,
        )
        session.add(clause_orm)
        inserted += 1

    # ── Tables ─────────────────────────────────────────────────────────────
    for tbl in payload.tables:
        tbl_id = new_ulid("tb_")
        tbl_orm = DocTableORM(
            id=tbl_id,
            tenant_id=tenant_id,
            document_id=document_id,
            page_no=tbl.page_no,
            bbox=json.dumps(list(tbl.bbox)),
            rows_count=tbl.rows_count,
            cols_count=tbl.cols_count,
            has_borders="true" if tbl.has_borders else "false",
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

    for fact in payload.facts:
        # 1. Citation
        citation_id = new_ulid("cit_")
        citation_orm = _build_citation_orm(citation_id, tenant_id, document_id, fact.citation)
        session.add(citation_orm)

        # 2. Fact
        fact_id = new_ulid("fct_")
        fact_orm = FactORM(
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
        session.add(fact_orm)
        inserted += 1

    await session.flush()
    logger.info(
        "ai2_extraction.persisted",
        document_id=document_id,
        tenant_id=tenant_id,
        run_id=run_id,
        facts=inserted,
        evidence_gaps=len(payload.evidence_gaps),
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

        # side_a citation
        side_a_cit_id = new_ulid("cit_")
        side_a_doc_id = finding.side_a.document_id
        side_a_cit = _build_citation_orm(
            side_a_cit_id, tenant_id, side_a_doc_id, finding.side_a.citation
        )
        session.add(side_a_cit)

        # side_b citation
        side_b_cit_id = new_ulid("cit_")
        side_b_doc_id = finding.side_b.document_id
        side_b_cit = _build_citation_orm(
            side_b_cit_id, tenant_id, side_b_doc_id, finding.side_b.citation
        )
        session.add(side_b_cit)

        await session.execute(
            text(
                """
                INSERT INTO finding (
                    id, tenant_id, dossier_id, finding_type, scope, key_or_topic,
                    disposition, severity, confidence, rationale, method
                ) VALUES (
                    :id, :tenant_id, :dossier_id, :finding_type, :scope, :key_or_topic,
                    :disposition, :severity, :confidence, :rationale, :method
                )
                """
            ),
            {
                "id": finding_id,
                "tenant_id": tenant_id,
                "dossier_id": dossier_id,
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
                    id, finding_id, side, document_id, fact_id, clause_node_id,
                    citation_id, value_snapshot
                ) VALUES (
                    :id, :finding_id, :side, :document_id, :fact_id, :clause_node_id,
                    :citation_id, :value_snapshot
                )
                """
            ),
            {
                "id": new_ulid("fs_"),
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
                    id, finding_id, side, document_id, fact_id, clause_node_id,
                    citation_id, value_snapshot
                ) VALUES (
                    :id, :finding_id, :side, :document_id, :fact_id, :clause_node_id,
                    :citation_id, :value_snapshot
                )
                """
            ),
            {
                "id": new_ulid("fs_"),
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

    await session.flush()
    logger.info(
        "ai2_comparison.persisted",
        dossier_id=dossier_id,
        tenant_id=tenant_id,
        run_id=run_id,
        annex_links=len(payload.annex_links),
        findings=inserted,
    )
    return inserted


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


def _build_citation_orm(
    citation_id: str,
    tenant_id: str,
    document_id: str,
    citation: CitationItem,
) -> CitationORM:
    """Build CitationORM từ CitationItem — id được sinh từ bên ngoài."""
    return CitationORM(
        id=citation_id,
        tenant_id=tenant_id,
        document_id=document_id,
        quote=citation.quote,
        quote_sha256=citation.quote_sha256
        or hashlib.sha256(citation.quote.encode("utf-8")).hexdigest(),
        doc_char_start=citation.doc_char_start,
        doc_char_end=citation.doc_char_end,
        segments=json.dumps(
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
        ),
    )


__all__ = [
    "persist_ai1_snapshot",
    "persist_ai2_comparison",
    "persist_ai2_extraction",
    "persist_usage_ledger",
    "update_pipeline_run_status",
    "update_pipeline_step",
]
