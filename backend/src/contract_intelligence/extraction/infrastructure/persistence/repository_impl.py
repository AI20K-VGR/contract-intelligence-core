"""Extraction BC repositories — real SQLAlchemy async implementations."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.extraction.domain.entities.pipeline_run import (
    PipelineRun,
    PipelineRunStatus,
)
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
from contract_intelligence.shared.base import Page

# ============================================================================
# PipelineRun
# ============================================================================


def _pipeline_run_to_domain(orm: PipelineRunORM) -> PipelineRun:
    return PipelineRun(
        id=orm.id,
        tenant_id=orm.tenant_id,
        dossier_id=orm.dossier_id,
        status=PipelineRunStatus(orm.status),
        pipeline_version=orm.pipeline_version,
        git_sha=orm.git_sha,
        trace_id=orm.trace_id,
        created_at=orm.created_at,
        finished_at=orm.finished_at.isoformat() if orm.finished_at else None,
    )


class PipelineRunRepositoryImpl:
    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def get(self, run_id: str) -> PipelineRun | None:
        stmt = select(PipelineRunORM).where(
            PipelineRunORM.id == run_id, PipelineRunORM.tenant_id == self._tenant_id
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return _pipeline_run_to_domain(orm) if orm else None

    async def create(
        self,
        *,
        run_id: str,
        dossier_id: str,
        pipeline_version: str,
        git_sha: str | None,
        trace_id: str | None,
    ) -> PipelineRun:

        orm = PipelineRunORM(
            id=run_id,
            tenant_id=self._tenant_id,
            job_id=run_id,  # 1:1 placeholder — Sprint 4 sẽ link qua job table
            dossier_id=dossier_id,
            status="queued",
            pipeline_version=pipeline_version,
            git_sha=git_sha or "",
            trace_id=trace_id,
        )
        self._session.add(orm)
        await self._session.flush()

        # Auto-create 11 steps S0..S10
        for step_code in (
            "S0", "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9", "S10"
        ):
            step = PipelineStepORM(
                tenant_id=self._tenant_id,
                run_id=run_id,
                step=step_code,
                status="queued",
            )
            self._session.add(step)
        await self._session.flush()
        return _pipeline_run_to_domain(orm)

    async def list(
        self, *, limit: int = 50, offset: int = 0, **filters: Any
    ) -> Page:
        stmt = select(PipelineRunORM).where(PipelineRunORM.tenant_id == self._tenant_id)
        if dossier_id := filters.get("dossier_id"):
            stmt = stmt.where(PipelineRunORM.dossier_id == dossier_id)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int((await self._session.execute(count_stmt)).scalar() or 0)
        stmt = stmt.order_by(PipelineRunORM.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return BasePage(
            items=[_pipeline_run_to_domain(o) for o in result.scalars().all()],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def update_status(
        self, run_id: str, status: str, *, error_code: str | None = None
    ) -> None:
        from contract_intelligence.shared.base import utcnow

        stmt = select(PipelineRunORM).where(
            PipelineRunORM.id == run_id, PipelineRunORM.tenant_id == self._tenant_id
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm:
            orm.status = status
            orm.error_code = error_code
            if status in ("succeeded", "failed", "cancelled"):
                orm.finished_at = utcnow()
            await self._session.flush()

    async def list_steps(self, run_id: str) -> list[dict[str, Any]]:
        stmt = (
            select(PipelineStepORM)
            .where(
                PipelineStepORM.run_id == run_id,
                PipelineStepORM.tenant_id == self._tenant_id,
            )
            .order_by(PipelineStepORM.id)
        )
        result = await self._session.execute(stmt)
        return [
            {
                "step": s.step,
                "status": s.status,
                "attempt": s.attempt,
                "pages": s.pages,
                "duration_ms": s.duration_ms,
                "created_at": s.created_at.isoformat(),
            }
            for s in result.scalars().all()
        ]


# ============================================================================
# Fact
# ============================================================================


def _fact_to_dict(orm: FactORM, citation: CitationORM | None) -> dict[str, Any]:
    return {
        "id": orm.id,
        "document_id": orm.document_id,
        "key": orm.key,
        "fact_type": orm.fact_type,
        "raw_text": orm.raw_text,
        "normalized_value": orm.normalized_value,
        "confidence": float(orm.confidence),
        "extractor": orm.extractor,
        "context_text": orm.context_text,
        "citation_id": orm.citation_id,
        "citation": _citation_to_dict(citation) if citation else None,
    }


class FactRepositoryImpl:
    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def list_by_document(self, document_id: str) -> list[dict[str, Any]]:
        stmt = (
            select(FactORM, CitationORM)
            .outerjoin(CitationORM, FactORM.citation_id == CitationORM.id)
            .where(
                FactORM.document_id == document_id,
                FactORM.tenant_id == self._tenant_id,
            )
        )
        result = await self._session.execute(stmt)
        return [_fact_to_dict(fact, citation) for fact, citation in result.all()]

    async def get(self, fact_id: str) -> dict[str, Any] | None:
        stmt = (
            select(FactORM, CitationORM)
            .outerjoin(CitationORM, FactORM.citation_id == CitationORM.id)
            .where(FactORM.id == fact_id, FactORM.tenant_id == self._tenant_id)
        )
        result = await self._session.execute(stmt)
        row = result.first()
        if row is None:
            return None
        fact, citation = row
        return _fact_to_dict(fact, citation)


# ============================================================================
# Citation
# ============================================================================


def _citation_to_dict(orm: CitationORM) -> dict[str, Any]:
    return {
        "id": orm.id,
        "document_id": orm.document_id,
        "quote": orm.quote,
        "quote_sha256": orm.quote_sha256,
        "doc_char_start": orm.doc_char_start,
        "doc_char_end": orm.doc_char_end,
        "segments": orm.segments,
    }


class CitationRepositoryImpl:
    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def get(self, citation_id: str) -> dict[str, Any] | None:
        stmt = select(CitationORM).where(
            CitationORM.id == citation_id, CitationORM.tenant_id == self._tenant_id
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return _citation_to_dict(orm) if orm else None


# ============================================================================
# Page + OcrLine
# ============================================================================


class PageRepositoryImpl:
    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def list_by_document(self, document_id: str) -> list[dict[str, Any]]:
        stmt = (
            select(PageORM)
            .where(
                PageORM.document_id == document_id,
                PageORM.tenant_id == self._tenant_id,
            )
            .order_by(PageORM.page_no)
        )
        result = await self._session.execute(stmt)
        return [
            {
                "id": p.id,
                "page_no": p.page_no,
                "width_pt": float(p.width_pt),
                "height_pt": float(p.height_pt),
                "rotation": p.rotation,
                "kind": p.kind,
                "render_blob_uri": p.render_blob_uri,
                "preview_blob_uri": p.preview_blob_uri,
            }
            for p in result.scalars().all()
        ]

    async def get(self, page_id: str) -> dict[str, Any] | None:
        stmt = select(PageORM).where(
            PageORM.id == page_id, PageORM.tenant_id == self._tenant_id
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        # Include OCR lines
        lines_stmt = (
            select(OcrLineORM)
            .where(
                OcrLineORM.document_id == orm.document_id,
                OcrLineORM.page_no == orm.page_no,
                OcrLineORM.tenant_id == self._tenant_id,
            )
            .order_by(OcrLineORM.line_no)
        )
        lines_result = await self._session.execute(lines_stmt)
        lines = [
            {
                "id": ln.id,
                "line_no": ln.line_no,
                "text": ln.text,
                "bbox": ln.bbox,
                "confidence": float(ln.confidence),
                "doc_char_start": ln.doc_char_start,
                "doc_char_end": ln.doc_char_end,
            }
            for ln in lines_result.scalars().all()
        ]
        return {
            "id": orm.id,
            "document_id": orm.document_id,
            "page_no": orm.page_no,
            "width_pt": float(orm.width_pt),
            "height_pt": float(orm.height_pt),
            "rotation": orm.rotation,
            "kind": orm.kind,
            "render_blob_uri": orm.render_blob_uri,
            "preview_blob_uri": orm.preview_blob_uri,
            "ocr_lines": lines,
        }


# ============================================================================
# ClauseNode
# ============================================================================


class ClauseNodeRepositoryImpl:
    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def list_by_document(self, document_id: str) -> list[dict[str, Any]]:
        stmt = (
            select(ClauseNodeORM)
            .where(
                ClauseNodeORM.document_id == document_id,
                ClauseNodeORM.tenant_id == self._tenant_id,
            )
            .order_by(ClauseNodeORM.doc_char_start)
        )
        result = await self._session.execute(stmt)
        return [
            {
                "id": n.id,
                "document_id": n.document_id,
                "parent_id": n.parent_id,
                "node_type": n.node_type,
                "label": n.label,
                "number": n.number,
                "title": n.title,
                "text": n.text,
                "page_start": n.page_start,
                "page_end": n.page_end,
                "confidence": float(n.confidence),
            }
            for n in result.scalars().all()
        ]


# ============================================================================
# DocTable
# ============================================================================


class DocTableRepositoryImpl:
    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def list_by_document(self, document_id: str) -> list[dict[str, Any]]:
        stmt = (
            select(DocTableORM)
            .where(
                DocTableORM.document_id == document_id,
                DocTableORM.tenant_id == self._tenant_id,
            )
            .order_by(DocTableORM.page_no)
        )
        result = await self._session.execute(stmt)
        return [
            {
                "id": t.id,
                "document_id": t.document_id,
                "page_no": t.page_no,
                "bbox": t.bbox,
                "rows_count": t.rows_count,
                "cols_count": t.cols_count,
                "has_borders": t.has_borders == "true",  # type: ignore[comparison-overlap]
                "cells": t.cells,
            }
            for t in result.scalars().all()
        ]


__all__ = [
    "CitationRepositoryImpl",
    "ClauseNodeRepositoryImpl",
    "DocTableRepositoryImpl",
    "FactRepositoryImpl",
    "PageRepositoryImpl",
    "PipelineRunRepositoryImpl",
]
