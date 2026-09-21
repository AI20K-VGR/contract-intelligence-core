"""Re-OCR application service.

Tạo yêu cầu Re-OCR cho 1+ trang và dispatch sang AI service qua BackgroundTasks.
Backend là system of record (DOC-04 ADR-03), AI service là stateless worker.

Flow (theo DOC-05c §4.2 — POST /jobs/reocr):
    1. Lưu ReOcrRequest ORM (status=queued)
    2. Submit job tới AI service (cùng headers chuẩn §3)
    3. Poll tới khi COMPLETED → cập nhật ReOcrRequest (status, job_id)
    4. Khi COMPLETED → trả kết quả qua SSE/poll

Bounded retry theo DOC-05c §7.3 — max_attempts từ settings.ai_dispatcher_max_attempts.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.config.settings import get_settings
from contract_intelligence.extraction.application.dtos.reocr_dtos import ReOcrRequestRecordDTO
from contract_intelligence.extraction.infrastructure.persistence.orm_reocr import (
    ReOcrRequestORM,
)

# Import directly from sub-modules to avoid transitive chain through
# shared/ai/__init__.py (which eagerly imports shared.ai.persistence,
# creating a back-reference to extraction.infrastructure).
from contract_intelligence.shared.ai.client import get_ai_service_client
from contract_intelligence.shared.ai.schemas import (
    JobStatus,
    JobStatusReport,
    ReOcrJobRequest,
)
from contract_intelligence.shared.base import new_ulid
from contract_intelligence.shared.exceptions import NotFoundError


class ReOcrService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        tenant_id: str,
    ) -> None:
        self._session = session
        self._tenant_id = tenant_id
        self._settings = get_settings()

    async def create_request(
        self,
        *,
        document_id: str,
        profile: str,
        page_numbers: list[int] | None = None,
        reason: str = "",
        requested_by: str,
        background_tasks: Any | None = None,
        # Back-compat kwargs (pre-OpenAPI)
        page_ids: list[str] | None = None,
        options: dict[str, Any] | None = None,
    ) -> ReOcrRequestRecordDTO:
        """Tạo ReOcrRequest + dispatch sang AI service async."""
        pages = list(page_numbers or [])
        # Legacy page_ids (string) → treat as opaque page references stored alongside numbers
        legacy_ids = list(page_ids or [])
        opts = dict(options or {})
        opts["profile"] = profile
        if pages:
            opts["page_numbers"] = pages

        stored_pages: list[Any] = pages if pages else legacy_ids

        req = ReOcrRequestORM(
            id=new_ulid("req_"),
            tenant_id=self._tenant_id,
            document_id=document_id,
            page_ids=json.dumps(stored_pages),
            reason=reason or f"re-ocr profile={profile}",
            options=json.dumps(opts),
            requested_by=requested_by,
            status="queued",
        )
        self._session.add(req)
        await self._session.flush()

        page_id = f"pg_no_{pages[0]}" if pages else (legacy_ids[0] if legacy_ids else "pg_unknown")
        page_no = pages[0] if pages else 1
        ai_req = ReOcrJobRequest(
            task_id=self._next_task_id(),
            attempt_id=1,
            tenant_id=self._tenant_id,
            document_id=document_id,
            page_id=page_id,
            page_no=page_no,
            source_page_render_url=f"http://minio.internal/renders/{page_id}.png?token=stub",
            crop_bbox=None,
            profile=profile,
            options={
                "deskew": opts.get("deskew", False),
                "denoise": opts.get("denoise", False),
                "enhance_dpi": opts.get("enhance_dpi", 300),
            },
        )

        client = get_ai_service_client()
        submission = await client.submit_reocr(ai_req)
        req.job_id = submission.job_id
        req.status = "running"
        await self._session.flush()

        if background_tasks is not None:
            background_tasks.add_task(
                self._poll_reocr_safely,
                request_id=req.id,
                job_id=submission.job_id,
            )
        else:
            asyncio.create_task(self._poll_reocr_safely(req.id, submission.job_id))

        return self._to_record(req)

    async def list_requests(self, document_id: str) -> list[ReOcrRequestRecordDTO]:
        stmt = (
            select(ReOcrRequestORM)
            .where(
                ReOcrRequestORM.document_id == document_id,
                ReOcrRequestORM.tenant_id == self._tenant_id,
            )
            .order_by(ReOcrRequestORM.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_record(r) for r in result.scalars().all()]

    async def get_request(self, request_id: str) -> ReOcrRequestRecordDTO:
        stmt = select(ReOcrRequestORM).where(
            ReOcrRequestORM.id == request_id,
            ReOcrRequestORM.tenant_id == self._tenant_id,
        )
        result = await self._session.execute(stmt)
        req = result.scalar_one_or_none()
        if req is None:
            raise NotFoundError(entity_type="ReOcrRequest", entity_id=request_id)
        return self._to_record(req)

    # ──────────────────────────────────────────────────────────────────────
    # Background polling — bound to AI service client
    # ──────────────────────────────────────────────────────────────────────

    async def _poll_reocr_safely(self, request_id: str, job_id: str) -> None:
        """Poll AI service cho tới khi job hoàn thành, cập nhật ReOcrRequest."""
        client = get_ai_service_client()
        max_polls = self._settings.ai_dispatcher_max_polls
        interval = self._settings.ai_dispatcher_poll_interval_seconds
        backoff = [interval, interval, interval * 2, interval * 3, interval * 5]

        try:
            for i in range(max_polls):
                await asyncio.sleep(backoff[min(i, len(backoff) - 1)])
                report = await client.get_job_status(job_id)
                if report.status in (
                    JobStatus.COMPLETED,
                    JobStatus.FAILED,
                    JobStatus.CANCELLED,
                ):
                    await self._update_reocr_status(request_id, report)
                    return
            # Timeout — cancel
            await client.cancel_job(job_id)
            await self._update_reocr_status(
                request_id,
                JobStatusReport(
                    job_id=job_id,
                    kind="reocr",
                    status=JobStatus.FAILED,
                    error={"code": "POLL_TIMEOUT", "message": "AI service timeout"},
                ),
            )
        except Exception as exc:
            await self._mark_reocr_failed(request_id, "POLL_ERROR", str(exc))

    async def _update_reocr_status(self, request_id: str, report: JobStatusReport) -> None:
        """Update ReOcrRequest status dựa trên JobStatusReport.

        Mở AsyncSession mới — tránh cross-await session reuse.
        """
        from contract_intelligence.shared.persistence import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            try:
                stmt = select(ReOcrRequestORM).where(
                    ReOcrRequestORM.id == request_id,
                    ReOcrRequestORM.tenant_id == self._tenant_id,
                )
                result = await session.execute(stmt)
                req = result.scalar_one_or_none()
                if req is None:
                    return
                if report.status is JobStatus.COMPLETED:
                    req.status = "succeeded"
                elif report.status is JobStatus.CANCELLED:
                    req.status = "cancelled"
                else:  # FAILED
                    req.status = "failed"
                    err = report.error or {}
                    req.error_code = err.get("code", "UNKNOWN")
                from datetime import datetime

                req.finished_at = datetime.utcnow()
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def _mark_reocr_failed(self, request_id: str, code: str, message: str) -> None:
        try:
            from contract_intelligence.shared.persistence import get_session_factory

            factory = get_session_factory()
            async with factory() as session:
                stmt = select(ReOcrRequestORM).where(
                    ReOcrRequestORM.id == request_id,
                    ReOcrRequestORM.tenant_id == self._tenant_id,
                )
                result = await session.execute(stmt)
                req = result.scalar_one_or_none()
                if req is None:
                    return
                req.status = "failed"
                req.error_code = code
                from datetime import datetime

                req.finished_at = datetime.utcnow()
                await session.commit()
        except Exception:
            pass  # last-resort — không để background crash

    # ──────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────

    def _next_task_id(self) -> int:
        """Stub task_id — Sprint 4 sẽ dùng DB sequence."""
        return int(new_ulid("tsk_").encode()[:8].hex(), 16) % 10_000_000

    @staticmethod
    def _to_record(req: ReOcrRequestORM) -> ReOcrRequestRecordDTO:
        pages = json.loads(req.page_ids) if req.page_ids else []
        opts = json.loads(req.options) if req.options else {}
        profile = str(opts.get("profile") or "high_res_binarize")
        # Prefer explicit page_numbers in options; else coerce stored list
        page_numbers: list[int] = []
        if isinstance(opts.get("page_numbers"), list):
            page_numbers = [int(n) for n in opts["page_numbers"]]
        else:
            for p in pages:
                if isinstance(p, int):
                    page_numbers.append(p)
        return ReOcrRequestRecordDTO.from_row(
            {
                "id": req.id,
                "document_id": req.document_id,
                "profile": profile,
                "page_numbers": page_numbers,
                "status": req.status,
                "job_id": req.job_id,
                "reason": req.reason,
                "requested_by": req.requested_by,
                "created_at": req.created_at,
                "finished_at": req.finished_at,
            }
        )


__all__ = ["ReOcrService"]
