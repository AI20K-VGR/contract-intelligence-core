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
from tests.pdf_bytes import make_pdf

from contract_intelligence.contract.application.services.contract_service import (
    ContractService,
)
from contract_intelligence.contract.domain.entities.document import Document, DocumentRole
from contract_intelligence.contract.domain.entities.dossier import Dossier
from contract_intelligence.contract.interfaces.api.routers.contract_router import _hits_from_ai2
from contract_intelligence.main import app
from contract_intelligence.shared.auth.schemas import AuthenticatedUser
from contract_intelligence.shared.exceptions import NotFoundError

pytestmark = pytest.mark.asyncio


async def test_ai2_text_span_citation_is_projected_to_fe_hit() -> None:
    hits = _hits_from_ai2(
        {"citations": [{"text_span": "Giá hợp đồng: 1.000.000.000 VND", "page": 9}]}
    )

    assert len(hits) == 1
    assert hits[0].text == "Giá hợp đồng: 1.000.000.000 VND"
    assert hits[0].page_no == 9


async def test_ai2_citation_projection_preserves_source_location() -> None:
    hits = _hits_from_ai2(
        {
            "citations": [
                {
                    "text_span": "Bên A là bên giao thầu.",
                    "source_file_id": "doc-1",
                    "line_ids": ["doc-1:s1:p003:l002"],
                    "page": 3,
                    "bbox": [0.1, 0.2, 0.8, 0.3],
                }
            ]
        }
    )

    assert hits[0].source_file_id == "doc-1"
    assert hits[0].line_id == "doc-1:s1:p003:l002"
    assert hits[0].bbox == [0.1, 0.2, 0.8, 0.3]


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
    """Create a fully mocked ContractService.

    By default the dossier belongs to the operator used by ``client``, so the
    edit/manage ACL passes; tests about other users override it.
    """
    svc = AsyncMock(spec=ContractService)
    svc.get_dossier.return_value = _make_dossier(metadata={"created_by": "usr_op_01"})
    return svc


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
        dossier = _make_dossier(metadata={"tags": ["test"], "created_by": "usr_op_01"})
        mock_svc.get_dossier.return_value = dossier
        mock_svc.list_documents.return_value = []

        resp = await client.get("/api/v1/dossiers/dos_TEST_01")

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["id"] == "dos_TEST_01"
        assert body["data"]["name"] == "Test Dossier"
        assert body["data"]["metadata"] == {
            "tags": ["test"],
            "created_by": "usr_op_01",
        }
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
        mock_svc.get_dossier.return_value = _make_dossier(metadata={"created_by": "usr_op_01"})
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
        mock_svc.get_dossier.return_value = _make_dossier(metadata={"created_by": "usr_op_01"})
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
                "contract": ("contract.pdf", make_pdf(3), "application/pdf"),
                "metadata": (None, json.dumps({"name": "Test Upload"})),
            },
        )

        assert resp.status_code == 202
        body = resp.json()
        assert body["data"]["dossier_id"] == "dos_NEW_01"
        assert body["data"]["job_id"] == "job_NEW_01"
        mock_svc.create_dossier.assert_called_once()
        # The real page count reaches the document, so AI1 gets one render URL per page.
        assert mock_svc.upload_document.call_args.kwargs["page_count"] == 3

    async def test_rejects_unreadable_pdf_before_creating_anything(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        resp = await client.post(
            "/api/v1/dossiers",
            files=[
                ("contract", ("contract.pdf", make_pdf(), "application/pdf")),
                ("annexes", ("broken.pdf", b"%PDF-1.4 not really", "application/pdf")),
                ("metadata", (None, json.dumps({"name": "Broken annex"}))),
            ],
        )

        assert resp.status_code == 422
        assert "broken.pdf" in resp.text
        mock_svc.create_dossier.assert_not_called()
        mock_svc.upload_document.assert_not_called()

    async def test_rejects_file_over_size_limit(
        self, client: AsyncClient, mock_svc: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from contract_intelligence.config.settings import get_settings

        pdf = make_pdf()
        monkeypatch.setattr(get_settings(), "upload_max_file_bytes", len(pdf) - 1)

        resp = await client.post(
            "/api/v1/dossiers",
            files={
                "contract": ("big.pdf", pdf, "application/pdf"),
                "metadata": (None, json.dumps({"name": "Too big"})),
            },
        )

        assert resp.status_code == 413
        mock_svc.create_dossier.assert_not_called()

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
                "contract": ("c.pdf", make_pdf(), "application/pdf"),
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
                ("contract", ("contract.pdf", make_pdf(marker="main"), "application/pdf")),
                ("annexes", ("annex1.pdf", make_pdf(marker="a1"), "application/pdf")),
                ("annexes", ("annex2.pdf", make_pdf(marker="a2"), "application/pdf")),
                ("metadata", (None, json.dumps({"name": "With Annexes"}))),
            ],
        )

        assert resp.status_code == 202
        # contract + 2 annexes
        assert mock_svc.upload_document.call_count == 3


# ---------------------------------------------------------------------------
# POST /api/v1/dossiers/{dossier_id}/ai2/retry
# ---------------------------------------------------------------------------


class TestRetryAi2Endpoint:
    @staticmethod
    def _dossier_with_job(**job_fields: Any) -> Dossier:
        from contract_intelligence.contract.domain.entities.job import Job

        dossier = _make_dossier(id="dos_AI2_01", metadata={"created_by": "usr_op_01"})
        dossier.jobs = [Job(id="job_AI2_01", dossier_id="dos_AI2_01", **job_fields)]
        return dossier

    async def test_publishes_retry_for_the_current_run(
        self, client: AsyncClient, mock_svc: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from contract_intelligence.contract.domain.entities.job import JobStatus
        from contract_intelligence.contract.interfaces.api.routers import contract_router

        mock_svc.get_dossier.return_value = self._dossier_with_job(
            status=JobStatus.FAILED, error_code="AI2_TIMEOUT", current_run_id="run_9"
        )
        publish = AsyncMock()
        monkeypatch.setattr(contract_router.messaging, "publish_event", publish)
        monkeypatch.setattr(contract_router, "_record", AsyncMock())

        resp = await client.post("/api/v1/dossiers/dos_AI2_01/ai2/retry")

        assert resp.status_code == 202
        assert resp.json()["data"]["status"] == "queued"
        publish.assert_awaited_once_with(
            "dossier_events",
            {"event": "dossier.ai2.retry", "dossier_id": "dos_AI2_01", "run_id": "run_9"},
        )

    @pytest.mark.parametrize(
        ("status", "error_code"),
        [("failed", "AI1_TIMEOUT"), ("pending_review", None), ("processing", None)],
    )
    async def test_rejects_when_ai2_did_not_fail(
        self,
        client: AsyncClient,
        mock_svc: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
        status: str,
        error_code: str | None,
    ) -> None:
        from contract_intelligence.contract.domain.entities.job import JobStatus
        from contract_intelligence.contract.interfaces.api.routers import contract_router

        mock_svc.get_dossier.return_value = self._dossier_with_job(
            status=JobStatus(status), error_code=error_code, current_run_id="run_9"
        )
        publish = AsyncMock()
        monkeypatch.setattr(contract_router.messaging, "publish_event", publish)

        resp = await client.post("/api/v1/dossiers/dos_AI2_01/ai2/retry")

        assert resp.status_code == 409
        publish.assert_not_awaited()


# ---------------------------------------------------------------------------
# POST /api/v1/dossiers/{dossier_id}/search  (AI2 /query)
# ---------------------------------------------------------------------------


_AI2_QUERY_TARGET = "contract_intelligence.infrastructure.ai_adapters.query_ai2"


def _owned_dossier(**kwargs: Any) -> Dossier:
    return _make_dossier(metadata={"created_by": "usr_op_01"}, **kwargs)


class TestSearchDossierEndpoint:
    async def test_maps_ai2_citations_to_hits(
        self, client: AsyncClient, mock_svc: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AI2 ``Citation`` dùng ``text_span`` + ``page``; hit phải giữ node/citation id."""
        mock_svc.get_dossier.return_value = _owned_dossier()
        mock_svc.list_documents.return_value = [_make_document()]
        seen: dict[str, Any] = {}

        async def fake_query(payload: dict[str, Any]) -> dict[str, Any]:
            seen.update(payload)
            return {
                "state": "PASS",
                "answer": "Mức trần bồi thường là 100% giá trị dịch vụ.",
                "citations": [
                    {
                        "node_id": "n_6_2",
                        "citation_id": "cit_01",
                        "source_file_id": "doc_TEST_01",
                        "text_span": "Mức trần bồi thường thiệt hại tối đa 100%",
                        "page": 12,
                        "bbox": [0.1, 0.2, 0.9, 0.3],
                        "breadcrumb": ["Điều 6", "6.2"],
                        "structure_path": "Điều 6 > 6.2",
                        "validation_status": "VALID",
                    },
                    {"node_id": "n_empty", "source_file_id": "doc_TEST_01", "text_span": "   "},
                    {
                        "source_file_id": "doc_TEST_01",
                        "text_span": "Phụ lục SLA",
                        "page_range": [36, 37],
                    },
                ],
                "retrieval_layer": {"used_llm": False},
                "reasoning_trace": [{"code": "L1", "message": "Đã khớp 2 nút."}],
            }

        monkeypatch.setattr(_AI2_QUERY_TARGET, fake_query)

        resp = await client.post(
            "/api/v1/dossiers/dos_TEST_01/search",
            json={"query": "Mức trần bồi thường?"},
        )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["connected"] is True
        assert data["state"] == "PASS"
        assert data["answer"].startswith("Mức trần")
        assert data["used_llm"] is False
        assert data["reasoning_trace"] == [{"code": "L1", "message": "Đã khớp 2 nút."}]
        assert len(data["hits"]) == 2
        first = data["hits"][0]
        assert first["text"] == "Mức trần bồi thường thiệt hại tối đa 100%"
        assert first["page_no"] == 12
        assert first["node_id"] == "n_6_2"
        assert first["citation_id"] == "cit_01"
        assert first["breadcrumb"] == ["Điều 6", "6.2"]
        assert first["bbox"] == [0.1, 0.2, 0.9, 0.3]
        assert first["validation_status"] == "VALID"
        assert data["hits"][1]["page_no"] == 36
        # Backend phải chuyển tenant + policy fail-closed sang AI2.
        assert seen["dossier_id"] == "dos_TEST_01"
        assert seen["tenant_id"] == "tenant_test"
        assert seen["actor_id"] == "usr_op_01"
        assert seen["policy_flags"]["egress_allowed"] is False
        assert data["acl_decision"] == "passed"
        # ACL lần 2 phải đọc lại dossier + danh sách tài liệu sau khi AI2 trả lời.
        assert mock_svc.get_dossier.await_count == 2
        mock_svc.list_documents.assert_awaited_once_with("dos_TEST_01")

    async def test_second_acl_pass_drops_foreign_citations(
        self, client: AsyncClient, mock_svc: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_svc.get_dossier.return_value = _owned_dossier()
        mock_svc.list_documents.return_value = [_make_document(id="doc_TEST_01")]

        async def fake_query(payload: dict[str, Any]) -> dict[str, Any]:
            return {
                "state": "PASS",
                "answer": "Trả lời dựa trên tài liệu khác.",
                "citations": [
                    {"text_span": "Điều 1", "source_file_id": "doc_TEST_01", "page": 1},
                    {"text_span": "Bí mật", "source_file_id": "doc_OTHER_TENANT", "page": 2},
                ],
            }

        monkeypatch.setattr(_AI2_QUERY_TARGET, fake_query)

        resp = await client.post("/api/v1/dossiers/dos_TEST_01/search", json={"query": "Điều 1?"})

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["acl_decision"] == "filtered"
        assert data["state"] == "BLOCKED"
        assert data["answer"] is None
        assert [hit["source_file_id"] for hit in data["hits"]] == ["doc_TEST_01"]
        assert any(note.startswith("BACKEND_ACL_FILTERED") for note in data["notes"])

    async def test_second_acl_pass_drops_citations_without_document_ref(
        self, client: AsyncClient, mock_svc: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_svc.get_dossier.return_value = _owned_dossier()
        mock_svc.list_documents.return_value = [_make_document(id="doc_TEST_01")]

        async def fake_query(payload: dict[str, Any]) -> dict[str, Any]:
            return {
                "state": "PASS",
                "answer": "Trích từ nguồn không rõ.",
                "citations": [{"text_span": "Không rõ tài liệu", "page": 3}],
                "retrieval_layer": {"used_llm": True, "node_ids": ["n_x"]},
                "reasoning_trace": [{"code": "L1", "message": "Trích: 'Không rõ tài liệu'"}],
            }

        monkeypatch.setattr(_AI2_QUERY_TARGET, fake_query)

        resp = await client.post("/api/v1/dossiers/dos_TEST_01/search", json={"query": "?"})

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["acl_decision"] == "filtered"
        assert data["answer"] is None
        assert data["hits"] == []
        assert data["retrieval_layer"] == {}
        assert [step["code"] for step in data["reasoning_trace"]] == ["BACKEND_ACL_FILTERED"]

    async def test_second_acl_pass_blocks_when_access_revoked_mid_query(
        self, client: AsyncClient, mock_svc: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Lần 1: còn quyền. Lần 2 (sau AI2): hồ sơ đã chuyển chủ, không còn share.
        mock_svc.get_dossier.side_effect = [
            _owned_dossier(),
            _make_dossier(metadata={"created_by": "usr_someone_else"}),
        ]
        mock_svc.list_documents.return_value = [_make_document()]

        async def fake_query(payload: dict[str, Any]) -> dict[str, Any]:
            return {
                "state": "PASS",
                "answer": "Nội dung nhạy cảm",
                "citations": [{"text_span": "x", "source_file_id": "doc_TEST_01"}],
            }

        monkeypatch.setattr(_AI2_QUERY_TARGET, fake_query)

        resp = await client.post("/api/v1/dossiers/dos_TEST_01/search", json={"query": "?"})

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["acl_decision"] == "denied"
        assert data["state"] == "BLOCKED"
        assert data["answer"] is None
        assert data["hits"] == []

    async def test_rate_limit_returns_429(
        self, client: AsyncClient, mock_svc: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from contract_intelligence.config.settings import get_settings

        monkeypatch.setattr(get_settings(), "query_rate_limit_per_minute", 2)
        mock_svc.get_dossier.return_value = _owned_dossier()
        mock_svc.list_documents.return_value = [_make_document()]
        calls = 0

        async def fake_query(payload: dict[str, Any]) -> dict[str, Any]:
            nonlocal calls
            calls += 1
            return {"state": "PASS", "answer": "ok", "citations": []}

        monkeypatch.setattr(_AI2_QUERY_TARGET, fake_query)

        statuses = [
            (
                await client.post("/api/v1/dossiers/dos_TEST_01/search", json={"query": "q"})
            ).status_code
            for _ in range(3)
        ]
        blocked = await client.post("/api/v1/dossiers/dos_TEST_01/search", json={"query": "q"})

        assert statuses == [200, 200, 429]
        assert blocked.status_code == 429
        assert blocked.headers["Retry-After"]
        assert "RATE_LIMITED" in blocked.text
        assert calls == 2  # request bị chặn không được chuyển sang AI2

    async def test_reports_not_connected_when_ai2_down(
        self, client: AsyncClient, mock_svc: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from contract_intelligence.infrastructure.ai_adapters import AiAdapterError

        mock_svc.get_dossier.return_value = _owned_dossier()

        async def failing_query(payload: dict[str, Any]) -> dict[str, Any]:
            raise AiAdapterError("connection refused")

        monkeypatch.setattr(_AI2_QUERY_TARGET, failing_query)

        resp = await client.post(
            "/api/v1/dossiers/dos_TEST_01/search",
            json={"query": "Điều 1 nói gì?"},
        )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data == {
            "query": "Điều 1 nói gì?",
            "answer": None,
            "connected": False,
            "hits": [],
            "state": "INSUFFICIENT_EVIDENCE",
            "used_llm": False,
            "notes": [],
            "retrieval_layer": {},
            "reasoning_trace": [],
            "trace_id": None,
            "acl_decision": None,
        }

    async def test_rejects_blank_query(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        resp = await client.post(
            "/api/v1/dossiers/dos_TEST_01/search",
            json={"query": "   "},
        )
        assert resp.status_code == 422

    async def test_returns_404_when_dossier_missing(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        mock_svc.get_dossier.side_effect = NotFoundError(
            entity_type="Dossier", entity_id="dos_MISSING"
        )
        resp = await client.post(
            "/api/v1/dossiers/dos_MISSING/search",
            json={"query": "abc"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/v1/dossiers/{dossier_id}/access — permission + expiry (DOC-11 #10)
# ---------------------------------------------------------------------------


class TestDossierAccessPermissions:
    @staticmethod
    def _body(**grant: Any) -> dict[str, Any]:
        return {
            "scope": "shared_out",
            "shared_with": [{"id": "usr_guest", "email": "", **grant}],
        }

    async def test_owner_stores_permission_and_utc_expiry(
        self, client: AsyncClient, mock_svc: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from contract_intelligence.contract.interfaces.api.routers import contract_router

        monkeypatch.setattr(contract_router, "_record", AsyncMock())
        resp = await client.put(
            "/api/v1/dossiers/dos_TEST_01/access",
            json=self._body(permission="read", expires_at="2099-01-01T07:00:00+07:00"),
        )

        assert resp.status_code == 200, resp.text
        grant = resp.json()["data"]["shared_with"][0]
        assert grant["permission"] == "read"
        stored = mock_svc.patch_dossier.await_args.kwargs
        assert stored["acl_update"] is True
        assert stored["metadata"]["shared_with"][0]["expires_at"] == "2099-01-01T00:00:00+00:00"

    async def test_missing_permission_keeps_edit(
        self, client: AsyncClient, mock_svc: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from contract_intelligence.contract.interfaces.api.routers import contract_router

        monkeypatch.setattr(contract_router, "_record", AsyncMock())
        resp = await client.put("/api/v1/dossiers/dos_TEST_01/access", json=self._body())
        assert resp.status_code == 200
        stored = mock_svc.patch_dossier.await_args.kwargs["metadata"]["shared_with"][0]
        assert stored["permission"] == "edit"
        assert stored["expires_at"] is None

    async def test_rejects_expiry_in_the_past(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        resp = await client.put(
            "/api/v1/dossiers/dos_TEST_01/access",
            json=self._body(expires_at="2020-01-01T00:00:00Z"),
        )
        assert resp.status_code == 422
        mock_svc.patch_dossier.assert_not_awaited()

    async def test_rejects_unknown_permission(self, client: AsyncClient) -> None:
        resp = await client.put(
            "/api/v1/dossiers/dos_TEST_01/access", json=self._body(permission="owner")
        )
        assert resp.status_code == 422

    async def test_only_owner_or_admin_changes_access(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        mock_svc.get_dossier.return_value = _make_dossier(
            metadata={
                "created_by": "usr_someone_else",
                "access_scope": "shared_out",
                "shared_with": [{"id": "usr_op_01", "permission": "edit"}],
            }
        )
        resp = await client.put("/api/v1/dossiers/dos_TEST_01/access", json=self._body())
        assert resp.status_code == 403
        mock_svc.patch_dossier.assert_not_awaited()

    async def test_read_grant_cannot_edit(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.get_dossier.return_value = _make_dossier(
            metadata={
                "created_by": "usr_someone_else",
                "access_scope": "shared_out",
                "shared_with": [{"id": "usr_op_01", "permission": "read"}],
            }
        )
        resp = await client.patch("/api/v1/dossiers/dos_TEST_01", json={"name": "x"})
        assert resp.status_code == 403
        resp = await client.post("/api/v1/dossiers/dos_TEST_01/ocr")
        assert resp.status_code == 403
        mock_svc.patch_dossier.assert_not_awaited()
        # Read still works.
        mock_svc.list_documents.return_value = []
        resp = await client.get("/api/v1/dossiers/dos_TEST_01/documents")
        assert resp.status_code == 200


class TestRetryFailedOcrEndpoint:
    @staticmethod
    def _dossier(**job_fields: Any) -> Dossier:
        from contract_intelligence.contract.domain.entities.job import Job

        dossier = _make_dossier(id="dos_R", metadata={"created_by": "usr_op_01"})
        dossier.jobs = [Job(id="job_R", dossier_id="dos_R", **job_fields)]
        return dossier

    async def test_publishes_retry_failed_for_an_ocr_failure(
        self, client: AsyncClient, mock_svc: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from contract_intelligence.contract.domain.entities.job import JobStatus
        from contract_intelligence.contract.interfaces.api.routers import contract_router

        mock_svc.get_dossier.return_value = self._dossier(
            status=JobStatus.FAILED, error_code="AI1_TIMEOUT", current_run_id="run_1"
        )
        publish = AsyncMock()
        monkeypatch.setattr(contract_router.messaging, "publish_event", publish)
        monkeypatch.setattr(contract_router, "_record", AsyncMock())

        resp = await client.post("/api/v1/dossiers/dos_R/ocr/retry-failed")

        assert resp.status_code == 202
        publish.assert_awaited_once_with(
            "dossier_events",
            {
                "event": "dossier.uploaded",
                "dossier_id": "dos_R",
                "restart": True,
                "retry_failed": True,
            },
        )

    @pytest.mark.parametrize(
        ("status_value", "error_code"),
        [("failed", "AI2_TIMEOUT"), ("pending_review", None), ("processing", None)],
    )
    async def test_rejects_when_ocr_did_not_fail(
        self, client: AsyncClient, mock_svc: AsyncMock, status_value: str, error_code: str | None
    ) -> None:
        from contract_intelligence.contract.domain.entities.job import JobStatus

        mock_svc.get_dossier.return_value = self._dossier(
            status=JobStatus(status_value), error_code=error_code, current_run_id="run_1"
        )
        resp = await client.post("/api/v1/dossiers/dos_R/ocr/retry-failed")
        assert resp.status_code == 409
