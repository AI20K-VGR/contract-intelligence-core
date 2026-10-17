"""Server-Timing: app and SQL time per request."""

from __future__ import annotations

import re
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route

from contract_intelligence.shared.server_timing import ServerTimingMiddleware

_HEADER = re.compile(r'^app;dur=(\d+\.\d), db;dur=(\d+\.\d);desc="(\d+) queries"$')


def _app(engine: Any, *, allow_origins: list[str] | None = None) -> Starlette:
    async def two_queries(_: Request) -> JSONResponse:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            await conn.execute(text("SELECT 2"))
        return JSONResponse({"ok": True})

    async def no_query(_: Request) -> JSONResponse:
        return JSONResponse({"ok": True})

    async def stream(_: Request) -> StreamingResponse:
        async def body() -> Any:
            yield b"data: one\n\n"
            yield b"data: two\n\n"

        return StreamingResponse(body(), media_type="text/event-stream")

    app = Starlette(
        routes=[Route("/q", two_queries), Route("/none", no_query), Route("/sse", stream)]
    )
    app.add_middleware(ServerTimingMiddleware, allow_origins=allow_origins)
    return app


@pytest.fixture
async def engine(tmp_path: Any) -> Any:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'timing.db'}")
    yield engine
    await engine.dispose()


async def _get(app: Starlette, path: str) -> Any:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        return await client.get(path)


@pytest.mark.asyncio
async def test_counts_the_sql_statements_of_the_request(engine: Any) -> None:
    app = _app(engine, allow_origins=["https://app.example", "https://other.example"])
    response = await _get(app, "/q")
    match = _HEADER.match(response.headers["server-timing"])
    assert match, response.headers["server-timing"]
    assert int(match.group(3)) == 2
    assert float(match.group(1)) >= float(match.group(2))
    assert response.headers["timing-allow-origin"] == "https://app.example, https://other.example"


@pytest.mark.asyncio
async def test_requests_do_not_share_counts(engine: Any) -> None:
    app = _app(engine)
    await _get(app, "/q")
    response = await _get(app, "/none")
    assert _HEADER.match(response.headers["server-timing"]).group(3) == "0"  # type: ignore[union-attr]
    assert "timing-allow-origin" not in response.headers


@pytest.mark.asyncio
async def test_sql_outside_a_request_is_not_counted(engine: Any) -> None:
    app = _app(engine, allow_origins=["*"])
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 3"))
    response = await _get(app, "/none")
    assert response.headers["server-timing"].endswith('desc="0 queries"')
    assert response.headers["timing-allow-origin"] == "*"


@pytest.mark.asyncio
async def test_streamed_responses_pass_through(engine: Any) -> None:
    response = await _get(_app(engine), "/sse")
    assert response.text == "data: one\n\ndata: two\n\n"
    assert _HEADER.match(response.headers["server-timing"])


@pytest.mark.asyncio
async def test_the_api_sends_the_header() -> None:
    from contract_intelligence.main import app

    response = await _get(app, "/health")  # type: ignore[arg-type]
    assert response.status_code == 200
    assert _HEADER.match(response.headers["server-timing"]), response.headers
