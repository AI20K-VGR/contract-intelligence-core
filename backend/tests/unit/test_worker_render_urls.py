"""Regression tests for AI1 render URL allocation."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from contract_intelligence import worker

pytestmark = pytest.mark.asyncio


async def test_unknown_page_count_reserves_render_url_for_each_possible_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(worker.storage, "generate_presigned_get_url", AsyncMock(return_value="get"))
    monkeypatch.setattr(
        worker.storage,
        "generate_presigned_put_url",
        AsyncMock(side_effect=lambda *, key: f"put:{key}"),
    )
    document = SimpleNamespace(
        id="doc_1",
        page_count=0,
        blob_uri="s3://dossiers/source.pdf",
        sha256="sha256",
        tenant_id="tenant_1",
        lang_detected="vi",
        role="CONTRACT",
        filename="source.pdf",
    )
    dossier = SimpleNamespace(id="dos_1", tenant_id="tenant_1")

    payload = await worker._build_ocr_command_payload(
        document=document,
        dossier=dossier,
        run_id="run_1",
    )

    put_urls = payload["payload"]["render_target"]["presigned_put_urls"]
    assert len(put_urls) == worker.UNKNOWN_PAGE_RENDER_RESERVE
    assert put_urls["1"] == "put:doc_1/page-001.png"
    assert put_urls[str(worker.UNKNOWN_PAGE_RENDER_RESERVE)] == (
        f"put:doc_1/page-{worker.UNKNOWN_PAGE_RENDER_RESERVE:03d}.png"
    )
