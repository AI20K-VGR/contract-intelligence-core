"""Unit tests for Manifest confirmation validation + router surface."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from contract_intelligence.contract.application.dtos.manifest_dtos import (
    ConfirmManifestRequest,
    ManifestDocumentRole,
    ManifestDTO,
    ManifestMemberDTO,
    ManifestRelationDTO,
    ManifestStatus,
    RelationConfirmation,
    RelationType,
)
from contract_intelligence.contract.application.services.contract_service import (
    ContractService,
)
from contract_intelligence.contract.application.services.manifest_confirmation import (
    validate_and_prepare_confirmation,
)
from contract_intelligence.contract.domain.entities.document import Document, DocumentRole
from contract_intelligence.contract.domain.entities.manifest import Manifest, ManifestRelation
from contract_intelligence.main import app
from contract_intelligence.shared.auth.schemas import AuthenticatedUser
from contract_intelligence.shared.exceptions import (
    DomainErrorCode,
    ManifestValidationError,
    ManifestVersionConflict,
)


def _operator() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="usr_op_01",
        tenant_id="tenant_test",
        email="operator@test.com",
        display_name="Operator",
        role="OPERATOR",
    )


def _reviewer() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="usr_rev_01",
        tenant_id="tenant_test",
        email="reviewer@test.com",
        display_name="Reviewer",
        role="REVIEWER",
    )


def _docs() -> list[Document]:
    return [
        Document(
            id="doc_c1",
            dossier_id="dos_01",
            role=DocumentRole.CONTRACT,
            order_index=0,
            filename="contract.pdf",
            sha256="a",
            blob_uri="x",
            file_size_bytes=10,
            page_count=2,
        ),
        Document(
            id="doc_a1",
            dossier_id="dos_01",
            role=DocumentRole.ANNEX,
            order_index=1,
            filename="annex.pdf",
            sha256="b",
            blob_uri="y",
            file_size_bytes=5,
            page_count=1,
        ),
    ]


def _pending_manifest(*, rel_id: str = "mrel_1") -> Manifest:
    return Manifest(
        id="mft_1",
        dossier_id="dos_01",
        status="pending",
        version=1,
        relations=[
            ManifestRelation(
                id=rel_id,
                manifest_id="mft_1",
                source_document_id="doc_a1",
                target_document_id="doc_c1",
                relation_type="annex_of",
                confirmation="unconfirmed",
            )
        ],
    )


def _valid_body(*, version: int = 1, rel_id: str = "mrel_1") -> ConfirmManifestRequest:
    return ConfirmManifestRequest(
        version=version,
        members=[
            ManifestMemberDTO(
                document_id="doc_c1",
                filename="contract.pdf",
                role=ManifestDocumentRole.CONTRACT,
                included=True,
                order_index=0,
                page_count=2,
                file_size_bytes=10,
            ),
            ManifestMemberDTO(
                document_id="doc_a1",
                filename="annex.pdf",
                role=ManifestDocumentRole.ANNEX,
                included=True,
                order_index=1,
                page_count=1,
                file_size_bytes=5,
            ),
        ],
        relations=[
            ManifestRelationDTO(
                id=rel_id,
                source_document_id="doc_a1",
                target_document_id="doc_c1",
                relation_type=RelationType.ANNEX_OF,
                confirmation=RelationConfirmation.CONFIRMED,
            )
        ],
    )


class TestValidateConfirm:
    def test_version_conflict(self) -> None:
        with pytest.raises(ManifestVersionConflict) as exc:
            validate_and_prepare_confirmation(
                manifest=_pending_manifest(),
                request=_valid_body(version=99),
                dossier_documents=_docs(),
            )
        assert exc.value.code == DomainErrorCode.MANIFEST_VERSION_CONFLICT

    def test_relations_unconfirmed(self) -> None:
        body = _valid_body()
        body.relations[0].confirmation = RelationConfirmation.UNCONFIRMED
        with pytest.raises(ManifestValidationError) as exc:
            validate_and_prepare_confirmation(
                manifest=_pending_manifest(),
                request=body,
                dossier_documents=_docs(),
            )
        assert exc.value.code == DomainErrorCode.RELATIONS_UNCONFIRMED

    def test_relation_missing(self) -> None:
        body = _valid_body()
        body.relations = []
        with pytest.raises(ManifestValidationError) as exc:
            validate_and_prepare_confirmation(
                manifest=_pending_manifest(),
                request=body,
                dossier_documents=_docs(),
            )
        assert exc.value.code == DomainErrorCode.RELATION_MISSING

    def test_contract_required(self) -> None:
        body = _valid_body()
        body.members[0].included = False
        with pytest.raises(ManifestValidationError) as exc:
            validate_and_prepare_confirmation(
                manifest=_pending_manifest(),
                request=body,
                dossier_documents=_docs(),
            )
        assert exc.value.code == DomainErrorCode.CONTRACT_REQUIRED

    def test_member_unknown(self) -> None:
        body = _valid_body()
        body.members.append(
            ManifestMemberDTO(
                document_id="doc_ghost",
                filename="x.pdf",
                role=ManifestDocumentRole.ANNEX,
                included=False,
                order_index=2,
                page_count=0,
                file_size_bytes=0,
            )
        )
        with pytest.raises(ManifestValidationError) as exc:
            validate_and_prepare_confirmation(
                manifest=_pending_manifest(),
                request=body,
                dossier_documents=_docs(),
            )
        assert exc.value.code == DomainErrorCode.MEMBER_UNKNOWN

    def test_relation_self(self) -> None:
        body = _valid_body()
        body.relations[0].target_document_id = "doc_a1"
        with pytest.raises(ManifestValidationError) as exc:
            validate_and_prepare_confirmation(
                manifest=_pending_manifest(),
                request=body,
                dossier_documents=_docs(),
            )
        assert exc.value.code == DomainErrorCode.RELATION_SELF

    def test_success_assigns_ids_for_null_relations(self) -> None:
        body = _valid_body()
        body.relations.append(
            ManifestRelationDTO(
                id=None,
                source_document_id="doc_a1",
                target_document_id="doc_c1",
                relation_type=RelationType.SUPPLEMENTS,
                confirmation=RelationConfirmation.CONFIRMED,
            )
        )
        members, relations = validate_and_prepare_confirmation(
            manifest=_pending_manifest(),
            request=body,
            dossier_documents=_docs(),
        )
        assert len(members) == 2
        assert all(r.id for r in relations)
        assert any(r.relation_type == "supplements" for r in relations)


@pytest_asyncio.fixture
async def mock_svc() -> AsyncMock:
    return AsyncMock(spec=ContractService)


@pytest_asyncio.fixture
async def client(mock_svc: AsyncMock) -> AsyncGenerator[AsyncClient, None]:
    from contract_intelligence.contract.interfaces.api.dependencies import (
        get_contract_service,
    )
    from contract_intelligence.shared.auth import get_current_user
    from contract_intelligence.shared.auth.tenant import get_tenant_id

    app.dependency_overrides[get_contract_service] = lambda: mock_svc
    app.dependency_overrides[get_current_user] = lambda: _operator()
    app.dependency_overrides[get_tenant_id] = lambda: "tenant_test"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


class TestManifestRouter:
    @pytest.mark.asyncio
    async def test_get_manifest_ok(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.get_manifest.return_value = ManifestDTO(
            dossier_id="dos_01",
            status=ManifestStatus.PENDING,
            version=1,
            latest_job_status="uploaded",
            members=[],
            relations=[],
            confirmed_at=None,
        )
        resp = await client.get(
            "/api/v1/dossiers/dos_01/manifest",
            headers={"X-Tenant-Id": "tenant_test", "X-Request-Id": "req-1"},
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert "data" in payload and "meta" in payload
        assert payload["data"]["status"] == "pending"
        assert payload["data"]["version"] == 1

    @pytest.mark.asyncio
    async def test_get_manifest_reviewer_forbidden(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        from contract_intelligence.shared.auth import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _reviewer()
        resp = await client.get(
            "/api/v1/dossiers/dos_01/manifest",
            headers={"X-Tenant-Id": "tenant_test"},
        )
        assert resp.status_code == 403
        mock_svc.get_manifest.assert_not_called()

    @pytest.mark.asyncio
    async def test_confirm_ok(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.confirm_manifest.return_value = ManifestDTO(
            dossier_id="dos_01",
            status=ManifestStatus.CONFIRMED,
            version=2,
            latest_job_status="uploaded",
            members=_valid_body().members,
            relations=_valid_body().relations,
            confirmed_at=None,
        )
        resp = await client.post(
            "/api/v1/dossiers/dos_01/manifest/confirm",
            headers={"X-Tenant-Id": "tenant_test", "Accept": "application/json"},
            json=_valid_body().model_dump(mode="json"),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "confirmed"
        assert resp.json()["data"]["version"] == 2

    @pytest.mark.asyncio
    async def test_confirm_version_conflict(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.confirm_manifest.side_effect = ManifestVersionConflict(
            dossier_id="dos_01",
            expected_version=1,
            current_version=3,
        )
        resp = await client.post(
            "/api/v1/dossiers/dos_01/manifest/confirm",
            headers={"X-Tenant-Id": "tenant_test"},
            json=_valid_body().model_dump(mode="json"),
        )
        assert resp.status_code == 409
        body = resp.json()
        assert body["error"]["code"] == "manifest_version_conflict"

    @pytest.mark.asyncio
    async def test_confirm_relations_unconfirmed(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        mock_svc.confirm_manifest.side_effect = ManifestValidationError(
            DomainErrorCode.RELATIONS_UNCONFIRMED,
            "unconfirmed relations remain",
        )
        resp = await client.post(
            "/api/v1/dossiers/dos_01/manifest/confirm",
            headers={"X-Tenant-Id": "tenant_test"},
            json=_valid_body().model_dump(mode="json"),
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "relations_unconfirmed"
