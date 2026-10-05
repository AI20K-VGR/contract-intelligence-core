"""When /query answers from the pinned semantic run and when it still asks AI2.

Only a current run that may still produce a semantic result blocks questions;
a failed/cancelled run or a run pinned to legacy (semantic off) falls back to
AI2 as before.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.integration.test_ai2_review_fixes_flow import BODY_DOCUMENT_ID, DOSSIER_ID, RUN_ID
from tests.integration.test_fe_reported_fixes import (  # noqa: F401 — pytest fixtures
    _QUERY_AI2,
    _ai2_answer,
    client,
    factory,
)

from contract_intelligence.extraction.infrastructure.persistence.orm import PipelineRunORM


async def _set_run(
    factory: async_sessionmaker[AsyncSession],  # noqa: F811
    *,
    status: str,
    config: dict[str, object] | None = None,
) -> None:
    async with factory() as session:
        run = await session.get(PipelineRunORM, RUN_ID)
        assert run is not None
        run.status = status
        run.config_snapshot = json.dumps(config) if config is not None else None
        await session.commit()


async def _query(client: AsyncClient) -> tuple[dict[str, object], AsyncMock]:  # noqa: F811
    with patch(_QUERY_AI2, new=AsyncMock(return_value=_ai2_answer(BODY_DOCUMENT_ID))) as ai2:
        response = await client.post(
            f"/api/v1/dossiers/{DOSSIER_ID}/query", json={"query": "Thời hạn thanh toán?"}
        )
    assert response.status_code == 200, response.text
    return response.json(), ai2


@pytest.mark.asyncio
async def test_pending_semantic_run_blocks_without_calling_ai2(
    factory: async_sessionmaker[AsyncSession],  # noqa: F811
    client: AsyncClient,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI2_SEMANTIC_ENABLED", "true")
    await _set_run(factory, status="running")

    body, ai2 = await _query(client)

    assert body["state"] == "BLOCKED"
    assert body["answer"] == ""
    assert ai2.await_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["failed", "cancelled"])
async def test_ended_run_without_result_falls_back_to_ai2(
    factory: async_sessionmaker[AsyncSession],  # noqa: F811
    client: AsyncClient,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    status: str,
) -> None:
    monkeypatch.setenv("AI2_SEMANTIC_ENABLED", "true")
    await _set_run(factory, status=status)

    body, ai2 = await _query(client)

    assert body["answer"] == "Thanh toán trong 30 ngày."
    assert ai2.await_count == 1


@pytest.mark.asyncio
async def test_run_pinned_to_legacy_falls_back_to_ai2_even_when_semantic_is_on(
    factory: async_sessionmaker[AsyncSession],  # noqa: F811
    client: AsyncClient,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI2_SEMANTIC_ENABLED", "true")
    await _set_run(factory, status="running", config={"semantic_profile": None})

    body, ai2 = await _query(client)

    assert body["answer"] == "Thanh toán trong 30 ngày."
    assert ai2.await_count == 1


@pytest.mark.asyncio
async def test_semantic_off_and_run_not_pinned_falls_back_to_ai2(
    factory: async_sessionmaker[AsyncSession],  # noqa: F811
    client: AsyncClient,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI2_SEMANTIC_ENABLED", "false")
    await _set_run(factory, status="running")

    body, ai2 = await _query(client)

    assert body["answer"] == "Thanh toán trong 30 ngày."
    assert ai2.await_count == 1
