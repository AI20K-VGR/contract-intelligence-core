"""HTTP client tới AI Service (FastAPI bên ngoài).

Sprint 1: polling. Protocol được application layer reference tới
qua ``AiServicePort`` — định nghĩa ở đây, không trong application
(để tránh application phụ thuộc HTTP lib).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class AiServicePort(Protocol):
    """Protocol — application layer type-hint qua đây."""

    async def submit_extraction_job(self, *, dossier_id: str) -> str:
        """Trả về ai_job_id để polling."""
        ...

    async def poll_extraction_result(self, ai_job_id: str) -> dict[str, object]: ...


class AiServiceClient:
    """Concrete — dùng ``httpx.AsyncClient``."""

    def __init__(self, base_url: str, api_key: str | None = None, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    async def submit_extraction_job(self, *, dossier_id: str) -> str:
        # Sprint 2 — implement HTTP call
        raise NotImplementedError("Sprint 2 — wiring httpx.AsyncClient")

    async def poll_extraction_result(self, ai_job_id: str) -> dict[str, object]:
        raise NotImplementedError


_: type[AiServicePort] = AiServiceClient
