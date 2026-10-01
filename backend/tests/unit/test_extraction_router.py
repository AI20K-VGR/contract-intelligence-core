"""Unit tests for Phase 2 Extraction endpoints (pages, clauses, tables, facts).

Mocks ExtractionService at the DI boundary — no DB / MinIO required.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from contract_intelligence.extraction.application.dtos.clause_dtos import (
    ClauseNodeDTO,
    build_clause_tree,
)
from contract_intelligence.extraction.application.dtos.fact_effective_dtos import (
    FactDTO,
    FactEffectiveDTO,
)
from contract_intelligence.extraction.application.dtos.page_dtos import PageDTO
from contract_intelligence.extraction.application.dtos.table_dtos import DocTableDTO
from contract_intelligence.extraction.application.services.extraction_service import (
    ExtractionService,
)
from contract_intelligence.main import app
from contract_intelligence.shared.auth.schemas import AuthenticatedUser
from contract_intelligence.shared.exceptions import NotFoundError

# asyncio mode=AUTO in pyproject — no module-level asyncio mark needed


def _operator() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="usr_op",
        tenant_id="tenant_test",
        email="op@test.com",
        display_name="Op",
        role="OPERATOR",
    )


@pytest_asyncio.fixture
async def mock_svc() -> AsyncMock:
    return AsyncMock(spec=ExtractionService)


@pytest_asyncio.fixture
async def client(mock_svc: AsyncMock) -> AsyncGenerator[AsyncClient, None]:
    from contract_intelligence.extraction.interfaces.api.dependencies import (
        get_extraction_service,
    )
    from contract_intelligence.shared.auth import get_current_user
    from contract_intelligence.shared.auth.tenant import get_tenant_id

    app.dependency_overrides[get_extraction_service] = lambda: mock_svc
    app.dependency_overrides[get_current_user] = lambda: _operator()
    app.dependency_overrides[get_tenant_id] = lambda: "tenant_test"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


class TestListPages:
    async def test_returns_200_with_pages(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.list_pages.return_value = [
            PageDTO(
                id="pg_1",
                document_id="doc_1",
                page_no=1,
                width_pt=595.0,
                height_pt=842.0,
                preview_uri="previews/pg_1.webp",
                render_uri="renders/pg_1.png",
            )
        ]
        resp = await client.get("/api/v1/documents/doc_1/pages")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["page_no"] == 1
        assert body["data"][0]["preview_uri"] == "previews/pg_1.webp"


class TestGetPageImage:
    async def test_returns_png_binary(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.get_page_image.return_value = (b"\x89PNG", "image/png")
        resp = await client.get("/api/v1/documents/doc_1/pages/1/image")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert resp.content == b"\x89PNG"
        mock_svc.get_page_image.assert_called_once_with("doc_1", 1, variant="preview")

    async def test_passes_render_variant(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.get_page_image.return_value = (b"PNG", "image/png")
        resp = await client.get(
            "/api/v1/documents/doc_1/pages/2/image", params={"variant": "render"}
        )
        assert resp.status_code == 200
        mock_svc.get_page_image.assert_called_once_with("doc_1", 2, variant="render")

    async def test_returns_404_when_missing(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.get_page_image.side_effect = NotFoundError(entity_type="Page", entity_id="doc_1#9")
        resp = await client.get("/api/v1/documents/doc_1/pages/9/image")
        assert resp.status_code == 404


class TestListClauses:
    async def test_returns_clause_tree(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        tree = build_clause_tree(
            [
                {
                    "id": "cl_art",
                    "document_id": "doc_1",
                    "parent_id": None,
                    "node_type": "article",
                    "label": "Dieu 5",
                    "number": "5",
                    "title": "Gia",
                    "text": "...",
                    "page_start": 1,
                    "page_end": 1,
                    "confidence": 0.9,
                    "regions": None,
                },
                {
                    "id": "cl_pt",
                    "document_id": "doc_1",
                    "parent_id": "cl_art",
                    "node_type": "point",
                    "label": "a",
                    "number": "a",
                    "title": "",
                    "text": "100 trieu",
                    "page_start": 1,
                    "page_end": 1,
                    "confidence": 0.8,
                    "regions": '[{"page_no":1,"bbox":[1,2,3,4]}]',
                },
            ]
        )
        mock_svc.list_clauses.return_value = tree
        resp = await client.get("/api/v1/documents/doc_1/clauses")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["node_type"] == "article"
        assert len(data[0]["children"]) == 1
        assert data[0]["stable_path"].startswith("art-5")


class TestListTables:
    async def test_returns_tables(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.list_tables.return_value = [
            DocTableDTO.from_row(
                {
                    "id": "tbl_1",
                    "document_id": "doc_1",
                    "page_no": 2,
                    "bbox": "[0,0,100,50]",
                    "rows_count": 2,
                    "cols_count": 2,
                    "has_borders": "true",
                    "cells": '[{"row_idx":0,"col_idx":0,"text":"A"}]',
                }
            )
        ]
        resp = await client.get("/api/v1/documents/doc_1/tables")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data[0]["rows_count"] == 2
        assert data[0]["cells"][0]["text"] == "A"


class TestListDossierFacts:
    async def test_returns_fact_effective_with_current_version(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        mock_svc.list_dossier_facts.return_value = [
            FactEffectiveDTO(
                fact=FactDTO(
                    id="fct_1",
                    document_id="doc_1",
                    key="price.total",
                    fact_type="money",
                    raw_text="100 trieu",
                    normalized_value={"amount": 100_000_000},
                    confidence=0.95,
                    extractor="ner",
                ),
                machine_value={"amount": 100_000_000},
                effective_value={"amount": 120_000_000},
                review_state="corrected",
                review_item_id="ri_1",
                current_version=2,
            )
        ]
        resp = await client.get("/api/v1/dossiers/dos_1/facts")
        assert resp.status_code == 200
        item = resp.json()["data"][0]
        assert item["fact"]["key"] == "price.total"
        assert item["current_version"] == 2
        assert item["review_state"] == "corrected"
        assert "ETag" in resp.headers

    async def test_passes_key_and_effective_query(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        mock_svc.list_dossier_facts.return_value = []
        await client.get(
            "/api/v1/dossiers/dos_1/facts",
            params={"key": "party.name", "effective": "false"},
        )
        mock_svc.list_dossier_facts.assert_called_once_with(
            "dos_1", key="party.name", effective=False
        )


class TestBuildClauseTreeUnit:
    def test_builds_nested_stable_paths(self) -> None:
        tree = build_clause_tree(
            [
                {
                    "id": "a",
                    "document_id": "d",
                    "parent_id": None,
                    "node_type": "article",
                    "label": "Dieu 1",
                    "number": "1",
                    "text": "",
                    "page_start": 1,
                    "page_end": 1,
                    "confidence": 1.0,
                },
                {
                    "id": "b",
                    "document_id": "d",
                    "parent_id": "a",
                    "node_type": "clause",
                    "label": "Khoan 1",
                    "number": "1",
                    "text": "",
                    "page_start": 1,
                    "page_end": 1,
                    "confidence": 1.0,
                },
            ]
        )
        assert isinstance(tree[0], ClauseNodeDTO)
        assert tree[0].stable_path == "art-1"
        assert tree[0].children[0].stable_path == "art-1/cl-1"
