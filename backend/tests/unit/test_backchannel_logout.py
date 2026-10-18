"""Back-channel logout: a session Keycloak ended stops working at once.

Keycloak POSTs a signed logout token (``sid``) to /api/v1/auth/backchannel-logout;
the backend stores the ``sid`` and refuses every access token of that session
instead of letting it run until ``exp`` (15 minutes).
"""

from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from contract_intelligence.config.settings import Settings
from contract_intelligence.main import app
from contract_intelligence.shared.auth.dependencies import get_current_user
from contract_intelligence.shared.auth.exceptions import (
    AuthenticationError,
    SessionRevokedError,
    client_auth_message,
)
from contract_intelligence.shared.auth.jwt_service import JWTService
from contract_intelligence.shared.auth.revoked_sessions import RevokedSessions, revoked_sessions
from contract_intelligence.shared.auth.schemas import AuthenticatedUser
from contract_intelligence.shared.persistence import get_async_session
from contract_intelligence.shared.persistence.base import Base
from contract_intelligence.shared.session_revocation import (
    RevokedSessionORM,
    load_revoked_sessions,
    revoke_session,
)

EVENT = "http://schemas.openid.net/event/backchannel-logout"
FRONTEND = "contract-intel-frontend"
URL = "/api/v1/auth/backchannel-logout"


@pytest.fixture(autouse=True)
def _empty_registry() -> Any:
    revoked_sessions.clear()
    yield
    revoked_sessions.clear()


@pytest.fixture
def sign(
    rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey],
    cached_keycloak_jwks: str,
    mock_keycloak_settings: Settings,
) -> Any:
    pem = rsa_keypair[0].private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )

    def _sign(claims: dict[str, Any], kid: str = cached_keycloak_jwks) -> str:
        return jwt.encode(claims, pem, algorithm="RS256", headers={"kid": kid})

    return _sign


@pytest.fixture
def logout_token(sign: Any, mock_keycloak_settings: Settings) -> Any:
    settings = mock_keycloak_settings
    issuer = f"{settings.keycloak_server_url}/realms/{settings.keycloak_realm}"

    def _make(**overrides: Any) -> str:
        now = int(time.time())
        claims: dict[str, Any] = {
            "iss": issuer,
            "aud": FRONTEND,
            "iat": now,
            "exp": now + 120,
            "jti": "lt-1",
            "typ": "Logout",
            "sub": "usr_1",
            "sid": "sid-abc-123",
            "events": {EVENT: {}},
        }
        for key, value in overrides.items():
            if value is None:
                claims.pop(key, None)
            else:
                claims[key] = value
        return sign(claims)

    return _make


@pytest_asyncio.fixture
async def factory() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[RevokedSessionORM.__table__])
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(factory: async_sessionmaker[AsyncSession]) -> AsyncGenerator[AsyncClient, None]:
    async def _session() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_async_session] = _session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()


def _protected_app() -> FastAPI:
    probe = FastAPI()

    @probe.get("/whoami")
    async def whoami(user: AuthenticatedUser = Depends(get_current_user)) -> dict[str, Any]:
        return {"sub": user.user_id, "sid": user.session_id}

    return probe


# --- logout token ------------------------------------------------------------


def test_valid_logout_token_gives_sid_and_sub(logout_token: Any) -> None:
    claims = JWTService().decode_logout_token(logout_token())

    assert (claims.sid, claims.sub) == ("sid-abc-123", "usr_1")


@pytest.mark.parametrize(
    ("override", "why"),
    [
        ({"aud": "contract-intel-backend"}, "audience is the backend, not the frontend"),
        ({"iss": "https://evil.example/realms/test-realm"}, "foreign issuer"),
        ({"events": None}, "no logout event"),
        ({"events": {"other": {}}}, "wrong event"),
        ({"nonce": "n"}, "an ID token, not a logout token"),
        ({"sid": None}, "no sid"),
        ({"sid": ""}, "empty sid"),
        ({"iat": None}, "no iat"),
        ({"exp": int(time.time()) - 10}, "expired"),
    ],
)
def test_logout_token_is_rejected(logout_token: Any, override: dict[str, Any], why: str) -> None:
    with pytest.raises(AuthenticationError):
        JWTService().decode_logout_token(logout_token(**override))


def test_logout_token_signed_by_another_key_is_rejected(
    mock_keycloak_settings: Settings, cached_keycloak_jwks: str
) -> None:
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = jwt.encode(
        {
            "iss": "https://test-keycloak.local/realms/test-realm",
            "aud": FRONTEND,
            "iat": int(time.time()),
            "sid": "s",
            "events": {EVENT: {}},
        },
        other,
        algorithm="RS256",
        headers={"kid": cached_keycloak_jwks},
    )

    with pytest.raises(AuthenticationError):
        JWTService().decode_logout_token(token)


# --- access tokens of an ended session ---------------------------------------


def test_access_token_of_a_revoked_session_is_refused(make_keycloak_token: Any) -> None:
    token = make_keycloak_token(extra_claims={"sid": "sid-abc-123"})
    assert JWTService().decode_and_validate_access(token).session_id == "sid-abc-123"

    revoked_sessions.add("sid-abc-123", time.time() + 60)

    with pytest.raises(SessionRevokedError):
        JWTService().decode_and_validate_access(token)


def test_other_sessions_and_tokens_without_sid_still_work(make_keycloak_token: Any) -> None:
    revoked_sessions.add("sid-abc-123", time.time() + 60)

    other = make_keycloak_token(extra_claims={"sid": "sid-other"})
    no_sid = make_keycloak_token()

    assert JWTService().decode_and_validate_access(other).session_id == "sid-other"
    assert JWTService().decode_and_validate_access(no_sid).session_id is None


def test_revocation_lapses_after_its_ttl(make_keycloak_token: Any) -> None:
    revoked_sessions.add("sid-abc-123", time.time() - 1)

    token = make_keycloak_token(extra_claims={"sid": "sid-abc-123"})

    assert JWTService().decode_and_validate_access(token).user_id == "usr_01HZ_TEST"


def test_client_is_told_the_session_ended() -> None:
    assert client_auth_message(SessionRevokedError()) == "Session has ended"
    assert client_auth_message(AuthenticationError("kid mismatch")) == "Invalid token"


async def test_api_answers_401_once_the_session_ended(make_keycloak_token: Any) -> None:
    token = make_keycloak_token(extra_claims={"sid": "sid-abc-123"})
    headers = {"Authorization": f"Bearer {token}"}
    async with AsyncClient(
        transport=ASGITransport(app=_protected_app()), base_url="http://test"
    ) as http:
        before = await http.get("/whoami", headers=headers)
        revoked_sessions.add("sid-abc-123", time.time() + 60)
        after = await http.get("/whoami", headers=headers)

    assert before.status_code == 200
    assert after.status_code == 401
    assert after.json()["detail"] == "Session has ended"


# --- endpoint ------------------------------------------------------------------


async def test_endpoint_records_the_session_and_refuses_its_tokens(
    client: AsyncClient,
    logout_token: Any,
    make_keycloak_token: Any,
    factory: async_sessionmaker[AsyncSession],
) -> None:
    response = await client.post(URL, data={"logout_token": logout_token()})

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert revoked_sessions.is_revoked("sid-abc-123")
    async with factory() as session:
        row = await session.get(RevokedSessionORM, "sid-abc-123")
    assert row is not None and row.sub == "usr_1"

    access = make_keycloak_token(extra_claims={"sid": "sid-abc-123"})
    with pytest.raises(SessionRevokedError):
        JWTService().decode_and_validate_access(access)


async def test_endpoint_is_idempotent(client: AsyncClient, logout_token: Any, factory: Any) -> None:
    token = logout_token()

    first = await client.post(URL, data={"logout_token": token})
    second = await client.post(URL, data={"logout_token": token})

    assert (first.status_code, second.status_code) == (200, 200)
    async with factory() as session:
        rows = (await session.execute(select(RevokedSessionORM))).scalars().all()
    assert [r.sid for r in rows] == ["sid-abc-123"]


async def test_endpoint_rejects_an_invalid_token_with_400(
    client: AsyncClient, logout_token: Any, factory: Any
) -> None:
    response = await client.post(URL, data={"logout_token": logout_token(aud="someone-else")})

    assert response.status_code == 400
    assert response.json() == {
        "error": "invalid_request",
        "error_description": "invalid logout token",
    }
    assert len(revoked_sessions) == 0
    async with factory() as session:
        assert (await session.execute(select(RevokedSessionORM))).first() is None


async def test_endpoint_requires_the_token(client: AsyncClient) -> None:
    assert (await client.post(URL, data={})).status_code == 422


def test_endpoint_is_not_in_the_public_api_schema() -> None:
    assert URL not in app.openapi()["paths"]


# --- persistence -----------------------------------------------------------------


async def test_startup_load_restores_live_revocations_and_drops_expired(factory: Any) -> None:
    now = datetime.now(UTC)
    async with factory() as session:
        session.add_all(
            [
                RevokedSessionORM(
                    sid="live", sub="u", revoked_at=now, expires_at=now + timedelta(minutes=30)
                ),
                RevokedSessionORM(
                    sid="old", sub="u", revoked_at=now, expires_at=now - timedelta(minutes=1)
                ),
            ]
        )
        await session.commit()

    async with factory() as session:
        loaded = await load_revoked_sessions(session)
        remaining = (await session.execute(select(RevokedSessionORM.sid))).scalars().all()

    assert loaded == 1
    assert revoked_sessions.is_revoked("live")
    assert not revoked_sessions.is_revoked("old")
    assert remaining == ["live"]


async def test_revoke_keeps_the_session_refused_for_the_configured_ttl(factory: Any) -> None:
    async with factory() as session:
        expires_at = await revoke_session(session, sid="s1", sub=None)

    remaining = expires_at - datetime.now(UTC)
    assert timedelta(minutes=59) < remaining <= timedelta(hours=1)
    assert revoked_sessions.is_revoked("s1")


# --- registry ----------------------------------------------------------------------


def test_registry_drops_expired_entries_and_keeps_the_later_deadline() -> None:
    registry = RevokedSessions()
    now = time.time()
    registry.add("a", now + 100)
    registry.add("a", now + 10)
    registry.add("gone", now - 1)
    registry.add("b", now + 5)

    assert registry.is_revoked("a") and registry.is_revoked("b")
    assert not registry.is_revoked("gone") and not registry.is_revoked(None)
    assert len(registry) == 2

    registry.replace({"c": now + 5, "d": now - 5})
    assert registry.is_revoked("c") and not registry.is_revoked("a") and len(registry) == 1


# --- disabling a user ends their sessions ---------------------------------------


class _AdminForDisable:
    def __init__(self, *, logout_error: Exception | None = None) -> None:
        self.user = {"id": "u-1", "email": "rita@lexis.vn", "enabled": True}
        self.calls: list[str] = []
        self._logout_error = logout_error

    def get_user(self, user_id: str) -> dict[str, Any]:
        return self.user

    def get_realm_roles_of_user(self, user_id: str) -> list[dict[str, Any]]:
        return [{"name": "REVIEWER"}]

    def get_events(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        return []

    def disable_user(self, user_id: str) -> None:
        self.calls.append("disable")
        self.user["enabled"] = False

    def enable_user(self, user_id: str) -> None:
        self.calls.append("enable")
        self.user["enabled"] = True

    def user_logout(self, user_id: str) -> dict[str, Any]:
        self.calls.append("logout")
        if self._logout_error is not None:
            raise self._logout_error
        return {}


def test_disabling_a_user_ends_their_sessions(monkeypatch: pytest.MonkeyPatch) -> None:
    from contract_intelligence.infrastructure import keycloak_admin

    admin = _AdminForDisable()
    monkeypatch.setattr(keycloak_admin, "_build_keycloak_admin", lambda: admin)

    keycloak_admin._set_enabled_sync(user_id="u-1", enabled=False)

    assert admin.calls == ["disable", "logout"]


def test_enabling_a_user_ends_no_session(monkeypatch: pytest.MonkeyPatch) -> None:
    from contract_intelligence.infrastructure import keycloak_admin

    admin = _AdminForDisable()
    monkeypatch.setattr(keycloak_admin, "_build_keycloak_admin", lambda: admin)

    keycloak_admin._set_enabled_sync(user_id="u-1", enabled=True)

    assert admin.calls == ["enable"]


def test_disable_still_succeeds_when_ending_sessions_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from keycloak.exceptions import KeycloakPostError

    from contract_intelligence.infrastructure import keycloak_admin

    admin = _AdminForDisable(
        logout_error=KeycloakPostError(error_message="boom", response_code=500)
    )
    monkeypatch.setattr(keycloak_admin, "_build_keycloak_admin", lambda: admin)

    dto = keycloak_admin._set_enabled_sync(user_id="u-1", enabled=False)

    assert admin.calls == ["disable", "logout"]
    assert dto.status == "disabled"
