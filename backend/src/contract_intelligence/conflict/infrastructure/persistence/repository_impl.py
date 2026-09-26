"""Conflict BC repositories — real SQLAlchemy async implementations."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.conflict.infrastructure.persistence.orm import (
    AnnexLinkORM,
    FindingORM,
    FindingSideORM,
)
from contract_intelligence.contract.infrastructure.persistence.orm import DocumentORM
from contract_intelligence.extraction.infrastructure.persistence.orm import CitationORM
from contract_intelligence.review.infrastructure.persistence.orm import ReviewItemORM

# disposition values that require reviewer attention (= v_conflict)
_CONFLICT_DISPOSITIONS = (
    "comparable_difference",
    "candidate_amendment",
    "insufficient_evidence",
)
_CONFLICT_CONFIDENCE_THRESHOLD = 0.6


def _citation_payload(orm: CitationORM) -> dict[str, Any]:
    """Quote + segments bbox để UI khoanh đúng chỗ trên từng tài liệu."""
    raw: object = orm.segments
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = []
    segments = raw if isinstance(raw, list) else []
    return {
        "id": orm.id,
        "document_id": orm.document_id,
        "quote": orm.quote,
        "segments": segments,
    }


class FindingRepositoryImpl:
    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def list_by_dossier(
        self,
        dossier_id: str,
        *,
        disposition: str | None = None,
        scope: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        stmt = select(FindingORM).where(
            FindingORM.dossier_id == dossier_id,
            FindingORM.tenant_id == self._tenant_id,
        )
        if disposition:
            stmt = stmt.where(FindingORM.disposition == disposition)
        if scope:
            stmt = stmt.where(FindingORM.scope == scope)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int((await self._session.execute(count_stmt)).scalar() or 0)
        stmt = stmt.order_by(FindingORM.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        findings = list(result.scalars().all())
        enriched = await self._enrich_findings(findings)
        return enriched, total

    async def get(self, finding_id: str) -> dict[str, Any] | None:
        stmt = select(FindingORM).where(
            FindingORM.id == finding_id, FindingORM.tenant_id == self._tenant_id
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        enriched = await self._enrich_findings([orm])
        return enriched[0] if enriched else None

    async def list_conflicts_for_review(
        self,
        dossier_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Findings needing reviewer attention — mirrors ``v_conflict`` view."""
        stmt = (
            select(FindingORM)
            .where(
                FindingORM.dossier_id == dossier_id,
                FindingORM.tenant_id == self._tenant_id,
            )
            .order_by(FindingORM.created_at.desc())
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        # Findings are append-only; a re-run appends a fresh set. Only the
        # latest run reflects the current documents, so older runs are hidden.
        latest_run = next((f.run_id for f in rows if f.run_id), None)
        if latest_run:
            rows = [f for f in rows if f.run_id == latest_run]
        filtered = [
            f
            for f in rows
            if f.disposition in _CONFLICT_DISPOSITIONS
            or float(f.confidence) < _CONFLICT_CONFIDENCE_THRESHOLD
        ]
        total = len(filtered)
        page = filtered[offset : offset + limit]
        enriched = await self._enrich_findings(page)
        return enriched, total

    async def add(self, finding: object) -> None:
        """Stub: real impl sẽ convert dict → FindingORM."""
        return

    async def _enrich_findings(self, findings: list[FindingORM]) -> list[dict[str, Any]]:
        if not findings:
            return []
        finding_ids = [f.id for f in findings]

        sides_stmt = (
            select(FindingSideORM, DocumentORM.role)
            .outerjoin(
                DocumentORM,
                and_(
                    DocumentORM.id == FindingSideORM.document_id,
                    DocumentORM.tenant_id == FindingSideORM.tenant_id,
                ),
            )
            .where(
                FindingSideORM.finding_id.in_(finding_ids),
                FindingSideORM.tenant_id == self._tenant_id,
            )
        )
        sides_result = await self._session.execute(sides_stmt)
        sides_by_finding: dict[str, list[dict[str, Any]]] = {fid: [] for fid in finding_ids}
        for side, doc_role in sides_result.all():
            snapshot = side.value_snapshot
            sides_by_finding.setdefault(side.finding_id, []).append(
                {
                    "side": side.side,
                    "document_id": side.document_id,
                    "document_role": doc_role,
                    "fact_id": side.fact_id,
                    "clause_node_id": side.clause_node_id,
                    "citation_id": side.citation_id,
                    "value_snapshot": snapshot,
                }
            )

        citation_ids = [
            str(side["citation_id"])
            for sides in sides_by_finding.values()
            for side in sides
            if side.get("citation_id")
        ]
        if citation_ids:
            cit_stmt = select(CitationORM).where(
                CitationORM.id.in_(citation_ids),
                CitationORM.tenant_id == self._tenant_id,
            )
            cit_rows = await self._session.execute(cit_stmt)
            by_id = {row.id: _citation_payload(row) for row in cit_rows.scalars().all()}
            for sides in sides_by_finding.values():
                for side in sides:
                    payload = by_id.get(str(side.get("citation_id") or ""))
                    if payload:
                        side["citation"] = payload

        review_stmt = select(ReviewItemORM).where(
            ReviewItemORM.tenant_id == self._tenant_id,
            ReviewItemORM.target_type == "finding",
            ReviewItemORM.target_id.in_(finding_ids),
        )
        review_result = await self._session.execute(review_stmt)
        review_by_finding = {ri.target_id: ri for ri in review_result.scalars().all()}

        return [
            self._finding_to_dict(
                f,
                sides=sides_by_finding.get(f.id, []),
                review=review_by_finding.get(f.id),
            )
            for f in findings
        ]

    def _finding_to_dict(
        self,
        orm: FindingORM,
        *,
        sides: list[dict[str, Any]] | None = None,
        review: ReviewItemORM | None = None,
    ) -> dict[str, Any]:
        review_payload = None
        if review is not None:
            review_payload = {
                "item_id": review.id,
                "status": review.status,
                "current_version": int(review.version or 0),
            }
        return {
            "id": orm.id,
            "dossier_id": orm.dossier_id,
            "run_id": orm.run_id,
            "finding_type": orm.finding_type,
            "scope": orm.scope,
            "key_or_topic": orm.key_or_topic,
            "disposition": orm.disposition,
            "severity": orm.severity,
            "confidence": float(orm.confidence),
            "rationale": orm.rationale,
            "method": orm.method,
            "sides": sides or [],
            "disclaimer": "Kết quả so sánh kỹ thuật, không phải kết luận pháp lý.",
            "review": review_payload,
        }


class AnnexLinkRepositoryImpl:
    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def list_by_dossier(self, dossier_id: str) -> list[dict[str, Any]]:
        stmt = (
            select(AnnexLinkORM)
            .where(
                AnnexLinkORM.dossier_id == dossier_id,
                AnnexLinkORM.tenant_id == self._tenant_id,
            )
            .order_by(AnnexLinkORM.annex_sequence)
        )
        result = await self._session.execute(stmt)
        return [
            {
                "id": o.id,
                "annex_document_id": o.annex_document_id,
                "contract_document_id": o.contract_document_id,
                "score": float(o.score),
                "annex_sequence": int(o.annex_sequence),
                "effective_date": o.effective_date,
                "status": o.status,
                "citation_id": o.citation_id,
            }
            for o in result.scalars().all()
        ]


__all__ = ["AnnexLinkRepositoryImpl", "FindingRepositoryImpl"]
