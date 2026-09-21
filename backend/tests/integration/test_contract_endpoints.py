"""Integration tests for Phase 1 Contract endpoints — FastAPI + SQLite in-memory.

Tests use httpx.AsyncClient with dependency overrides (no Docker required).
Covers the endpoints from openapi.yaml:

    POST /dossiers            — multipart upload (aligned with spec)
    GET  /dossiers            — list with pagination
    GET  /dossiers/{id}      — detail
    PATCH /dossiers/{id}     — update metadata
    GET  /dossiers/{id}/documents
    GET  /documents/{id}
    GET  /documents/{id}/content

Chạy:
    cd backend
    uv run pytest tests/integration/test_contract_endpoints.py -v
"""

from __future__ import annotations

import json as _json
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tests.unit.conftest_contract import FakeFileStorage

from contract_intelligence.config.settings import get_settings
from contract_intelligence.main import app
from contract_intelligence.shared.persistence import Base, bind_engine, reset_engine
from contract_intelligence.shared.persistence.session import get_async_session

# ---------------------------------------------------------------------------
# Settings override — SQLite in-memory + Keycloak mode
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _override_settings() -> Any:
    """Force settings to test values (SQLite + Keycloak JWT mode)."""
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
    yield
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# DB setup — use tempfile SQLite so all sessions share the same DB
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def db_engine(tmp_path: Any) -> Any:
    """Fresh SQLite file-based engine + schema per test.

    Using a file (not :memory:) ensures all async sessions share the same DB
    without SQLite shared-cache mode issues.
    """
    db_path = tmp_path / "test_contract.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    bind_engine(engine)
    yield engine
    reset_engine()
    await engine.dispose()


# ---------------------------------------------------------------------------
# Test client
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client(
    db_engine: Any,
    cached_keycloak_jwks: str,
    mock_keycloak_settings: Any,
) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient bound to FastAPI app with dependency overrides.

    Uses FakeFileStorage (in-memory) to avoid async executor deadlocks from
    LocalFileStorage.run_in_executor() in pytest-asyncio context.
    """
    # Override storage singleton with in-memory fake — avoids run_in_executor hangs
    # in pytest-asyncio context (asyncio.get_event_loop() inside executor is unreliable).
    from contract_intelligence.shared.storage import set_file_storage

    fake_storage = FakeFileStorage()
    set_file_storage(fake_storage)

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

    # Override the session dependency

    app.dependency_overrides[get_async_session] = override_get_async_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    # Reset storage singleton to allow next test to re-override cleanly
    from contract_intelligence.shared.storage import reset_file_storage

    reset_file_storage()


def _auth_headers(token: str) -> dict[str, str]:
    """Standard auth headers — includes X-Tenant-Id extracted from token claims."""
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": "tenant_vgr_01",  # matches make_keycloak_token default tenant
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDossierEndpoints:
    """Phase 1: Core Document Ingestion endpoints."""

    @pytest.mark.asyncio
    async def test_create_dossier_multipart_upload_returns_202(
        self,
        client: AsyncClient,
        make_keycloak_token: Any,
    ) -> None:
        """POST /dossiers with contract PDF → 202 Accepted."""
        token = make_keycloak_token(role="OPERATOR")
        response = await client.post(
            "/api/v1/dossiers",
            files=[("contract", ("test.pdf", b"%PDF-1.4 content", "application/pdf"))],
            data={"metadata": '{"name": "Test Contract"}'},
            headers=_auth_headers(token),
        )
        assert response.status_code == 202, (
            f"Expected 202, got {response.status_code}: {response.text}"
        )
        body = response.json()
        assert "data" in body
        assert "dossier_id" in body["data"]
        assert body["data"]["dossier_id"].startswith("dos_")
        assert body["data"]["job_id"] is not None
        assert body["data"]["job_id"].startswith("job_")

    @pytest.mark.asyncio
    async def test_create_dossier_requires_auth(
        self,
        client: AsyncClient,
    ) -> None:
        """POST /dossiers without token → 401."""
        response = await client.post(
            "/api/v1/dossiers",
            files=[("contract", ("x.pdf", b"pdf", "application/pdf"))],
            data={"metadata": "{}"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_dossier_requires_operator_or_admin(
        self,
        client: AsyncClient,
        make_keycloak_token: Any,
    ) -> None:
        """POST /dossiers with REVIEWER role → 403."""
        token = make_keycloak_token(role="REVIEWER")
        response = await client.post(
            "/api/v1/dossiers",
            files=[("contract", ("x.pdf", b"pdf", "application/pdf"))],
            data={"metadata": "{}"},
            headers=_auth_headers(token),
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_create_dossier_with_annex(
        self,
        client: AsyncClient,
        make_keycloak_token: Any,
    ) -> None:
        """POST /dossiers with contract + annex → 202."""
        token = make_keycloak_token(role="OPERATOR")
        response = await client.post(
            "/api/v1/dossiers",
            files=[
                ("contract", ("contract.pdf", b"%PDF-1.4 contract", "application/pdf")),
                ("annexes", ("annex_1.pdf", b"%PDF-1.4 annex 1", "application/pdf")),
            ],
            data={"metadata": '{"name": "Multi-doc dossier"}'},
            headers=_auth_headers(token),
        )
        assert response.status_code == 202, response.text

    @pytest.mark.asyncio
    async def test_list_dossiers_requires_auth(
        self,
        client: AsyncClient,
    ) -> None:
        """GET /dossiers without token → 401."""
        response = await client.get("/api/v1/dossiers")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_dossiers_returns_empty_list(
        self,
        client: AsyncClient,
        make_keycloak_token: Any,
    ) -> None:
        """GET /dossiers with no dossiers → empty array."""
        token = make_keycloak_token(role="OPERATOR")
        response = await client.get(
            "/api/v1/dossiers",
            headers=_auth_headers(token),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["data"] == []

    @pytest.mark.asyncio
    async def test_list_dossiers_returns_created_dossiers(
        self,
        client: AsyncClient,
        make_keycloak_token: Any,
    ) -> None:
        """POST + GET → dossier appears in list."""
        token = make_keycloak_token(role="OPERATOR")

        for name in ["Dossier A", "Dossier B"]:
            r = await client.post(
                "/api/v1/dossiers",
                files=[("contract", ("x.pdf", b"pdf", "application/pdf"))],
                data={"metadata": _json.dumps({"name": name})},
                headers=_auth_headers(token),
            )
            assert r.status_code == 202, r.text

        response = await client.get(
            "/api/v1/dossiers",
            headers=_auth_headers(token),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert len(body["data"]) == 2

    @pytest.mark.asyncio
    async def test_get_dossier_detail(
        self,
        client: AsyncClient,
        make_keycloak_token: Any,
    ) -> None:
        """GET /dossiers/{id} → detail with documents."""
        token = make_keycloak_token(role="OPERATOR")

        r = await client.post(
            "/api/v1/dossiers",
            files=[("contract", ("main.pdf", b"%PDF-1.4", "application/pdf"))],
            data={"metadata": '{"name": "Detail Test"}'},
            headers=_auth_headers(token),
        )
        dossier_id = r.json()["data"]["dossier_id"]

        response = await client.get(
            f"/api/v1/dossiers/{dossier_id}",
            headers=_auth_headers(token),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["data"]["id"] == dossier_id
        assert body["data"]["name"] == "Detail Test"
        assert "documents" in body["data"]

    @pytest.mark.asyncio
    async def test_get_dossier_not_found_returns_404(
        self,
        client: AsyncClient,
        make_keycloak_token: Any,
    ) -> None:
        """GET /dossiers/{missing_id} → 404."""
        token = make_keycloak_token(role="OPERATOR")
        response = await client.get(
            "/api/v1/dossiers/dos_MISSING",
            headers=_auth_headers(token),
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_patch_dossier_updates_name(
        self,
        client: AsyncClient,
        make_keycloak_token: Any,
    ) -> None:
        """PATCH /dossiers/{id} → name updated."""
        token = make_keycloak_token(role="OPERATOR")

        r = await client.post(
            "/api/v1/dossiers",
            files=[("contract", ("x.pdf", b"pdf", "application/pdf"))],
            data={"metadata": '{"name": "Old Name"}'},
            headers=_auth_headers(token),
        )
        dossier_id = r.json()["data"]["dossier_id"]

        response = await client.patch(
            f"/api/v1/dossiers/{dossier_id}",
            json={"name": "New Name"},
            headers=_auth_headers(token),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["data"]["name"] == "New Name"

    @pytest.mark.asyncio
    async def test_patch_dossier_requires_write_role(
        self,
        client: AsyncClient,
        make_keycloak_token: Any,
    ) -> None:
        """PATCH with REVIEWER role → 403 (hierarchy restricts to OPERATOR+)."""
        token = make_keycloak_token(role="REVIEWER")
        token_op = make_keycloak_token(role="OPERATOR")

        r = await client.post(
            "/api/v1/dossiers",
            files=[("contract", ("x.pdf", b"pdf", "application/pdf"))],
            data={"metadata": "{}"},
            headers=_auth_headers(token_op),
        )
        dossier_id = r.json()["data"]["dossier_id"]

        response = await client.patch(
            f"/api/v1/dossiers/{dossier_id}",
            json={"name": "X"},
            headers=_auth_headers(token),
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_list_dossier_documents(
        self,
        client: AsyncClient,
        make_keycloak_token: Any,
    ) -> None:
        """GET /dossiers/{id}/documents → document list."""
        token = make_keycloak_token(role="OPERATOR")

        r = await client.post(
            "/api/v1/dossiers",
            files=[
                ("contract", ("c.pdf", b"%PDF-1.4 contract", "application/pdf")),
                ("annexes", ("a.pdf", b"%PDF-1.4 annex", "application/pdf")),
            ],
            data={"metadata": '{"name": "Doc List"}'},
            headers=_auth_headers(token),
        )
        dossier_id = r.json()["data"]["dossier_id"]

        response = await client.get(
            f"/api/v1/dossiers/{dossier_id}/documents",
            headers=_auth_headers(token),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert len(body["data"]) == 2
        roles = {d["role"] for d in body["data"]}
        assert "CONTRACT" in roles
        assert "ANNEX" in roles

    @pytest.mark.asyncio
    async def test_get_document_detail(
        self,
        client: AsyncClient,
        make_keycloak_token: Any,
    ) -> None:
        """GET /documents/{id} → document detail."""
        token = make_keycloak_token(role="OPERATOR")

        r = await client.post(
            "/api/v1/dossiers",
            files=[("contract", ("doc.pdf", b"%PDF-1.4 content", "application/pdf"))],
            data={"metadata": '{"name": "Doc Test"}'},
            headers=_auth_headers(token),
        )
        dossier_id = r.json()["data"]["dossier_id"]

        docs_r = await client.get(
            f"/api/v1/dossiers/{dossier_id}/documents",
            headers=_auth_headers(token),
        )
        doc_id = docs_r.json()["data"][0]["id"]

        response = await client.get(
            f"/api/v1/documents/{doc_id}",
            headers=_auth_headers(token),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["data"]["id"] == doc_id
        assert "file_size_bytes" in body["data"]
        assert body["data"]["file_size_bytes"] > 0
        assert "storage_path" in body["data"]
        assert "ocr_status" in body["data"]

    @pytest.mark.asyncio
    async def test_stream_document_content(
        self,
        client: AsyncClient,
        make_keycloak_token: Any,
    ) -> None:
        """GET /documents/{id}/content → binary PDF stream."""
        token = make_keycloak_token(role="OPERATOR")
        content = b"%PDF-1.4 full content here"

        r = await client.post(
            "/api/v1/dossiers",
            files=[("contract", ("stream.pdf", content, "application/pdf"))],
            data={"metadata": '{"name": "Stream Test"}'},
            headers=_auth_headers(token),
        )
        dossier_id = r.json()["data"]["dossier_id"]

        docs_r = await client.get(
            f"/api/v1/dossiers/{dossier_id}/documents",
            headers=_auth_headers(token),
        )
        doc_id = docs_r.json()["data"][0]["id"]

        response = await client.get(
            f"/api/v1/documents/{doc_id}/content",
            headers=_auth_headers(token),
        )
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/pdf"
        assert response.content == content

    @pytest.mark.asyncio
    async def test_read_ops_accessible_by_reviewer(
        self,
        client: AsyncClient,
        make_keycloak_token: Any,
    ) -> None:
        """GET endpoints are accessible by REVIEWER (hierarchy allows)."""
        token_op = make_keycloak_token(role="OPERATOR")
        token_reviewer = make_keycloak_token(role="REVIEWER")

        # Create dossier as OPERATOR
        r = await client.post(
            "/api/v1/dossiers",
            files=[("contract", ("x.pdf", b"pdf", "application/pdf"))],
            data={"metadata": "{}"},
            headers=_auth_headers(token_op),
        )
        dossier_id = r.json()["data"]["dossier_id"]

        # All GET endpoints should work as REVIEWER
        for path in [
            "/api/v1/dossiers",
            f"/api/v1/dossiers/{dossier_id}",
            f"/api/v1/dossiers/{dossier_id}/documents",
        ]:
            resp = await client.get(path, headers=_auth_headers(token_reviewer))
            assert resp.status_code == 200, f"GET {path} failed as REVIEWER: {resp.status_code}"
