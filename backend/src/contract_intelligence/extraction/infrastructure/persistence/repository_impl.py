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
        git_sha=orm.git_sha or "",
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
        for step_code in ("S0", "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9", "S10"):
            step = PipelineStepORM(
                tenant_id=self._tenant_id,
                run_id=run_id,
                step=step_code,
                status="queued",
            )
            self._session.add(step)
        await self._session.flush()
        return _pipeline_run_to_domain(orm)

    async def list_pipeline_runs(
        self, *, limit: int = 50, offset: int = 0, **filters: Any
    ) -> Page[str]:
        stmt = select(PipelineRunORM).where(PipelineRunORM.tenant_id == self._tenant_id)
        if dossier_id := filters.get("dossier_id"):
            stmt = stmt.where(PipelineRunORM.dossier_id == dossier_id)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int((await self._session.execute(count_stmt)).scalar() or 0)
        stmt = stmt.order_by(PipelineRunORM.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return Page(
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

    async def list_by_key(self, key: str) -> list[dict[str, Any]]:
        stmt = (
            select(FactORM, CitationORM)
            .outerjoin(CitationORM, FactORM.citation_id == CitationORM.id)
            .where(FactORM.key == key, FactORM.tenant_id == self._tenant_id)
        )
        result = await self._session.execute(stmt)
        return [_fact_to_dict(fact, citation) for fact, citation in result.all()]

    async def list_effective_by_dossier(
        self,
        dossier_id: str,
        *,
        key: str | None = None,
        effective: bool = True,
    ) -> list[dict[str, Any]]:
        """List FactEffective rows for a dossier (SQLite/Postgres portable join).

        Equivalent to ``v_fact_effective``: fact + optional review_item + latest
        review_action. ``current_version`` comes from ``review_item.version``
        (0 when no review_item exists).
        """
        from contract_intelligence.contract.infrastructure.persistence.orm import (
            DocumentORM,
        )
        from contract_intelligence.review.infrastructure.persistence.orm import (
            ReviewActionORM,
            ReviewItemORM,
        )

        stmt = (
            select(FactORM, CitationORM)
            .join(DocumentORM, FactORM.document_id == DocumentORM.id)
            .outerjoin(CitationORM, FactORM.citation_id == CitationORM.id)
            .where(
                DocumentORM.dossier_id == dossier_id,
                FactORM.tenant_id == self._tenant_id,
            )
        )
        if key:
            stmt = stmt.where(FactORM.key == key)
        result = await self._session.execute(stmt)
        rows = list(result.all())
        if not rows:
            return []

        fact_ids = [fact.id for fact, _citation in rows]
        review_stmt = select(ReviewItemORM).where(
            ReviewItemORM.tenant_id == self._tenant_id,
            ReviewItemORM.target_type == "fact",
            ReviewItemORM.target_id.in_(fact_ids),
        )
        review_result = await self._session.execute(review_stmt)
        review_by_fact: dict[str, Any] = {ri.target_id: ri for ri in review_result.scalars().all()}

        latest_action_by_item: dict[str, Any] = {}
        if effective and review_by_fact:
            item_ids = [ri.id for ri in review_by_fact.values()]
            action_stmt = (
                select(ReviewActionORM)
                .where(
                    ReviewActionORM.tenant_id == self._tenant_id,
                    ReviewActionORM.review_item_id.in_(item_ids),
                )
                .order_by(ReviewActionORM.created_at.desc())
            )
            action_result = await self._session.execute(action_stmt)
            for act in action_result.scalars().all():
                # First seen per item is latest due to DESC order
                if act.review_item_id not in latest_action_by_item:
                    latest_action_by_item[act.review_item_id] = act

        out: list[dict[str, Any]] = []
        for fact, citation in rows:
            base = _fact_to_dict(fact, citation)
            machine_value = fact.normalized_value
            review_item = review_by_fact.get(fact.id)
            if not effective or review_item is None:
                out.append(
                    {
                        **base,
                        "machine_value": machine_value,
                        "effective_value": machine_value,
                        "review_state": "unreviewed",
                        "reviewer_id": None,
                        "reviewed_at": None,
                        "review_item_id": None,
                        "current_version": 0,
                    }
                )
                continue

            latest = latest_action_by_item.get(review_item.id)
            effective_value = machine_value
            review_state = "unreviewed"
            reviewer_id = None
            reviewed_at = None
            if latest is not None:
                review_state = latest.action
                reviewer_id = latest.reviewer_id
                reviewed_at = latest.created_at
                if latest.action == "correct":
                    effective_value = latest.corrected_value or machine_value
                elif latest.action == "reject":
                    effective_value = None

            out.append(
                {
                    **base,
                    "machine_value": machine_value,
                    "effective_value": effective_value,
                    "review_state": review_state,
                    "reviewer_id": reviewer_id,
                    "reviewed_at": reviewed_at,
                    "review_item_id": review_item.id,
                    "current_version": int(review_item.version or 0),
                }
            )
        return out

    async def add(self, fact: object) -> None:
        """Stub — Protocol conformance."""
        return


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

    async def list_for_document(self, document_id: str, run_id: str) -> list[dict[str, Any]]:
        """Stub — Protocol conformance; full impl filter theo document_id + run_id."""
        return []

    async def add(self, citation: object) -> None:
        """Stub — Protocol conformance."""
        return


# ============================================================================
# Page + OcrLine
# ============================================================================


def _page_to_dict(orm: PageORM) -> dict[str, Any]:
    return {
        "id": orm.id,
        "document_id": orm.document_id,
        "page_no": orm.page_no,
        "width_pt": float(orm.width_pt),
        "height_pt": float(orm.height_pt),
        "rotation": orm.rotation,
        "kind": orm.kind,
        "render_dpi": 300,
        "render_uri": orm.render_blob_uri,
        "preview_uri": orm.preview_blob_uri,
        "render_blob_uri": orm.render_blob_uri,
        "preview_blob_uri": orm.preview_blob_uri,
        "features": orm.features,
    }


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
        return [_page_to_dict(p) for p in result.scalars().all()]

    async def get_by_document_and_page_no(
        self, document_id: str, page_no: int
    ) -> dict[str, Any] | None:
        stmt = select(PageORM).where(
            PageORM.document_id == document_id,
            PageORM.page_no == page_no,
            PageORM.tenant_id == self._tenant_id,
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return _page_to_dict(orm) if orm else None

    async def get(self, page_id: str) -> dict[str, Any] | None:
        stmt = select(PageORM).where(PageORM.id == page_id, PageORM.tenant_id == self._tenant_id)
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
        data = _page_to_dict(orm)
        data["ocr_lines"] = lines
        return data

    async def add(self, page: object) -> None:
        """Stub — Protocol conformance; full impl trong sprint sau."""
        return


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
                "doc_char_start": n.doc_char_start,
                "doc_char_end": n.doc_char_end,
                "regions": n.regions,
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
                "has_borders": t.has_borders,
                "is_multi_page": False,
                "continued_from": None,
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
