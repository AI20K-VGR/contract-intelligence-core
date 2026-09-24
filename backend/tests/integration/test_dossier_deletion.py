"""Integration tests for 2-step dossier deletion (tombstone + purge)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tests.unit.conftest_contract import FakeFileStorage

from contract_intelligence.config.settings import get_settings
from contract_intelligence.contract.infrastructure.persistence.orm import (
    DeletionLedgerORM,
    DocumentORM,
    DossierORM,
    JobORM,
)
from contract_intelligence.main import app
from contract_intelligence.shared.persistence import Base, bind_engine, reset_engine
from contract_intelligence.shared.persistence.orm_registry import import_all_models
from contract_intelligence.shared.persistence.session import get_async_session


@pytest.fixture(scope="session", autouse=True)
def _override_settings() -> Any:
    get_settings.cache_clear()
    settings = get_settings()
    settings.database_url = "sqlite+aiosqlite:///:memory:"
    settings.auth_mode = "keycloak"
    settings.keycloak_server_url = "https://test-keycloak.local"
    settings.keycloak_realm = "test-realm"
    settings.keycloak_client_id = "ci-backend"
    settings.keycloak_audience = "ci-backend"
    settings.keycloak_role_map = {
        "ci_operator": "OPERATOR",
        "ci_reviewer": "REVIEWER",
        "ci_administrator": "ADMINISTRATOR",
    }
    settings.env = "test"
    settings.job_queue_enabled = False
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture(scope="function")
async def db_engine(tmp_path: Any) -> Any:
    import_all_models()
    db_path = tmp_path / "test_deletion.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    bind_engine(engine)
    yield engine
    reset_engine()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(
    db_engine: Any,
    cached_keycloak_jwks: str,
    mock_keycloak_settings: Any,
) -> AsyncGenerator[AsyncClient, None]:
    from contract_intelligence.shared.storage import reset_file_storage, set_file_storage

    set_file_storage(FakeFileStorage())
    factory = async_sessionmaker(bind=db_engine, expire_on_commit=False, class_=AsyncSession)

    async def override_get_async_session() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_async_session] = override_get_async_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    reset_file_storage()


async def _create_dossier(client: AsyncClient, token: str) -> tuple[str, str]:
    response = await client.post(
        "/api/v1/dossiers",
        files=[("contract", ("test.pdf", b"%PDF-1.4 content", "application/pdf"))],
        data={"metadata": '{"name": "To Delete", "notes": "secret note"}'},
        headers={
            "Authorization": f"Bearer {token}",
            "X-Tenant-Id": "tenant_vgr_01",
        },
    )
    assert response.status_code == 202, response.text
    data = response.json()["data"]
    return data["dossier_id"], data["job_id"]


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": "tenant_vgr_01",
    }


class TestDossierDeletion:
    @pytest.mark.asyncio
    async def test_delete_tombstones_hides_from_list_and_detail(
        self,
        client: AsyncClient,
        make_keycloak_token: Any,
        db_engine: Any,
    ) -> None:
        token = make_keycloak_token(role="OPERATOR", user_id="usr_op_delete")
        dossier_id, job_id = await _create_dossier(client, token)

        delete_resp = await client.delete(
            f"/api/v1/dossiers/{dossier_id}",
            headers=_headers(token),
        )
        assert delete_resp.status_code == 202, delete_resp.text
        body = delete_resp.json()["data"]
        assert body["dossier_id"] == dossier_id
        assert body["purge_status"] == "pending"
        assert body["deleted_at"]

        await asyncio.sleep(0.3)

        list_resp = await client.get("/api/v1/dossiers", headers=_headers(token))
        assert list_resp.status_code == 200
        ids = [d["id"] for d in list_resp.json()["data"]]
        assert dossier_id not in ids

        get_resp = await client.get(
            f"/api/v1/dossiers/{dossier_id}",
            headers=_headers(token),
        )
        assert get_resp.status_code == 404

        factory = async_sessionmaker(bind=db_engine, expire_on_commit=False, class_=AsyncSession)
        async with factory() as session:
            dossier = (
                await session.execute(select(DossierORM).where(DossierORM.id == dossier_id))
            ).scalar_one()
            assert dossier.deleted_at is not None
            assert dossier.deleted_by == "usr_op_delete"
            assert dossier.purge_status in ("pending", "running", "completed", "failed")

            assert (
                await session.execute(select(JobORM).where(JobORM.id == job_id))
            ).scalar_one() is not None

            docs = (
                (
                    await session.execute(
                        select(DocumentORM).where(DocumentORM.dossier_id == dossier_id)
                    )
                )
                .scalars()
                .all()
            )
            assert len(docs) >= 1
            if dossier.purge_status == "completed":
                assert docs[0].filename == "[purged]"
                assert docs[0].blob_uri is None
                assert dossier.name == "[deleted]"

            ledger = (
                (
                    await session.execute(
                        select(DeletionLedgerORM).where(DeletionLedgerORM.dossier_id == dossier_id)
                    )
                )
                .scalars()
                .all()
            )
            phases = {row.phase for row in ledger}
            assert "tombstone" in phases
            assert any(row.actor_user_id == "usr_op_delete" for row in ledger)

    @pytest.mark.asyncio
    async def test_delete_content_returns_404(
        self,
        client: AsyncClient,
        make_keycloak_token: Any,
    ) -> None:
        token = make_keycloak_token(role="OPERATOR")
        dossier_id, _ = await _create_dossier(client, token)

        docs_resp = await client.get(
            f"/api/v1/dossiers/{dossier_id}/documents",
            headers=_headers(token),
        )
        assert docs_resp.status_code == 200
        documents = docs_resp.json()["data"]
        assert documents
        document_id = documents[0]["id"]

        del_resp = await client.delete(
            f"/api/v1/dossiers/{dossier_id}",
            headers=_headers(token),
        )
        assert del_resp.status_code == 202

        content = await client.get(
            f"/api/v1/documents/{document_id}/content",
            headers=_headers(token),
        )
        assert content.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_idempotent(
        self,
        client: AsyncClient,
        make_keycloak_token: Any,
    ) -> None:
        token = make_keycloak_token(role="OPERATOR")
        dossier_id, _ = await _create_dossier(client, token)

        first = await client.delete(
            f"/api/v1/dossiers/{dossier_id}",
            headers=_headers(token),
        )
        second = await client.delete(
            f"/api/v1/dossiers/{dossier_id}",
            headers=_headers(token),
        )
        assert first.status_code == 202
        assert second.status_code == 202
        assert second.json()["data"]["dossier_id"] == dossier_id

    @pytest.mark.asyncio
    async def test_delete_forbidden_for_reviewer(
        self,
        client: AsyncClient,
        make_keycloak_token: Any,
    ) -> None:
        op = make_keycloak_token(role="OPERATOR")
        dossier_id, _ = await _create_dossier(client, op)

        reviewer = make_keycloak_token(role="REVIEWER")
        resp = await client.delete(
            f"/api/v1/dossiers/{dossier_id}",
            headers=_headers(reviewer),
        )
        assert resp.status_code == 403
