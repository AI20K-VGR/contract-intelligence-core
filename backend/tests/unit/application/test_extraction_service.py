"""Unit tests for ExtractionService Phase 2 read methods (in-memory fakes)."""

from __future__ import annotations

from typing import Any, BinaryIO
from unittest.mock import AsyncMock

import pytest

from contract_intelligence.extraction.application.services.extraction_service import (
    ExtractionService,
)
from contract_intelligence.shared.exceptions import NotFoundError
from contract_intelligence.shared.storage import FileStorage

pytestmark = pytest.mark.asyncio


class FakePageRepo:
    def __init__(self) -> None:
        self.pages: dict[tuple[str, int], dict[str, Any]] = {}
        self.by_id: dict[str, dict[str, Any]] = {}

    async def list_by_document(self, document_id: str) -> list[dict[str, Any]]:
        return sorted(
            [p for (doc, _), p in self.pages.items() if doc == document_id],
            key=lambda p: p["page_no"],
        )

    async def get_by_document_and_page_no(
        self, document_id: str, page_no: int
    ) -> dict[str, Any] | None:
        return self.pages.get((document_id, page_no))

    async def get(self, page_id: str) -> dict[str, Any] | None:
        return self.by_id.get(page_id)

    async def add(self, page: object) -> None:
        return


class FakeFactRepo:
    def __init__(self) -> None:
        self.effective_rows: list[dict[str, Any]] = []

    async def get(self, fact_id: str) -> dict[str, Any] | None:
        return None

    async def list_by_document(self, document_id: str) -> list[dict[str, Any]]:
        return []

    async def list_by_key(self, key: str) -> list[dict[str, Any]]:
        return []

    async def list_effective_by_dossier(
        self,
        dossier_id: str,
        *,
        key: str | None = None,
        effective: bool = True,
    ) -> list[dict[str, Any]]:
        rows = list(self.effective_rows)
        if key:
            rows = [r for r in rows if r.get("key") == key]
        return rows

    async def add(self, fact: object) -> None:
        return


class FakeClauseRepo:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = rows or []

    async def list_by_document(self, document_id: str) -> list[dict[str, Any]]:
        return list(self.rows)


class FakeTableRepo:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = rows or []

    async def list_by_document(self, document_id: str) -> list[dict[str, Any]]:
        return list(self.rows)


class FakeStorage(FileStorage):
    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}

    async def put(self, key: str, stream: BinaryIO) -> str:
        data = stream.read()
        self.blobs[key] = data
        return key

    async def get(self, blob_uri: str) -> bytes:
        if blob_uri not in self.blobs:
            raise FileNotFoundError(blob_uri)
        return self.blobs[blob_uri]

    async def stream(self, blob_uri: str):  # type: ignore[override]
        yield await self.get(blob_uri)

    async def exists(self, blob_uri: str) -> bool:
        return blob_uri in self.blobs

    async def delete(self, blob_uri: str) -> None:
        self.blobs.pop(blob_uri, None)


@pytest.fixture
def page_repo() -> FakePageRepo:
    return FakePageRepo()


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture
def service(page_repo: FakePageRepo, storage: FakeStorage) -> ExtractionService:
    return ExtractionService(
        pipeline_run_repo=AsyncNoop(),
        page_repo=page_repo,  # type: ignore[arg-type]
        ocr_line_repo=None,
        fact_repo=FakeFactRepo(),  # type: ignore[arg-type]
        citation_repo=AsyncNoop(),  # type: ignore[arg-type]
        clause_repo=FakeClauseRepo(
            [
                {
                    "id": "root",
                    "document_id": "doc_1",
                    "parent_id": None,
                    "node_type": "article",
                    "label": "Dieu 1",
                    "number": "1",
                    "title": "",
                    "text": "body",
                    "page_start": 1,
                    "page_end": 1,
                    "confidence": 1.0,
                    "regions": None,
                }
            ]
        ),
        table_repo=FakeTableRepo(
            [
                {
                    "id": "t1",
                    "document_id": "doc_1",
                    "page_no": 1,
                    "bbox": [0, 0, 10, 10],
                    "rows_count": 1,
                    "cols_count": 1,
                    "has_borders": True,
                    "cells": [{"row_idx": 0, "col_idx": 0, "text": "X"}],
                }
            ]
        ),
        storage=storage,
        orchestrator=AsyncMock(),  # avoid DB-bound get_pipeline_orchestrator()
        tenant_id="tenant_t",
    )


class AsyncNoop:
    async def get(self, *_a: object, **_k: object) -> None:
        return None


class TestGetPageImage:
    async def test_streams_preview(
        self, service: ExtractionService, page_repo: FakePageRepo, storage: FakeStorage
    ) -> None:
        storage.blobs["previews/p1.webp"] = b"WEBP"
        page_repo.pages[("doc_1", 1)] = {
            "id": "pg_1",
            "document_id": "doc_1",
            "page_no": 1,
            "width_pt": 100.0,
            "height_pt": 200.0,
            "preview_uri": "previews/p1.webp",
            "render_uri": "renders/p1.png",
        }
        data, media = await service.get_page_image("doc_1", 1, variant="preview")
        assert data == b"WEBP"
        assert media == "image/webp"

    async def test_missing_page_raises(self, service: ExtractionService) -> None:
        with pytest.raises(NotFoundError):
            await service.get_page_image("doc_1", 99)


class TestListClausesAndTables:
    async def test_clause_tree(self, service: ExtractionService) -> None:
        tree = await service.list_clauses("doc_1")
        assert len(tree) == 1
        assert tree[0].stable_path == "art-1"

    async def test_tables(self, service: ExtractionService) -> None:
        tables = await service.list_tables("doc_1")
        assert tables[0].cells[0].text == "X"


class TestListDossierFacts:
    async def test_maps_current_version(
        self, page_repo: FakePageRepo, storage: FakeStorage
    ) -> None:
        fact_repo = FakeFactRepo()
        fact_repo.effective_rows = [
            {
                "id": "fct_1",
                "document_id": "doc_1",
                "key": "price.total",
                "fact_type": "money",
                "raw_text": "100",
                "normalized_value": '{"amount":100}',
                "confidence": 0.9,
                "extractor": "ner",
                "citation_id": "cit_1",
                "machine_value": '{"amount":100}',
                "effective_value": '{"amount":120}',
                "review_state": "correct",
                "review_item_id": "ri_1",
                "current_version": 3,
            }
        ]
        svc = ExtractionService(
            pipeline_run_repo=AsyncNoop(),
            page_repo=page_repo,  # type: ignore[arg-type]
            ocr_line_repo=None,
            fact_repo=fact_repo,  # type: ignore[arg-type]
            citation_repo=AsyncNoop(),  # type: ignore[arg-type]
            clause_repo=FakeClauseRepo(),
            table_repo=FakeTableRepo(),
            storage=storage,
            orchestrator=AsyncMock(),
            tenant_id="t",
        )
        items = await svc.list_dossier_facts("dos_1")
        assert items[0].current_version == 3
        assert items[0].review_state == "corrected"
        assert items[0].effective_value == {"amount": 120}
