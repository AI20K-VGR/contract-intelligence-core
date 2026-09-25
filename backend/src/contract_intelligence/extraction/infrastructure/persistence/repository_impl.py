"""Extraction BC repositories — real SQLAlchemy async implementations."""

from __future__ import annotations

import json
import re
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
        job_id: str | None = None,
    ) -> PipelineRun:
        from contract_intelligence.contract.infrastructure.persistence.orm import JobORM
        from contract_intelligence.shared.base import new_ulid, utcnow
        from contract_intelligence.shared.persistence.job_queue import enqueue_job

        resolved_job_id = job_id
        if resolved_job_id is None:
            # Prefer the newest job for this dossier; create one if missing.
            job_stmt = (
                select(JobORM)
                .where(
                    JobORM.dossier_id == dossier_id,
                    JobORM.tenant_id == self._tenant_id,
                )
                .order_by(JobORM.created_at.desc())
                .limit(1)
            )
            existing = (await self._session.execute(job_stmt)).scalar_one_or_none()
            if existing is not None:
                resolved_job_id = existing.id
            else:
                resolved_job_id = new_ulid("job_")
                self._session.add(
                    JobORM(
                        id=resolved_job_id,
                        tenant_id=self._tenant_id,
                        dossier_id=dossier_id,
                        status="uploaded",
                        current_run_id=run_id,
                    )
                )
                await self._session.flush()

        orm = PipelineRunORM(
            id=run_id,
            tenant_id=self._tenant_id,
            job_id=resolved_job_id,
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

        # Enqueue on Postgres job queue (worker claims via SKIP LOCKED).
        await enqueue_job(self._session, job_id=resolved_job_id, current_run_id=run_id)
        # Touch updated_at on job row for observability
        job_row = (
            await self._session.execute(select(JobORM).where(JobORM.id == resolved_job_id))
        ).scalar_one_or_none()
        if job_row is not None:
            job_row.updated_at = utcnow()
            await self._session.flush()

        return _pipeline_run_to_domain(orm)

    async def list_pipeline_runs(
        self, *, limit: int = 50, offset: int = 0, **filters: Any
    ) -> Page[str]:
        stmt = select(PipelineRunORM).where(PipelineRunORM.tenant_id == self._tenant_id)
        if dossier_id := filters.get("dossier_id"):
            stmt = stmt.where(PipelineRunORM.dossier_id == dossier_id)
        status_in = filters.get("status_in")
        if status_in:
            stmt = stmt.where(PipelineRunORM.status.in_(tuple(status_in)))
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
        """List citations for a document.

        ``run_id`` is accepted for Protocol compatibility; citations are keyed
        by ``document_id`` (immutable OCR evidence for the active dossier run).
        """
        _ = run_id
        stmt = select(CitationORM).where(
            CitationORM.document_id == document_id,
            CitationORM.tenant_id == self._tenant_id,
        )
        result = await self._session.execute(stmt)
        return [_citation_to_dict(orm) for orm in result.scalars().all()]

    async def add(self, citation: object) -> None:
        """Persist a domain Citation entity (Protocol conformance)."""
        from contract_intelligence.extraction.domain.entities.citation import Citation

        if not isinstance(citation, Citation):
            return
        orm = CitationORM(
            id=citation.id,
            tenant_id=self._tenant_id,
            document_id=citation.document_id,
            quote=citation.quote,
            quote_sha256=citation.quote_sha256,
            doc_char_start=getattr(citation, "doc_char_start", 0) or 0,
            doc_char_end=getattr(citation, "doc_char_end", 0) or 0,
            segments=json.dumps(getattr(citation, "segments", None) or []),
        )
        self._session.add(orm)
        await self._session.flush()


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


def _table_rows(raw_cells: str) -> dict[int, list[dict[str, Any]]]:
    try:
        cells = json.loads(raw_cells or "[]")
    except (TypeError, json.JSONDecodeError):
        return {}
    rows: dict[int, list[dict[str, Any]]] = {}
    for cell in cells if isinstance(cells, list) else []:
        if not isinstance(cell, dict):
            continue
        try:
            row_index = int(cell.get("row_idx", 0))
        except (TypeError, ValueError):
            continue
        rows.setdefault(row_index, []).append(cell)
    return rows


def _row_text(row: list[dict[str, Any]]) -> str:
    return " ".join(str(cell.get("text") or "").strip() for cell in row).strip().lower()


def _row_anchor(row: list[dict[str, Any]]) -> int | None:
    first = next((cell for cell in row if int(cell.get("col_idx", 0)) == 0), None)
    if not first:
        return None
    match = re.fullmatch(r"\d{1,3}", str(first.get("text") or "").strip())
    return int(match.group()) if match else None


def _last_numeric_anchor(table: dict[str, Any]) -> int | None:
    rows = _table_rows(str(table.get("cells") or ""))
    for row_index in sorted(rows, reverse=True):
        anchor = _row_anchor(rows[row_index])
        if anchor is not None:
            return anchor
        if any(token in _row_text(rows[row_index]) for token in ("tổng", "total", "subtotal")):
            return None
    return None


def _first_numeric_anchor(table: dict[str, Any]) -> int | None:
    rows = _table_rows(str(table.get("cells") or ""))
    for row_index in sorted(rows):
        anchor = _row_anchor(rows[row_index])
        if anchor is not None:
            return anchor
    return None


def _numeric_row_shape(table: dict[str, Any], *, first: bool) -> int:
    rows = _table_rows(str(table.get("cells") or ""))
    indexes = sorted(rows) if first else sorted(rows, reverse=True)
    for row_index in indexes:
        if _row_anchor(rows[row_index]) is not None:
            return len({int(cell.get("col_idx", 0)) for cell in rows[row_index]})
    return 0


def _infer_legacy_continuity(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Recover links for snapshots created before v10 lost table_continuity.

    The only automatic legacy merge signal is a same-width table on the next
    page whose first STT is exactly the previous fragment's last STT + 1. This
    avoids joining unrelated tables that merely share a column count.
    """
    by_page: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        by_page.setdefault(int(row.get("page_no") or 0), []).append(row)
    for page_rows in by_page.values():
        page_rows.sort(key=lambda row: str(row.get("id") or ""))

    for page_no in sorted(by_page):
        previous = by_page.get(page_no - 1, [])
        current = by_page[page_no]
        if not previous or not current:
            continue
        prior = next(
            (
                candidate
                for candidate in reversed(previous)
                if _last_numeric_anchor(candidate) is not None
            ),
            None,
        )
        fragment = next(
            (candidate for candidate in current if _first_numeric_anchor(candidate) is not None),
            None,
        )
        if prior is None or fragment is None:
            continue
        if fragment.get("continued_from") or fragment.get("is_multi_page"):
            continue
        if _numeric_row_shape(prior, first=False) != _numeric_row_shape(fragment, first=True):
            continue
        last_anchor = _last_numeric_anchor(prior)
        first_anchor = _first_numeric_anchor(fragment)
        if last_anchor is None or first_anchor != last_anchor + 1:
            continue
        prior["is_multi_page"] = True
        fragment["is_multi_page"] = True
        fragment["continued_from"] = prior.get("id")
    return rows


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
        rows = [
            {
                "id": t.id,
                "document_id": t.document_id,
                "page_no": t.page_no,
                "bbox": t.bbox,
                "rows_count": t.rows_count,
                "cols_count": t.cols_count,
                "has_borders": t.has_borders,
                "is_multi_page": t.is_multi_page,
                "continued_from": t.continued_from,
                "cells": t.cells,
            }
            for t in result.scalars().all()
        ]
        return _infer_legacy_continuity(rows)


__all__ = [
    "CitationRepositoryImpl",
    "ClauseNodeRepositoryImpl",
    "DocTableRepositoryImpl",
    "FactRepositoryImpl",
    "PageRepositoryImpl",
    "PipelineRunRepositoryImpl",
]
