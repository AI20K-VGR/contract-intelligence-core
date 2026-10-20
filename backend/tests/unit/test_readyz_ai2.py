"""/readyz checks AI2, the AI service the pipeline really calls over HTTP.

Before, it probed the legacy DOC-05c client (AI_SERVICE_URL, localhost:8001),
which has no service behind it in production: /readyz said "degraded" and
"stub" while AI2 was healthy.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import httpx
import pytest

from contract_intelligence.config.settings import get_settings
from contract_intelligence.shared.ai import health_router

pytestmark = pytest.mark.asyncio

_REAL_ASYNC_CLIENT = httpx.AsyncClient


@pytest.fixture
def http_mode() -> Iterator[Any]:
    settings = get_settings()
    saved = (settings.ai_service_mode, settings.ai2_base_url)
    settings.ai_service_mode = "http"
    settings.ai2_base_url = "http://ai2-service:8002/api/v1"
    yield settings
    settings.ai_service_mode, settings.ai2_base_url = saved


def _use_transport(
    monkeypatch: pytest.MonkeyPatch, handler: Callable[[httpx.Request], httpx.Response]
) -> list[str]:
    seen: list[str] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return handler(request)

    def client(**kwargs: Any) -> httpx.AsyncClient:
        return _REAL_ASYNC_CLIENT(transport=httpx.MockTransport(wrapped), **kwargs)

    monkeypatch.setattr(health_router.httpx, "AsyncClient", client)
    return seen


async def test_probes_ai2_liveness_not_the_legacy_service(
    http_mode: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = _use_transport(monkeypatch, lambda request: httpx.Response(200, json={"ok": True}))
    assert await health_router.ai2_alive() is True
    # /api/v1 is stripped; /readyz (which calls the paid LLM provider) is not used.
    assert seen == ["http://ai2-service:8002/healthz"]


async def test_ai2_error_or_unreachable_is_not_alive(
    http_mode: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use_transport(monkeypatch, lambda request: httpx.Response(503))
    assert await health_router.ai2_alive() is False

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    _use_transport(monkeypatch, refuse)
    assert await health_router.ai2_alive() is False


async def test_readyz_reports_ai2(http_mode: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    async def alive() -> bool:
        return True

    async def dead() -> bool:
        return False

    class _Conn:
        async def __aenter__(self) -> _Conn:
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

        async def execute(self, statement: Any) -> None:
            return None

    class _Engine:
        def connect(self) -> _Conn:
            return _Conn()

    import contract_intelligence.shared.persistence as persistence

    monkeypatch.setattr(persistence, "get_engine", lambda: _Engine())

    monkeypatch.setattr(health_router, "ai2_alive", alive)
    ready = (await health_router.backend_readyz()).data
    assert ready == {
        "status": "ready",
        "checks": {"db_ok": True, "ai_service_ok": True, "ai_service_mode": "live"},
    }

    monkeypatch.setattr(health_router, "ai2_alive", dead)
    degraded = (await health_router.backend_readyz()).data
    assert degraded["status"] == "degraded"
    assert degraded["checks"]["ai_service_mode"] == "unavailable"
