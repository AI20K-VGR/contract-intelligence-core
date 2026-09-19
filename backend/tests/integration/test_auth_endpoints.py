"""Integration tests cho /auth/* endpoints — dùng SQLite in-memory.

Test setup:
    - Spin up SQLite in-memory qua aiosqlite
    - Bind engine singleton trong shared.persistence.session
    - Tạo schema từ Base.metadata (không cần alembic)
    - Seed 3 dev users (admin/reviewer/operator) với Argon2 hash
    - Override get_async_session dependency để dùng test session

Mỗi test:
    - Tạo AsyncClient với dependency override
    - Gọi POST /auth/login → nhận JWT tokens
    - Gọi các endpoint còn lại với Bearer token
    - Verify response

Chạy:
    cd backend
    uv run pytest tests/integration/ -v
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
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
from contract_intelligence.identity.domain.entities.app_user import AppUser, UserRole
from contract_intelligence.identity.infrastructure.persistence.user_repository_impl import (
    UserRepositoryImpl,
)
from contract_intelligence.identity.infrastructure.security.password_hasher import (
    Argon2PasswordHasher,
)
from contract_intelligence.main import app
from contract_intelligence.shared.persistence import (
    Base,
    bind_engine,
    reset_engine,
)
from contract_intelligence.shared.persistence.session import get_async_session

# -----------------------------------------------------------------------------
# Force test settings — phải set TRƯỚC khi import app để settings cached
# -----------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _override_settings() -> Generator[None, None, None]:
    """Force settings sang test values (SQLite, local JWT mode)."""
    get_settings.cache_clear()
    settings = get_settings()
    # Override to SQLite in-memory + local JWT mode
    settings.database_url = "sqlite+aiosqlite:///:memory:"
    settings.auth_mode = "local"
    settings.jwt_secret_key = "integration-test-secret-key-32chars!!"
    settings.jwt_algorithm = "HS256"
    settings.env = "test"
    yield
    get_settings.cache_clear()


# -----------------------------------------------------------------------------
# DB setup — create schema once per session
# -----------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def db_engine() -> AsyncGenerator[Any, None]:
    """Fresh SQLite engine + schema per test (function-scoped cho isolation)."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    # Create all tables from Base.metadata
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Bind singleton for get_async_session dependency
    bind_engine(engine)

    yield engine

    # Cleanup
    reset_engine()
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine: Any) -> AsyncGenerator[AsyncSession, None]:
    """AsyncSession bound to test engine."""
    factory = async_sessionmaker(bind=db_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def seeded_users(db_session: AsyncSession) -> AsyncGenerator[None, None]:
    """Seed 3 dev users với Argon2 hash trước mỗi test."""
    hasher = Argon2PasswordHasher()
    repo = UserRepositoryImpl(db_session)

    users = [
        AppUser(
            id="usr_admin",
            tenant_id="tenant_vgr_01",
            email="admin@vgr.vn",
            display_name="Admin",
            role=UserRole.ADMINISTRATOR,
            password_hash=hasher.hash("Admin@123"),
            is_active=True,
            token_version=0,
        ),
        AppUser(
            id="usr_reviewer",
            tenant_id="tenant_vgr_01",
            email="reviewer@vgr.vn",
            display_name="Reviewer",
            role=UserRole.REVIEWER,
            password_hash=hasher.hash("Reviewer@123"),
            is_active=True,
            token_version=0,
        ),
        AppUser(
            id="usr_operator",
            tenant_id="tenant_vgr_01",
            email="operator@vgr.vn",
            display_name="Operator",
            role=UserRole.OPERATOR,
            password_hash=hasher.hash("Operator@123"),
            is_active=False,  # Test deactivation
            token_version=0,
        ),
    ]

    for user in users:
        await repo.save(user)
    await db_session.commit()


# -----------------------------------------------------------------------------
# Test client
# -----------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client(db_engine: Any, seeded_users: None) -> AsyncGenerator[AsyncClient, None]:
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
# Tests — POST /auth/login
# =============================================================================


class TestLogin:
    @pytest.mark.asyncio
    async def test_login_success_returns_tokens(self, client: AsyncClient) -> None:
        """Login với credentials đúng → 201 + access/refresh token + profile."""
        response = await client.post(
            "/api/v1/auth/login",
            headers={"X-Tenant-Id": "tenant_vgr_01"},
            json={"email": "admin@vgr.vn", "password": "Admin@123"},
        )
        assert response.status_code == 201
        body = response.json()

        # Envelope shape
        assert "data" in body
        assert "meta" in body

        data = body["data"]
        assert data["token_type"] == "Bearer"
        assert isinstance(data["access_token"], str)
        assert len(data["access_token"]) > 20
        assert isinstance(data["refresh_token"], str)
        assert len(data["refresh_token"]) > 20
        assert data["expires_in"] == 3600  # 60 minutes

        # User profile in response
        user = data["user"]
        assert user["id"] == "usr_admin"
        assert user["role"] == "ADMINISTRATOR"
        assert user["tenant_id"] == "tenant_vgr_01"

    @pytest.mark.asyncio
    async def test_login_wrong_password_returns_401(self, client: AsyncClient) -> None:
        """Sai password → 401."""
        response = await client.post(
            "/api/v1/auth/login",
            headers={"X-Tenant-Id": "tenant_vgr_01"},
            json={"email": "admin@vgr.vn", "password": "WrongPassword"},
        )
        assert response.status_code == 401
        body = response.json()
        # FastAPI HTTPException shape: {"detail": "..."}
        assert "detail" in body or "error" in body

    @pytest.mark.asyncio
    async def test_login_nonexistent_user_returns_401(self, client: AsyncClient) -> None:
        """Email không tồn tại → 401 (không phân biệt được với wrong-password)."""
        response = await client.post(
            "/api/v1/auth/login",
            headers={"X-Tenant-Id": "tenant_vgr_01"},
            json={"email": "ghost@vgr.vn", "password": "Anything"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_deactivated_user_returns_401(self, client: AsyncClient) -> None:
        """User bị deactivate (is_active=False) → 401, không leak thông tin."""
        response = await client.post(
            "/api/v1/auth/login",
            headers={"X-Tenant-Id": "tenant_vgr_01"},
            json={"email": "operator@vgr.vn", "password": "Operator@123"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_wrong_tenant_returns_401(self, client: AsyncClient) -> None:
        """Email + tenant_id khác nhau → 401 (email unique per tenant)."""
        response = await client.post(
            "/api/v1/auth/login",
            headers={"X-Tenant-Id": "tenant_other_99"},
            json={"email": "admin@vgr.vn", "password": "Admin@123"},
        )
        assert response.status_code == 401


# =============================================================================
# Tests — GET /auth/me
# =============================================================================


class TestMe:
    @pytest.mark.asyncio
    async def test_me_with_valid_token_returns_profile(self, client: AsyncClient) -> None:
        # Login trước
        login_response = await client.post(
            "/api/v1/auth/login",
            headers={"X-Tenant-Id": "tenant_vgr_01"},
            json={"email": "admin@vgr.vn", "password": "Admin@123"},
        )
        access_token = login_response.json()["data"]["access_token"]

        # Gọi /me
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["id"] == "usr_admin"
        assert body["data"]["role"] == "ADMINISTRATOR"
        assert body["data"]["email"] == "admin@vgr.vn"

    @pytest.mark.asyncio
    async def test_me_without_token_returns_401(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_me_with_invalid_token_returns_401(self, client: AsyncClient) -> None:
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert response.status_code == 401


# =============================================================================
# Tests — POST /auth/refresh
# =============================================================================


class TestRefresh:
    @pytest.mark.asyncio
    async def test_refresh_with_valid_token_returns_new_pair(self, client: AsyncClient) -> None:
        # Login
        login_response = await client.post(
            "/api/v1/auth/login",
            headers={"X-Tenant-Id": "tenant_vgr_01"},
            json={"email": "admin@vgr.vn", "password": "Admin@123"},
        )
        refresh_token = login_response.json()["data"]["refresh_token"]
        original_access = login_response.json()["data"]["access_token"]

        # Sleep 1s để iat timestamp khác (JWT determinism với same second)
        import asyncio

        await asyncio.sleep(1.1)

        # Refresh
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        body = response.json()
        assert "access_token" in body["data"]
        assert "refresh_token" in body["data"]
        # Token mới phải khác token cũ
        assert body["data"]["access_token"] != original_access
        # Refresh token có token_version nên LUÔN khác (tăng mỗi lần refresh)
        assert body["data"]["refresh_token"] != refresh_token

    @pytest.mark.asyncio
    async def test_old_refresh_token_rejected_after_rotation(self, client: AsyncClient) -> None:
        """Sau refresh, dùng refresh_token CŨ → 401 (token_version revoked)."""
        # Login
        login_response = await client.post(
            "/api/v1/auth/login",
            headers={"X-Tenant-Id": "tenant_vgr_01"},
            json={"email": "admin@vgr.vn", "password": "Admin@123"},
        )
        old_refresh = login_response.json()["data"]["refresh_token"]

        # Refresh lần 1 — OK
        await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": old_refresh},
        )

        # Refresh lần 2 với CÙNG refresh_token cũ → 401
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": old_refresh},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_with_invalid_token_returns_401(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid.token.here"},
        )
        assert response.status_code == 401


# =============================================================================
# Tests — POST /auth/logout
# =============================================================================


class TestLogout:
    @pytest.mark.asyncio
    async def test_logout_revokes_session(self, client: AsyncClient) -> None:
        """Logout → refresh token cũ bị reject ở lần refresh tiếp theo."""
        # Login
        login_response = await client.post(
            "/api/v1/auth/login",
            headers={"X-Tenant-Id": "tenant_vgr_01"},
            json={"email": "admin@vgr.vn", "password": "Admin@123"},
        )
        access_token = login_response.json()["data"]["access_token"]
        refresh_token = login_response.json()["data"]["refresh_token"]

        # Logout
        logout_response = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert logout_response.status_code == 200
        assert logout_response.json()["data"]["message"] == "Logged out successfully"

        # Refresh sau logout → 401 (token_version đã tăng)
        refresh_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh_response.status_code == 401

    @pytest.mark.asyncio
    async def test_logout_without_token_returns_401(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/auth/logout")
        assert response.status_code == 401
