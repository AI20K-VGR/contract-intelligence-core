"""Integration tests cho /auth/me — dùng SQLite in-memory + mock Keycloak JWKS.

Sau refactor Keycloak SSO:
    - Backend CHỈ có endpoint /auth/me (pass-through từ JWT claims).
    - KHÔNG có /auth/login, /auth/refresh, /auth/logout — frontend gọi thẳng Keycloak.
    - Test tạo mock Keycloak JWKS + sign JWT với RSA private key.

Test setup:
    - Spin up SQLite in-memory qua aiosqlite
    - Bind engine singleton trong shared.persistence.session
    - Tạo schema từ Base.metadata
    - Patch JWKS cache với test RSA public key
    - Tạo valid Keycloak JWT qua helper fixture

Mỗi test:
    - Tạo AsyncClient với dependency override
    - Gọi GET /auth/me với Bearer token
    - Verify response — pass-through từ JWT claims

Chạy:
    cd backend
    uv run pytest tests/integration/test_auth_endpoints.py -v
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from contract_intelligence.config.settings import get_settings
from contract_intelligence.main import app
from contract_intelligence.shared.persistence import (
    Base,
    bind_engine,
    reset_engine,
)
from contract_intelligence.shared.persistence.session import get_async_session

# -----------------------------------------------------------------------------
# Settings override — chạy SQLite + Keycloak mode
# -----------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _override_settings() -> AsyncGenerator[None, None]:
    """Force settings sang test values (SQLite, keycloak JWT mode)."""
    get_settings.cache_clear()
    settings = get_settings()
    # SQLite in-memory cho test
    settings.database_url = "sqlite+aiosqlite:///:memory:"
    # Keycloak mode (chỉ hỗ trợ mode này)
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


# -----------------------------------------------------------------------------
# DB setup
# -----------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def db_engine() -> AsyncGenerator[Any, None]:
    """Fresh SQLite engine + schema per test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    bind_engine(engine)
    yield engine
    reset_engine()
    await engine.dispose()


# -----------------------------------------------------------------------------
# Mock Keycloak JWKS — patch JWKS cache với test public key
# -----------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def mock_keycloak_jwks(
    monkeypatch: pytest.MonkeyPatch,
    make_keycloak_token: Any,
) -> str:
    """Patch global JWKS cache với test RSA public key.

    Returns:
        kid được sử dụng — pass vào make_keycloak_token(..., kid=...).
    """
    # make_keycloak_token fixture đã patch JWKS cache qua cached_keycloak_jwks
    # nhưng ta cần đảm bảo cả hai fixture work together
    return "test-kid-1"


# -----------------------------------------------------------------------------
# Test client
# -----------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client(
    db_engine: Any,
    cached_keycloak_jwks: str,
    mock_keycloak_settings: Any,
) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient bound to FastAPI app with dependency override."""

    async def override_get_async_session() -> AsyncGenerator[AsyncSession, None]:
        factory = async_sessionmaker(bind=db_engine, expire_on_commit=False, class_=AsyncSession)
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


# =============================================================================
# Tests — GET /auth/me (Keycloak JWT pass-through)
# =============================================================================


class TestMe:
    @pytest.mark.asyncio
    async def test_me_with_valid_keycloak_token_returns_profile(
        self,
        client: AsyncClient,
        make_keycloak_token: Any,
    ) -> None:
        """Mock Keycloak JWT với claims chuẩn → /me trả về profile đúng."""
        token = make_keycloak_token(
            user_id="usr_01HZ_TEST_USER",
            tenant_id="tenant_vgr_01",
            email="reviewer@vgr.vn",
            display_name="Trần Thị Phê Duyệt",
            role="REVIEWER",
        )

        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        data = body["data"]
        assert data["id"] == "usr_01HZ_TEST_USER"
        assert data["email"] == "reviewer@vgr.vn"
        assert data["display_name"] == "Trần Thị Phê Duyệt"
        assert data["role"] == "REVIEWER"
        assert data["tenant_id"] == "tenant_vgr_01"

    @pytest.mark.asyncio
    async def test_me_without_token_returns_401(self, client: AsyncClient) -> None:
        """Không có Authorization header → 401."""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401
        assert "detail" in response.json() or "error" in response.json()

    @pytest.mark.asyncio
    async def test_me_with_invalid_token_returns_401(
        self,
        client: AsyncClient,
        make_keycloak_token: Any,
        rsa_keypair: Any,
    ) -> None:
        """Token sign với key không có trong JWKS → 401."""
        # Tạo key khác (không patch vào cache)
        import jwt as _jwt
        from cryptography.hazmat.primitives import serialization as _ser
        from cryptography.hazmat.primitives.asymmetric import rsa as _rsa

        other_private = _rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = other_private.private_bytes(
            encoding=_ser.Encoding.PEM,
            format=_ser.PrivateFormat.PKCS8,
            encryption_algorithm=_ser.NoEncryption(),
        )
        bad_token = _jwt.encode(
            {
                "sub": "u1",
                "email": "x@v.vn",
                "name": "X",
                "iss": "https://test-keycloak.local/realms/test-realm",
                "aud": "ci-backend",
                "iat": 0,
                "exp": 9999999999,
                "tenant_id": "t1",
                "realm_access": {"roles": ["ci_operator"]},
            },
            pem,
            algorithm="RS256",
            headers={"kid": "unknown-kid"},
        )

        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {bad_token}"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_me_with_wrong_audience_returns_401(
        self,
        client: AsyncClient,
        make_keycloak_token: Any,
    ) -> None:
        """Token có aud claim khác với keycloak_client_id → 401."""
        token = make_keycloak_token(audience="some-other-client")
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_me_with_malformed_token_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer not.a.real.jwt"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_me_with_authorization_header_without_bearer_prefix_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert response.status_code == 401


# =============================================================================
# Tests — Endpoint nào KHÔNG còn tồn tại (regression cho refactor)
# =============================================================================


class TestRemovedEndpoints:
    """Verify các endpoint đã bị xóa đúng cách — frontend không thể gọi nhầm."""

    @pytest.mark.asyncio
    async def test_login_endpoint_returns_404(self, client: AsyncClient) -> None:
        """POST /auth/login không còn — phải trả 404 (method/endpoint không tồn tại)."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "x@v.vn", "password": "y"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_refresh_endpoint_returns_404(self, client: AsyncClient) -> None:
        """POST /auth/refresh không còn — phải trả 404."""
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "any"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_logout_endpoint_returns_404(self, client: AsyncClient) -> None:
        """POST /auth/logout không còn — frontend phải gọi thẳng Keycloak."""
        response = await client.post("/api/v1/auth/logout")
        assert response.status_code == 404
