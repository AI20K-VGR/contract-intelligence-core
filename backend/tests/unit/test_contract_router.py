"""Router-level unit tests for Phase 1 Contract endpoints.

Tests mock the ContractService at the dependency level and verify:
- HTTP status codes match OpenAPI spec
- Response envelope structure (data, meta)
- RBAC enforcement (OPERATOR/ADMIN vs REVIEWER)
- Error handling (404, 422)
- Multipart upload parsing
- PDF binary streaming

Uses httpx.AsyncClient with ASGITransport — no DB, no MinIO required.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from contract_intelligence.contract.application.services.contract_service import (
    ContractService,
)
from contract_intelligence.contract.domain.entities.document import Document, DocumentRole
from contract_intelligence.contract.domain.entities.dossier import Dossier
from contract_intelligence.main import app
from contract_intelligence.shared.auth.schemas import AuthenticatedUser
from contract_intelligence.shared.exceptions import NotFoundError

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_dossier(**kwargs: Any) -> Dossier:
    """Create a Dossier entity with sensible defaults."""
    defaults: dict[str, Any] = {
        "id": "dos_TEST_01",
        "name": "Test Dossier",
        "batch_id": None,
        "has_conflicts": False,
        "metadata": None,
    }
    defaults.update(kwargs)
    return Dossier(**defaults)


def _make_document(**kwargs: Any) -> Document:
    """Create a Document entity with sensible defaults."""
    defaults: dict[str, Any] = {
        "id": "doc_TEST_01",
        "dossier_id": "dos_TEST_01",
        "role": DocumentRole.CONTRACT,
        "order_index": 0,
        "filename": "contract.pdf",
        "sha256": "abc123",
        "blob_uri": "contracts/dos_TEST_01/ab/contract.pdf",
        "file_size_bytes": 1024,
        "page_count": 5,
        "lang_detected": "vi",
    }
    defaults.update(kwargs)
    return Document(**defaults)


def _operator_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="usr_op_01",
        tenant_id="tenant_test",
        email="operator@test.com",
        display_name="Operator",
        role="OPERATOR",
    )


def _reviewer_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="usr_rev_01",
        tenant_id="tenant_test",
        email="reviewer@test.com",
        display_name="Reviewer",
        role="REVIEWER",
    )


@pytest_asyncio.fixture
async def mock_svc() -> AsyncMock:
    """Create a fully mocked ContractService."""
    return AsyncMock(spec=ContractService)


@pytest_asyncio.fixture
async def client(mock_svc: AsyncMock) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient with ContractService dependency overridden to mock.

    MinIO/Kafka are stubbed globally via ``mock_minio_and_kafka`` (tests/conftest.py).
    """
    from contract_intelligence.contract.interfaces.api.dependencies import (
        get_contract_service,
    )
    from contract_intelligence.shared.auth import get_current_user
    from contract_intelligence.shared.auth.tenant import get_tenant_id

    # Override service dependency
    app.dependency_overrides[get_contract_service] = lambda: mock_svc
    # Override auth to return operator by default
    app.dependency_overrides[get_current_user] = lambda: _operator_user()
    app.dependency_overrides[get_tenant_id] = lambda: "tenant_test"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /api/v1/dossiers
# ---------------------------------------------------------------------------


class TestListDossiersEndpoint:
    async def test_returns_200_with_empty_list(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        mock_svc.list_dossiers.return_value = ([], 0)

        resp = await client.get("/api/v1/dossiers")

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []
        assert "meta" in body

    async def test_returns_200_with_dossier_list(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        dossiers = [
            _make_dossier(id="dos_01", name="Alpha"),
            _make_dossier(id="dos_02", name="Beta"),
        ]
        mock_svc.list_dossiers.return_value = (dossiers, 2)

        resp = await client.get("/api/v1/dossiers")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2
        assert body["data"][0]["id"] == "dos_01"
        assert body["data"][1]["id"] == "dos_02"
        assert body["meta"]["total"] == 2

    async def test_passes_query_params_to_service(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        mock_svc.list_dossiers.return_value = ([], 0)

        await client.get(
            "/api/v1/dossiers",
            params={"q": "contract", "batch_id": "bat_01", "status": "extracted", "limit": 10},
        )

        mock_svc.list_dossiers.assert_called_once()
        call_kwargs = mock_svc.list_dossiers.call_args.kwargs
        assert call_kwargs["q"] == "contract"
        assert call_kwargs["batch_id"] == "bat_01"
        assert call_kwargs["status"] == "extracted"
        assert call_kwargs["limit"] == 10


# ---------------------------------------------------------------------------
# GET /api/v1/dossiers/{dossier_id}
# ---------------------------------------------------------------------------


class TestGetDossierEndpoint:
    async def test_returns_200_with_dossier_detail(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        dossier = _make_dossier(metadata={"tags": ["test"]})
        mock_svc.get_dossier.return_value = dossier
        mock_svc.list_documents.return_value = []

        resp = await client.get("/api/v1/dossiers/dos_TEST_01")

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["id"] == "dos_TEST_01"
        assert body["data"]["name"] == "Test Dossier"
        assert body["data"]["metadata"] == {"tags": ["test"]}
        assert body["data"]["documents"] == []

    async def test_returns_404_when_not_found(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        mock_svc.get_dossier.side_effect = NotFoundError(
            entity_type="Dossier", entity_id="dos_MISSING"
        )

        resp = await client.get("/api/v1/dossiers/dos_MISSING")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/v1/dossiers/{dossier_id}
# ---------------------------------------------------------------------------


class TestPatchDossierEndpoint:
    async def test_returns_200_with_updated_dossier(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        updated = _make_dossier(name="Updated Name", metadata={"priority": "high"})
        mock_svc.patch_dossier.return_value = updated
        mock_svc.list_documents.return_value = []

        resp = await client.patch(
            "/api/v1/dossiers/dos_TEST_01",
            json={"name": "Updated Name", "metadata": {"priority": "high"}},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["name"] == "Updated Name"
        assert body["data"]["metadata"] == {"priority": "high"}

        # Verify service called with correct args
        mock_svc.patch_dossier.assert_called_once_with(
            "dos_TEST_01", name="Updated Name", metadata={"priority": "high"}
        )

    async def test_patch_with_name_only(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        updated = _make_dossier(name="Just Name")
        mock_svc.patch_dossier.return_value = updated
        mock_svc.list_documents.return_value = []

        resp = await client.patch(
            "/api/v1/dossiers/dos_TEST_01",
            json={"name": "Just Name"},
        )

        assert resp.status_code == 200
        mock_svc.patch_dossier.assert_called_once_with(
            "dos_TEST_01", name="Just Name", metadata=None
        )

    async def test_patch_with_metadata_only(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        updated = _make_dossier(metadata={"key": "val"})
        mock_svc.patch_dossier.return_value = updated
        mock_svc.list_documents.return_value = []

        resp = await client.patch(
            "/api/v1/dossiers/dos_TEST_01",
            json={"metadata": {"key": "val"}},
        )

        assert resp.status_code == 200
        mock_svc.patch_dossier.assert_called_once_with(
            "dos_TEST_01", name=None, metadata={"key": "val"}
        )

    async def test_returns_404_when_dossier_not_found(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        mock_svc.patch_dossier.side_effect = NotFoundError(
            entity_type="Dossier", entity_id="dos_MISSING"
        )

        resp = await client.patch(
            "/api/v1/dossiers/dos_MISSING",
            json={"name": "X"},
        )

        assert resp.status_code == 404

    async def test_rbac_rejects_reviewer(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        """PATCH should be rejected for REVIEWER role (only OPERATOR/ADMIN allowed)."""
        from contract_intelligence.shared.auth import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _reviewer_user()

        resp = await client.patch(
            "/api/v1/dossiers/dos_TEST_01",
            json={"name": "Should Fail"},
        )

        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /api/v1/dossiers/{dossier_id}/documents
# ---------------------------------------------------------------------------


class TestListDossierDocumentsEndpoint:
    async def test_returns_200_with_document_list(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        mock_svc.get_dossier.return_value = _make_dossier()
        mock_svc.list_documents.return_value = [
            _make_document(id="doc_01", filename="contract.pdf", order_index=0),
            _make_document(
                id="doc_02",
                filename="annex.pdf",
                role=DocumentRole.ANNEX,
                order_index=1,
            ),
        ]

        resp = await client.get("/api/v1/dossiers/dos_TEST_01/documents")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2
        assert body["data"][0]["filename"] == "contract.pdf"
        assert body["data"][1]["role"] == "ANNEX"

    async def test_returns_404_when_dossier_not_found(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        mock_svc.get_dossier.side_effect = NotFoundError(
            entity_type="Dossier", entity_id="dos_MISSING"
        )

        resp = await client.get("/api/v1/dossiers/dos_MISSING/documents")

        assert resp.status_code == 404

    async def test_returns_empty_list_for_dossier_without_documents(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        mock_svc.get_dossier.return_value = _make_dossier()
        mock_svc.list_documents.return_value = []

        resp = await client.get("/api/v1/dossiers/dos_TEST_01/documents")

        assert resp.status_code == 200
        assert resp.json()["data"] == []


# ---------------------------------------------------------------------------
# GET /api/v1/documents/{document_id}
# ---------------------------------------------------------------------------


class TestGetDocumentEndpoint:
    async def test_returns_200_with_document_detail(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        mock_svc.get_document.return_value = _make_document()

        resp = await client.get("/api/v1/documents/doc_TEST_01")

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["id"] == "doc_TEST_01"
        assert body["data"]["filename"] == "contract.pdf"
        assert body["data"]["role"] == "CONTRACT"
        assert body["data"]["sha256"] == "abc123"
        assert body["data"]["storage_path"] is not None
        assert body["data"]["ocr_status"] == "pending"

    async def test_returns_404_when_document_not_found(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        mock_svc.get_document.side_effect = NotFoundError(
            entity_type="Document", entity_id="doc_MISSING"
        )

        resp = await client.get("/api/v1/documents/doc_MISSING")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/documents/{document_id}/content
# ---------------------------------------------------------------------------


class TestGetDocumentContentEndpoint:
    async def test_returns_200_with_pdf_binary(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        pdf_bytes = b"%PDF-1.4 fake content"
        mock_svc.get_document_blob.return_value = (pdf_bytes, "contract.pdf")

        resp = await client.get("/api/v1/documents/doc_TEST_01/content")

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert "contract.pdf" in resp.headers.get("content-disposition", "")
        assert resp.content == pdf_bytes

    async def test_returns_404_when_document_not_found(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        mock_svc.get_document_blob.side_effect = NotFoundError(
            entity_type="Document", entity_id="doc_MISSING"
        )

        resp = await client.get("/api/v1/documents/doc_MISSING/content")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/v1/dossiers (Multipart upload)
# ---------------------------------------------------------------------------


class TestCreateDossierEndpoint:
    async def test_returns_202_with_dossier_created(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        from contract_intelligence.contract.domain.entities.job import Job, JobStatus

        dossier = _make_dossier(id="dos_NEW_01")
        job = Job(
            id="job_NEW_01",
            dossier_id="dos_NEW_01",
            status=JobStatus.UPLOADED,
        )
        dossier.jobs = [job]
        mock_svc.create_dossier.return_value = dossier
        doc = _make_document(dossier_id="dos_NEW_01")
        mock_svc.upload_document.return_value = doc

        resp = await client.post(
            "/api/v1/dossiers",
            files={
                "contract": ("contract.pdf", b"%PDF-1.4 content", "application/pdf"),
                "metadata": (None, json.dumps({"name": "Test Upload"})),
            },
        )

        assert resp.status_code == 202
        body = resp.json()
        assert body["data"]["dossier_id"] == "dos_NEW_01"
        assert body["data"]["job_id"] == "job_NEW_01"
        mock_svc.create_dossier.assert_called_once()

    async def test_passes_metadata_tags_and_notes(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        from contract_intelligence.contract.domain.entities.job import Job, JobStatus

        dossier = _make_dossier(id="dos_META_01")
        dossier.jobs = [Job(id="job_META_01", dossier_id="dos_META_01", status=JobStatus.UPLOADED)]
        mock_svc.create_dossier.return_value = dossier
        mock_svc.upload_document.return_value = _make_document(dossier_id="dos_META_01")

        resp = await client.post(
            "/api/v1/dossiers",
            files={
                "contract": ("c.pdf", b"%PDF", "application/pdf"),
                "metadata": (
                    None,
                    json.dumps({"name": "Tagged", "tags": ["urgent"], "notes": "review asap"}),
                ),
            },
        )

        assert resp.status_code == 202
        call_kwargs = mock_svc.create_dossier.call_args.kwargs
        assert call_kwargs["name"] == "Tagged"
        assert call_kwargs["metadata"]["tags"] == ["urgent"]
        assert call_kwargs["metadata"]["notes"] == "review asap"

    async def test_returns_422_when_no_contract_file(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        """POST /dossiers without contract file should return 422 (FastAPI validation)."""
        resp = await client.post(
            "/api/v1/dossiers",
            files={
                "metadata": (None, json.dumps({"name": "No contract"})),
            },
        )

        assert resp.status_code == 422

    async def test_rbac_rejects_reviewer(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        """POST /dossiers should reject REVIEWER role."""
        from contract_intelligence.shared.auth import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _reviewer_user()

        resp = await client.post(
            "/api/v1/dossiers",
            files={
                "contract": ("contract.pdf", b"%PDF-1.4", "application/pdf"),
                "metadata": (None, json.dumps({"name": "Should Fail"})),
            },
        )

        assert resp.status_code == 403

    async def test_upload_with_annexes(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        from contract_intelligence.contract.domain.entities.job import Job, JobStatus

        dossier = _make_dossier(id="dos_ANNEX_01")
        dossier.jobs = [
            Job(id="job_ANNEX_01", dossier_id="dos_ANNEX_01", status=JobStatus.UPLOADED)
        ]
        mock_svc.create_dossier.return_value = dossier
        mock_svc.upload_document.return_value = _make_document(dossier_id="dos_ANNEX_01")

        resp = await client.post(
            "/api/v1/dossiers",
            files=[
                ("contract", ("contract.pdf", b"%PDF-main", "application/pdf")),
                ("annexes", ("annex1.pdf", b"%PDF-a1", "application/pdf")),
                ("annexes", ("annex2.pdf", b"%PDF-a2", "application/pdf")),
                ("metadata", (None, json.dumps({"name": "With Annexes"}))),
            ],
        )

        assert resp.status_code == 202
        # contract + 2 annexes
        assert mock_svc.upload_document.call_count == 3
