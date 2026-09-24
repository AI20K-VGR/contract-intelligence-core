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

from contract_intelligence.shared.ai.client import (
    AiServiceClient,
    get_ai_service_client,
)
from contract_intelligence.shared.ai.schemas import (
    CompareJobRequest,
    ExtractJobRequest,
    JobStatus,
    JobStatusReport,
    OcrJobRequest,
    ReOcrJobRequest,
)

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
                    # Persistence hook — concrete implementation sẽ ghi vào DB
                    # theo dispatch_task.kind. Hiện tại chỉ log.
                    await _persist_result(dispatch_task, report)
                    return
            # Timeout — cancel + log
            logger.warning("dispatcher.timeout", task_id=dispatch_task.task_id)
            await self._client.cancel_job(submission.job_id)
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
) -> None:
    """Hook để persist canonical payload xuống DB.

    Sprint 3: chỉ log structured — Sprint 4 sẽ wire persistence theo kind.
    Khi production-ready, các handler sẽ được register theo ``dispatch_task.kind``.
    """
    logger.info(
        "dispatcher.persist",
        task_id=dispatch_task.task_id,
        kind=dispatch_task.kind,
        tenant_id=dispatch_task.tenant_id,
        status=report.status.value,
        has_result=report.result is not None,
        usage_cost=report.usage.cost_usd if report.usage else 0.0,
    )


# -----------------------------------------------------------------------------
# Helpers — build DispatchTask từ typed request
# -----------------------------------------------------------------------------


def build_ocr_task(
    *,
    task_id: int,
    req: OcrJobRequest,
    client: AiServiceClient,
) -> DispatchTask:
    return DispatchTask(
        task_id=task_id,
        kind="ocr",
        submit_coroutine=lambda: client.submit_ocr(req),
        request_payload=req,
        tenant_id=req.tenant_id,
    )


def build_reocr_task(
    *,
    task_id: int,
    req: ReOcrJobRequest,
    client: AiServiceClient,
) -> DispatchTask:
    return DispatchTask(
        task_id=task_id,
        kind="reocr",
        submit_coroutine=lambda: client.submit_reocr(req),
        request_payload=req,
        tenant_id=req.tenant_id,
    )


def build_extract_task(
    *,
    task_id: int,
    req: ExtractJobRequest,
    client: AiServiceClient,
) -> DispatchTask:
    return DispatchTask(
        task_id=task_id,
        kind="extract",
        submit_coroutine=lambda: client.submit_extract(req),
        request_payload=req,
        tenant_id=req.tenant_id,
    )


def build_compare_task(
    *,
    task_id: int,
    req: CompareJobRequest,
    client: AiServiceClient,
) -> DispatchTask:
    return DispatchTask(
        task_id=task_id,
        kind="compare",
        submit_coroutine=lambda: client.submit_compare(req),
        request_payload=req,
        tenant_id=req.tenant_id,
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
