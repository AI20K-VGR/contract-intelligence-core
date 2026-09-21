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
from contract_intelligence.shared.ai.citation_guard import verify_citation
from contract_intelligence.shared.ai.schemas import (
    Ai1SnapshotPayload,
    Ai2ComparisonPayload,
    Ai2ExtractionPayload,
    CitationItem,
    UsageLedgerReport,
)
from contract_intelligence.shared.base import new_ulid
from contract_intelligence.shared.utils import normalize_text

logger = structlog.get_logger(__name__)

# HITL thresholds — facts/findings below these create review_item rows.
_FACT_REVIEW_CONFIDENCE = 0.85
_FINDING_REVIEW_CONFIDENCE = 0.80
_FINDING_REVIEW_DISPOSITIONS = frozenset(
    {"conflict", "needs_review", "uncertain", "ambiguous"}
)


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
    clause_id_map: dict[int, str] = {}
    for clause in payload.clauses:
        clause_id = new_ulid("cl_")
        clause_id_map[id(clause)] = clause_id
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
                [
                    {"page_no": r.page_no, "bbox": list(r.bbox), "bbox_source": r.bbox_source}
                    for r in clause.regions
                ]
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
            review_targets.append(
                ("fact", fact_id, f"citation_guard_rejected:{fact.key}", "P1")
            )

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
                review_targets.append(
                    ("fact", fact_id, f"low_confidence:{fact.key}", priority)
                )

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
    "persist_ai1_snapshot",
    "persist_ai2_comparison",
    "persist_ai2_extraction",
    "persist_usage_ledger",
    "update_pipeline_run_status",
    "update_pipeline_step",
]
