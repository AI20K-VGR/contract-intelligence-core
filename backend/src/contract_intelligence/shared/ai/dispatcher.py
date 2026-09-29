"""Background dispatcher — wrap AI service calls theo cơ chế async.

Pattern (theo DOC-04 ADR-03):
    1. Frontend POST /runs → Backend tạo ``pipeline_run`` + ``task`` row
    2. Backend return 202 ngay (không đợi AI)
    3. BackgroundDispatcher.poll_task(task_id) chạy nền:
        - Submit job sang AI service
        - Poll AI service cho tới khi COMPLETED
        - Validate canonical payload
        - Persist kết quả vào DB
    4. Frontend poll GET /runs/{id} → thấy status chuyển từ running → succeeded

Sprint 3: dispatcher dùng FastAPI BackgroundTasks (in-process).
Khi scale, có thể swap sang Celery/Arq mà application layer không đổi.

Module này được phép import infrastructure (SQLAlchemy) vì là cross-cutting
composition root — KHÔNG vi phạm Dependency Rule (infrastructure ở ngoài cùng).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contract_intelligence.shared.ai.ai1_adapter import adapt_ai1_snapshot_result
from contract_intelligence.shared.ai.client import (
    AiServiceClient,
    get_ai_service_client,
)
from contract_intelligence.shared.ai.persistence import (
    persist_ai1_snapshot,
    persist_ai2_comparison,
    persist_ai2_extraction,
    persist_usage_ledger,
)
from contract_intelligence.shared.ai.schemas import (
    CompareJobRequest,
    ExtractJobRequest,
    JobStatus,
    JobStatusReport,
    OcrJobRequest,
    ReOcrJobRequest,
)
from contract_intelligence.shared.audit import add_audit_event
from contract_intelligence.shared.persistence.session import get_session_factory

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class DispatchTask:
    """Một job sẽ chạy nền.

    Lưu các tham chiếu closure (coroutine factory + task_id) để dispatcher
    có thể chạy mà không giữ reference tới SQLAlchemy session cross-await.
    """

    task_id: int
    kind: str  # "ocr" | "reocr" | "extract" | "compare"
    submit_coroutine: Any  # Callable[..., Awaitable[JobSubmission]]
    request_payload: Any  # OCR/Extract/... request
    tenant_id: str
    attempt_id: int = 1
    poll_interval_seconds: float = 1.5
    max_polls: int = 200  # ≈ 5 phút ở poll_interval=1.5s
    run_id: str | None = None
    dossier_id: str | None = None


class BackgroundDispatcher:
    """Quản lý background polling loop — một instance cho cả process.

    Trong production có thể chia thành N worker processes, mỗi process một
    instance lấy tasks từ queue ``FOR UPDATE SKIP LOCKED``.
    """

    def __init__(self, client: AiServiceClient) -> None:
        self._client = client
        self._running_tasks: dict[int, asyncio.Task[None]] = {}

    async def dispatch_and_poll(self, dispatch_task: DispatchTask) -> None:
        """Submit job + poll tới khi xong, persist result.

        Lifecycle:
            1. submit → JobSubmission
            2. loop poll get_job_status → JobStatusReport
            3. khi COMPLETED → persist result
            4. khi FAILED → mark failed + log
            5. timeout → cancel via cancel_job + mark failed
        """
        try:
            submission = await dispatch_task.submit_coroutine()
            logger.info(
                "dispatcher.submitted",
                task_id=dispatch_task.task_id,
                kind=dispatch_task.kind,
                job_id=submission.job_id,
            )

            for _attempt in range(dispatch_task.max_polls):
                await asyncio.sleep(dispatch_task.poll_interval_seconds)
                report = await self._client.get_job_status(submission.job_id)
                if report.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                    logger.info(
                        "dispatcher.finished",
                        task_id=dispatch_task.task_id,
                        status=report.status.value,
                    )
                    await _persist_result(dispatch_task, report)
                    return
            logger.warning("dispatcher.timeout", task_id=dispatch_task.task_id)
            await self._client.cancel_job(submission.job_id)
            await _persist_result(
                dispatch_task,
                JobStatusReport(
                    job_id=submission.job_id,
                    kind=dispatch_task.kind,
                    status=JobStatus.FAILED,
                    error={
                        "code": "POLL_TIMEOUT",
                        "message": "AI service did not complete in time",
                    },
                ),
            )
        except Exception:
            logger.exception(
                "dispatcher.error",
                task_id=dispatch_task.task_id,
                kind=dispatch_task.kind,
            )

    def schedule(self, dispatch_task: DispatchTask) -> asyncio.Task[None]:
        """Schedule background coroutine — caller không cần await."""
        task = asyncio.create_task(self.dispatch_and_poll(dispatch_task))
        self._running_tasks[dispatch_task.task_id] = task
        return task

    async def shutdown(self) -> None:
        """Drain running tasks — gọi trong app shutdown."""
        for task in list(self._running_tasks.values()):
            task.cancel()
        # Wait briefly
        await asyncio.gather(*self._running_tasks.values(), return_exceptions=True)
        self._running_tasks.clear()


async def _persist_result(
    dispatch_task: DispatchTask,
    report: JobStatusReport,
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> int:
    """Validate + persist a terminal AI job report by ``dispatch_task.kind``.

    Writes the canonical payload (snapshot / extraction / comparison), the
    usage ledger and one ``audit_event`` in a single transaction. Returns the
    number of domain rows written (0 for failed jobs).
    """
    factory = session_factory
    if factory is None:
        try:
            factory = get_session_factory()
        except RuntimeError:
            logger.error("dispatcher.persist_no_db", task_id=dispatch_task.task_id)
            raise

    succeeded = report.status is JobStatus.COMPLETED and isinstance(report.result, dict)
    async with factory() as session:
        try:
            written = 0
            if succeeded:
                written = await _persist_payload(session, dispatch_task, report.result or {})
                if report.usage:
                    await persist_usage_ledger(
                        session,
                        tenant_id=dispatch_task.tenant_id,
                        usage=report.usage,
                        task_id=dispatch_task.task_id,
                        job_kind=dispatch_task.kind,
                    )
            add_audit_event(
                session,
                tenant_id=dispatch_task.tenant_id,
                action=f"ai.{dispatch_task.kind}.{'persisted' if succeeded else 'failed'}",
                entity_type="ai_job",
                entity_id=report.job_id,
                actor_id="system:dispatcher",
                dossier_id=dispatch_task.dossier_id,
                run_id=dispatch_task.run_id,
                to_state=report.status.value,
                detail={
                    "task_id": dispatch_task.task_id,
                    "rows_written": written,
                    "error": report.error,
                },
            )
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception(
                "dispatcher.persist_failed",
                task_id=dispatch_task.task_id,
                kind=dispatch_task.kind,
            )
            raise
    logger.info(
        "dispatcher.persist",
        task_id=dispatch_task.task_id,
        kind=dispatch_task.kind,
        tenant_id=dispatch_task.tenant_id,
        status=report.status.value,
        rows_written=written,
    )
    return written


async def _persist_payload(
    session: AsyncSession, dispatch_task: DispatchTask, result: dict[str, Any]
) -> int:
    if dispatch_task.kind in {"ocr", "reocr"}:
        snapshot = adapt_ai1_snapshot_result(result)
        return await persist_ai1_snapshot(
            session,
            tenant_id=dispatch_task.tenant_id,
            snapshot=snapshot,
            run_id=dispatch_task.run_id,
        )
    if dispatch_task.kind == "extract":
        return await persist_ai2_extraction(
            session,
            tenant_id=dispatch_task.tenant_id,
            extraction=result,
            run_id=dispatch_task.run_id,
        )
    if dispatch_task.kind == "compare":
        return await persist_ai2_comparison(
            session,
            tenant_id=dispatch_task.tenant_id,
            comparison=result,
            run_id=dispatch_task.run_id,
            queue_all_findings=True,
        )
    raise ValueError(f"Unknown dispatch kind: {dispatch_task.kind!r}")


# -----------------------------------------------------------------------------
# Helpers — build DispatchTask từ typed request
# -----------------------------------------------------------------------------


def build_ocr_task(
    *,
    task_id: int,
    req: OcrJobRequest,
    client: AiServiceClient,
    run_id: str | None = None,
    dossier_id: str | None = None,
) -> DispatchTask:
    return DispatchTask(
        task_id=task_id,
        kind="ocr",
        submit_coroutine=lambda: client.submit_ocr(req),
        request_payload=req,
        tenant_id=req.tenant_id,
        run_id=run_id,
        dossier_id=dossier_id,
    )


def build_reocr_task(
    *,
    task_id: int,
    req: ReOcrJobRequest,
    client: AiServiceClient,
    run_id: str | None = None,
    dossier_id: str | None = None,
) -> DispatchTask:
    return DispatchTask(
        task_id=task_id,
        kind="reocr",
        submit_coroutine=lambda: client.submit_reocr(req),
        request_payload=req,
        tenant_id=req.tenant_id,
        run_id=run_id,
        dossier_id=dossier_id,
    )


def build_extract_task(
    *,
    task_id: int,
    req: ExtractJobRequest,
    client: AiServiceClient,
    run_id: str | None = None,
    dossier_id: str | None = None,
) -> DispatchTask:
    return DispatchTask(
        task_id=task_id,
        kind="extract",
        submit_coroutine=lambda: client.submit_extract(req),
        request_payload=req,
        tenant_id=req.tenant_id,
        run_id=run_id,
        dossier_id=dossier_id,
    )


def build_compare_task(
    *,
    task_id: int,
    req: CompareJobRequest,
    client: AiServiceClient,
    run_id: str | None = None,
) -> DispatchTask:
    return DispatchTask(
        task_id=task_id,
        kind="compare",
        submit_coroutine=lambda: client.submit_compare(req),
        request_payload=req,
        tenant_id=req.tenant_id,
        run_id=run_id,
        dossier_id=req.dossier_id,
    )


# -----------------------------------------------------------------------------
# Singleton
# -----------------------------------------------------------------------------

_dispatcher: BackgroundDispatcher | None = None


def get_background_dispatcher() -> BackgroundDispatcher:
    """Singleton — bound to AI service client."""
    global _dispatcher  # noqa: PLW0603
    if _dispatcher is None:
        _dispatcher = BackgroundDispatcher(get_ai_service_client())
    return _dispatcher


def reset_background_dispatcher() -> None:
    """Test helper."""
    global _dispatcher  # noqa: PLW0603
    _dispatcher = None


__all__ = [
    "BackgroundDispatcher",
    "DispatchTask",
    "build_compare_task",
    "build_extract_task",
    "build_ocr_task",
    "build_reocr_task",
    "get_background_dispatcher",
    "reset_background_dispatcher",
]
