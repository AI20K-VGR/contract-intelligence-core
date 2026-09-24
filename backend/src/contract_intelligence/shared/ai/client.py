"""AI service client — wrap cho ai-service HTTP API (DOC-05c).

Hai implementation:
    1. ``StubAiServiceClient`` — trả về canned responses. Dùng cho dev/test
       khi ai-service chưa sẵn sàng (mặc định).
    2. ``HttpAiServiceClient`` — gọi HTTP thật tới ``settings.ai_service_url``.

Chọn theo ``settings.ai_service_mode``:
    - ``"stub"`` (mặc định Sprint 3) → StubAiServiceClient
    - ``"http"`` (khi ai-service ready) → HttpAiServiceClient

Composition root (FastAPI Depends) gọi ``get_ai_service_client()`` để lấy
instance. Khi AI service team chất lượng, chỉ cần đổi env var ``AI_SERVICE_MODE=http``.

Headers chuẩn (DOC-05c §3):
    X-Internal-Service-Key — pre-shared key
    X-Tenant-Id — tenant scope
    X-Task-Id — BIGSERIAL task trong DB
    X-Attempt-Id — retry attempt
    X-Trace-Id — W3C TraceContext
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import httpx
import structlog

from contract_intelligence.config.settings import Settings, get_settings
from contract_intelligence.shared.ai.schemas import (
    CompareJobRequest,
    ExtractJobRequest,
    JobStatus,
    JobStatusReport,
    JobSubmission,
    OcrJobRequest,
    ReOcrJobRequest,
    UsageLedgerReport,
)

logger = structlog.get_logger(__name__)


# -----------------------------------------------------------------------------
# Abstract Protocol
# -----------------------------------------------------------------------------


class AiServiceClient(ABC):
    """Abstract AI service client — backend luôn depend vào interface này.

    Khi swap stub ↔ http, application/dispatcher không cần thay đổi.
    """

    @abstractmethod
    async def submit_ocr(
        self,
        req: OcrJobRequest,
        *,
        headers: dict[str, str] | None = None,
    ) -> JobSubmission: ...

    @abstractmethod
    async def submit_reocr(
        self,
        req: ReOcrJobRequest,
        *,
        headers: dict[str, str] | None = None,
    ) -> JobSubmission: ...

    @abstractmethod
    async def submit_extract(
        self,
        req: ExtractJobRequest,
        *,
        headers: dict[str, str] | None = None,
    ) -> JobSubmission: ...

    @abstractmethod
    async def submit_compare(
        self,
        req: CompareJobRequest,
        *,
        headers: dict[str, str] | None = None,
    ) -> JobSubmission: ...

    @abstractmethod
    async def get_job_status(self, job_id: str) -> JobStatusReport: ...

    @abstractmethod
    async def cancel_job(self, job_id: str) -> JobStatusReport: ...

    @abstractmethod
    async def healthcheck(self) -> bool: ...


# -----------------------------------------------------------------------------
# Stub implementation — canned responses cho dev/test
# -----------------------------------------------------------------------------


def _stub_usage() -> UsageLedgerReport:
    return UsageLedgerReport(
        provider="stub",
        model_requested="stub-v1",
        model_returned="stub-v1",
        latency_ms=0,
        cost_usd=0.0,
        price_version="stub@dev",
    )


class StubAiServiceClient(AiServiceClient):
    """In-memory stub — trả completed ngay lập tức với data giả.

    Dùng khi ``ai_service_mode=stub`` (mặc định Sprint 3).
    Khi AI service thật chất lượng, switch sang ``HttpAiServiceClient``.
    """

    def __init__(self) -> None:
        # In-memory state cho cancel/healthcheck demo
        self._jobs: dict[str, JobStatusReport] = {}

    async def submit_ocr(
        self,
        req: OcrJobRequest,
        *,
        headers: dict[str, str] | None = None,
    ) -> JobSubmission:
        from ulid import ULID

        job_id = f"ai_job_{ULID()}"
        self._jobs[job_id] = JobStatusReport(
            job_id=job_id,
            kind="ocr",
            status=JobStatus.COMPLETED,
            progress_pct=100,
            current_stage="done",
            finished_at="2026-09-18T00:00:00Z",
            result={
                "schema_version": "ai1.snapshot.v3",
                "document_id": req.document_id,
                "total_pages": len(req.pages_to_process),
                "pages": [],
                "full_text_nfc": f"[STUB OCR text for {req.document_id}]",
                "lines": [],
                "clauses": [],
                "tables": [],
            },
            usage=_stub_usage(),
        )
        return JobSubmission(
            job_id=job_id, kind="ocr", status=JobStatus.QUEUED, created_at="2026-09-18T00:00:00Z"
        )

    async def submit_reocr(
        self,
        req: ReOcrJobRequest,
        *,
        headers: dict[str, str] | None = None,
    ) -> JobSubmission:
        from ulid import ULID

        job_id = f"ai_job_{ULID()}"
        self._jobs[job_id] = JobStatusReport(
            job_id=job_id,
            kind="reocr",
            status=JobStatus.COMPLETED,
            progress_pct=100,
            finished_at="2026-09-18T00:00:00Z",
            usage=_stub_usage(),
        )
        return JobSubmission(
            job_id=job_id, kind="reocr", status=JobStatus.QUEUED, created_at="2026-09-18T00:00:00Z"
        )

    async def submit_extract(
        self,
        req: ExtractJobRequest,
        *,
        headers: dict[str, str] | None = None,
    ) -> JobSubmission:
        from ulid import ULID

        job_id = f"ai_job_{ULID()}"
        self._jobs[job_id] = JobStatusReport(
            job_id=job_id,
            kind="extract",
            status=JobStatus.COMPLETED,
            progress_pct=100,
            finished_at="2026-09-18T00:00:00Z",
            result={
                "schema_version": "ai2.extraction.v2",
                "document_id": req.document_id,
                "facts": [],
                "evidence_gaps": [],
            },
            usage=_stub_usage(),
        )
        return JobSubmission(
            job_id=job_id,
            kind="extract",
            status=JobStatus.QUEUED,
            created_at="2026-09-18T00:00:00Z",
        )

    async def submit_compare(
        self,
        req: CompareJobRequest,
        *,
        headers: dict[str, str] | None = None,
    ) -> JobSubmission:
        from ulid import ULID

        job_id = f"ai_job_{ULID()}"
        self._jobs[job_id] = JobStatusReport(
            job_id=job_id,
            kind="compare",
            status=JobStatus.COMPLETED,
            progress_pct=100,
            finished_at="2026-09-18T00:00:00Z",
            result={
                "schema_version": "ai2.comparison.v2",
                "dossier_id": req.dossier_id,
                "annex_links": [],
                "findings": [],
            },
            usage=_stub_usage(),
        )
        return JobSubmission(
            job_id=job_id,
            kind="compare",
            status=JobStatus.QUEUED,
            created_at="2026-09-18T00:00:00Z",
        )

    async def get_job_status(self, job_id: str) -> JobStatusReport:
        report = self._jobs.get(job_id)
        if report is None:
            return JobStatusReport(
                job_id=job_id,
                kind="unknown",
                status=JobStatus.FAILED,
                error={"code": "UNKNOWN_JOB", "message": "Stub does not retain job state"},
            )
        return report

    async def cancel_job(self, job_id: str) -> JobStatusReport:
        report = self._jobs.get(job_id)
        if report is None:
            return JobStatusReport(
                job_id=job_id,
                kind="unknown",
                status=JobStatus.CANCELLED,
            )
        report.status = JobStatus.CANCELLED
        return report

    async def healthcheck(self) -> bool:
        return True


# -----------------------------------------------------------------------------
# HTTP implementation — gọi ai-service thật
# -----------------------------------------------------------------------------


class HttpAiServiceClient(AiServiceClient):
    """HTTP client cho ai-service (DOC-05c base URL: ``settings.ai_service_url``).

    Singleton AsyncClient với connection pooling.
    Tất cả request tự gắn headers chuẩn (X-Internal-Service-Key, X-Tenant-Id,
    X-Task-Id, X-Attempt-Id, X-Trace-Id).
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if settings.ai_service_api_key:
            headers["X-Internal-Service-Key"] = settings.ai_service_api_key
        self._client = httpx.AsyncClient(
            base_url=settings.ai_service_url,
            timeout=httpx.Timeout(settings.ai_service_timeout_seconds),
            headers=headers,
        )

    def _common_headers(self, *, task_id: int, attempt_id: int, tenant_id: str) -> dict[str, str]:
        return {
            "X-Tenant-Id": tenant_id,
            "X-Task-Id": str(task_id),
            "X-Attempt-Id": str(attempt_id),
        }

    async def _post(
        self,
        path: str,
        body: dict[str, Any],
        extra_headers: dict[str, str],
    ) -> dict[str, Any]:
        response = await self._client.post(path, json=body, headers=extra_headers)
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]

    async def submit_ocr(
        self,
        req: OcrJobRequest,
        *,
        headers: dict[str, str] | None = None,
    ) -> JobSubmission:
        h = {
            **self._common_headers(
                task_id=req.task_id,
                attempt_id=req.attempt_id,
                tenant_id=req.tenant_id,
            ),
            **(headers or {}),
        }
        data = await self._post("/api/v1/jobs/ocr", req.model_dump(mode="json"), h)
        return JobSubmission.model_validate(data)

    async def submit_reocr(
        self,
        req: ReOcrJobRequest,
        *,
        headers: dict[str, str] | None = None,
    ) -> JobSubmission:
        h = {
            **self._common_headers(
                task_id=req.task_id,
                attempt_id=req.attempt_id,
                tenant_id=req.tenant_id,
            ),
            **(headers or {}),
        }
        data = await self._post("/api/v1/jobs/reocr", req.model_dump(mode="json"), h)
        return JobSubmission.model_validate(data)

    async def submit_extract(
        self,
        req: ExtractJobRequest,
        *,
        headers: dict[str, str] | None = None,
    ) -> JobSubmission:
        h = {
            **self._common_headers(
                task_id=req.task_id,
                attempt_id=req.attempt_id,
                tenant_id=req.tenant_id,
            ),
            **(headers or {}),
        }
        data = await self._post("/api/v1/jobs/extract", req.model_dump(mode="json"), h)
        return JobSubmission.model_validate(data)

    async def submit_compare(
        self,
        req: CompareJobRequest,
        *,
        headers: dict[str, str] | None = None,
    ) -> JobSubmission:
        h = {
            **self._common_headers(
                task_id=req.task_id,
                attempt_id=req.attempt_id,
                tenant_id=req.tenant_id,
            ),
            **(headers or {}),
        }
        data = await self._post("/api/v1/jobs/compare", req.model_dump(mode="json"), h)
        return JobSubmission.model_validate(data)

    async def get_job_status(self, job_id: str) -> JobStatusReport:
        response = await self._client.get(f"/api/v1/jobs/{job_id}")
        response.raise_for_status()
        return JobStatusReport.model_validate(response.json())

    async def cancel_job(self, job_id: str) -> JobStatusReport:
        response = await self._client.delete(f"/api/v1/jobs/{job_id}")
        response.raise_for_status()
        return JobStatusReport.model_validate(response.json())

    async def healthcheck(self) -> bool:
        try:
            response = await self._client.get("/healthz", timeout=5.0)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def aclose(self) -> None:
        """Cleanup connection pool — gọi trong app shutdown."""
        await self._client.aclose()


# -----------------------------------------------------------------------------
# Factory + singleton
# -----------------------------------------------------------------------------


_client: AiServiceClient | None = None


def get_ai_service_client() -> AiServiceClient:
    """Singleton factory — gọi 1 lần trong composition root."""
    global _client  # noqa: PLW0603
    if _client is not None:
        return _client

    settings = get_settings()
    if settings.ai_service_mode == "http":
        logger.info("ai_client.http", url=settings.ai_service_url)
        _client = HttpAiServiceClient(settings)
    else:
        logger.info("ai_client.stub", note="ai_service_mode=stub (default)")
        _client = StubAiServiceClient()
    return _client


def reset_ai_service_client() -> None:
    """Reset singleton — gọi trong test teardown."""
    global _client  # noqa: PLW0603
    _client = None


__all__ = [
    "AiServiceClient",
    "HttpAiServiceClient",
    "StubAiServiceClient",
    "get_ai_service_client",
    "reset_ai_service_client",
]
