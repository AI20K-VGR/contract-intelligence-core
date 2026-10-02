"""/admin/monitoring session + /grafana proxy: who gets in, and what Grafana sees."""

from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator, Callable
from typing import Any
from urllib.parse import unquote

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from prometheus_client import REGISTRY

from contract_intelligence.config.settings import Settings
from contract_intelligence.main import create_app
from contract_intelligence.monitoring import grafana_proxy
from contract_intelligence.monitoring.session import (
    COOKIE_NAME,
    issue_session_token,
    verify_session_token,
)
from contract_intelligence.shared.auth.exceptions import AuthenticationError
from contract_intelligence.shared.auth.schemas import AuthenticatedUser

SECRET = "unit-test-monitoring-secret-0123456789"
SESSION_PATH = "/api/v1/admin/monitoring/session"


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "env": "test",
        "grafana_upstream_url": "http://grafana:3000",
        "monitoring_session_secret": SECRET,
        "cors_allow_origins": ["http://localhost:5173"],
    }
    values.update(overrides)
    return Settings(**values)


def _user(role: str) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=f"usr_{role.lower()}",
        tenant_id="tenant_vgr_01",
        email=f"{role.lower()}@vgr.vn",
        display_name=role,
        role=role,
    )


class _Body(httpx.AsyncByteStream):
    """A real network body: httpx pre-reads a plain bytes body, a socket it does not."""

    def __init__(self, data: bytes) -> None:
        self._data = data

    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield self._data


class _FakeGrafana:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        await request.aread()
        self.requests.append(request)
        return httpx.Response(
            200,
            headers=[
                ("Content-Type", "application/json"),
                ("Set-Cookie", "a=1"),
                ("Set-Cookie", "b=2"),
            ],
            stream=_Body(b'{"ok": true}'),
        )


@pytest.fixture
def grafana() -> _FakeGrafana:
    return _FakeGrafana()


@pytest.fixture
def monitoring_settings(monkeypatch: pytest.MonkeyPatch) -> Callable[..., Settings]:
    def _apply(**overrides: Any) -> Settings:
        settings = _settings(**overrides)
        for module in (
            "contract_intelligence.monitoring.grafana_proxy",
            "contract_intelligence.api.v1.monitoring",
        ):
            monkeypatch.setattr(f"{module}.get_settings", lambda: settings)
        return settings

    _apply()
    return _apply


@pytest_asyncio.fixture
async def client(
    monitoring_settings: Callable[..., Settings],
    grafana: _FakeGrafana,
    make_keycloak_token: Callable[..., str],
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[AsyncClient, None]:
    upstream = httpx.AsyncClient(transport=httpx.MockTransport(grafana))
    monkeypatch.setattr(grafana_proxy, "_client", upstream)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://api.test") as ac:
        yield ac
    await upstream.aclose()


async def _raw_asgi_get(app: Any, raw_path: bytes, token: str) -> int:
    """GET with an unnormalized path, as uvicorn passes it on (curl --path-as-is)."""
    sent: dict[str, int] = {}

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        if message["type"] == "http.response.start":
            sent["status"] = message["status"]

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": unquote(raw_path.decode("latin-1")),
        "raw_path": raw_path,
        "query_string": b"",
        "root_path": "",
        "headers": [(b"host", b"api.test"), (b"authorization", f"Bearer {token}".encode())],
        "client": ("203.0.113.5", 40000),
        "server": ("api.test", 80),
    }
    await app(scope, receive, send)
    return sent["status"]


def _bearer(make_keycloak_token: Callable[..., str], role: str) -> dict[str, str]:
    token = make_keycloak_token(role=role, user_id=f"usr_{role.lower()}")
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Session token
# ---------------------------------------------------------------------------


class TestSessionToken:
    def test_round_trip(self) -> None:
        token = issue_session_token(_user("ADMINISTRATOR"), secret=SECRET, ttl_seconds=60)
        session = verify_session_token(token, secret=SECRET)
        assert session.user_id == "usr_administrator"
        assert session.role == "ADMINISTRATOR"

    def test_other_secret_is_rejected(self) -> None:
        token = issue_session_token(
            _user("ADMINISTRATOR"), secret="attacker-secret-of-at-least-32-bytes!", ttl_seconds=60
        )
        with pytest.raises(AuthenticationError):
            verify_session_token(token, secret=SECRET)

    def test_expired_is_rejected(self) -> None:
        token = issue_session_token(_user("ADMINISTRATOR"), secret=SECRET, ttl_seconds=-1)
        with pytest.raises(AuthenticationError, match="expired"):
            verify_session_token(token, secret=SECRET)


# ---------------------------------------------------------------------------
# POST /api/v1/admin/monitoring/session
# ---------------------------------------------------------------------------


class TestOpenSession:
    async def test_unauthenticated_is_401(self, client: AsyncClient) -> None:
        resp = await client.post(SESSION_PATH)
        assert resp.status_code == 401

    @pytest.mark.parametrize("role", ["OPERATOR", "REVIEWER"])
    async def test_non_admin_is_403(
        self, client: AsyncClient, make_keycloak_token: Callable[..., str], role: str
    ) -> None:
        resp = await client.post(SESSION_PATH, headers=_bearer(make_keycloak_token, role))
        assert resp.status_code == 403
        assert "set-cookie" not in resp.headers

    async def test_admin_gets_http_only_cookie_scoped_to_grafana(
        self, client: AsyncClient, make_keycloak_token: Callable[..., str]
    ) -> None:
        resp = await client.post(
            SESSION_PATH, headers=_bearer(make_keycloak_token, "ADMINISTRATOR")
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data == {"dashboard_path": "/grafana/d/ci-overview?orgId=1&kiosk", "expires_in": 300}
        cookie = resp.headers["set-cookie"]
        assert cookie.startswith(f"{COOKIE_NAME}=")
        for attribute in ("HttpOnly", "Path=/grafana", "SameSite=none", "Secure", "Partitioned"):
            assert attribute in cookie
        assert resp.headers["cache-control"] == "no-store"

    async def test_lax_cookie_is_not_partitioned(
        self,
        client: AsyncClient,
        make_keycloak_token: Callable[..., str],
        monitoring_settings: Callable[..., Settings],
    ) -> None:
        monitoring_settings(monitoring_cookie_samesite="lax", monitoring_cookie_secure=False)
        resp = await client.post(
            SESSION_PATH, headers=_bearer(make_keycloak_token, "ADMINISTRATOR")
        )
        cookie = resp.headers["set-cookie"]
        assert "SameSite=lax" in cookie
        assert "Partitioned" not in cookie
        assert "Secure" not in cookie

    async def test_not_configured_is_503(
        self,
        client: AsyncClient,
        make_keycloak_token: Callable[..., str],
        monitoring_settings: Callable[..., Settings],
    ) -> None:
        monitoring_settings(grafana_upstream_url=None)
        resp = await client.post(
            SESSION_PATH, headers=_bearer(make_keycloak_token, "ADMINISTRATOR")
        )
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# /grafana/* proxy
# ---------------------------------------------------------------------------


class TestGrafanaAccess:
    async def test_unauthenticated_is_401(self, client: AsyncClient, grafana: _FakeGrafana) -> None:
        resp = await client.get("/grafana/")
        assert resp.status_code == 401
        assert grafana.requests == []

    async def test_forged_auth_proxy_header_alone_is_401(
        self, client: AsyncClient, grafana: _FakeGrafana
    ) -> None:
        resp = await client.get("/grafana/", headers={"X-WEBAUTH-USER": "admin"})
        assert resp.status_code == 401
        assert grafana.requests == []

    @pytest.mark.parametrize("role", ["OPERATOR", "REVIEWER"])
    async def test_non_admin_bearer_is_403(
        self,
        client: AsyncClient,
        grafana: _FakeGrafana,
        make_keycloak_token: Callable[..., str],
        role: str,
    ) -> None:
        resp = await client.get("/grafana/", headers=_bearer(make_keycloak_token, role))
        assert resp.status_code == 403
        assert grafana.requests == []

    async def test_non_admin_session_cookie_is_403(
        self, client: AsyncClient, grafana: _FakeGrafana
    ) -> None:
        token = issue_session_token(_user("OPERATOR"), secret=SECRET, ttl_seconds=60)
        client.cookies.set(COOKIE_NAME, token)
        resp = await client.get("/grafana/")
        assert resp.status_code == 403
        assert grafana.requests == []

    async def test_cookie_signed_with_another_secret_is_401(
        self, client: AsyncClient, grafana: _FakeGrafana
    ) -> None:
        token = issue_session_token(
            _user("ADMINISTRATOR"), secret="a-guessed-secret-of-at-least-32-bytes", ttl_seconds=60
        )
        client.cookies.set(COOKIE_NAME, token)
        resp = await client.get("/grafana/")
        assert resp.status_code == 401
        assert grafana.requests == []

    async def test_disabled_monitoring_is_404(
        self, client: AsyncClient, monitoring_settings: Callable[..., Settings]
    ) -> None:
        monitoring_settings(monitoring_session_secret=None)
        resp = await client.get("/grafana/")
        assert resp.status_code == 404


class TestGrafanaProxying:
    async def _admin_cookie(
        self, client: AsyncClient, make_keycloak_token: Callable[..., str]
    ) -> None:
        resp = await client.post(
            SESSION_PATH, headers=_bearer(make_keycloak_token, "ADMINISTRATOR")
        )
        token = (
            resp.cookies.get(COOKIE_NAME)
            or resp.headers["set-cookie"].split(";")[0].split("=", 1)[1]
        )
        client.cookies.set(COOKIE_NAME, token)

    async def test_admin_cookie_reaches_grafana_as_viewer(
        self,
        client: AsyncClient,
        grafana: _FakeGrafana,
        make_keycloak_token: Callable[..., str],
    ) -> None:
        await self._admin_cookie(client, make_keycloak_token)
        resp = await client.get(
            "/grafana/api/search?query=ci",
            headers={
                # Everything a client might use to pick its Grafana identity.
                "X-WEBAUTH-USER": "admin",
                "X-Webauth-Role": "Admin",
                "X-Forwarded-For": "172.30.240.10",
                "X-Real-IP": "172.30.240.10",
            },
        )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

        [sent] = grafana.requests
        assert str(sent.url) == "http://grafana:3000/grafana/api/search?query=ci"
        assert sent.headers.get_list("x-webauth-user") == [
            grafana_proxy.grafana_login("tenant_vgr_01", "usr_administrator")
        ]
        assert sent.headers.get_list("x-webauth-role") == ["Viewer"]
        for header in ("authorization", "cookie", "x-forwarded-for", "x-real-ip"):
            assert header not in sent.headers

    async def test_grafana_login_is_a_pseudonym(self) -> None:
        login = grafana_proxy.grafana_login("tenant_vgr_01", "usr_administrator")
        assert login.startswith("ci-admin-")
        assert "usr_administrator" not in login
        assert "@" not in login

    async def test_admin_bearer_reaches_grafana(
        self,
        client: AsyncClient,
        grafana: _FakeGrafana,
        make_keycloak_token: Callable[..., str],
    ) -> None:
        resp = await client.get(
            "/grafana/api/health", headers=_bearer(make_keycloak_token, "ADMINISTRATOR")
        )
        assert resp.status_code == 200
        assert "authorization" not in grafana.requests[0].headers

    async def test_response_keeps_every_set_cookie_and_limits_framing(
        self,
        client: AsyncClient,
        make_keycloak_token: Callable[..., str],
    ) -> None:
        resp = await client.get("/grafana/", headers=_bearer(make_keycloak_token, "ADMINISTRATOR"))
        assert resp.headers.get_list("set-cookie") == ["a=1", "b=2"]
        assert resp.headers["content-security-policy"] == (
            "frame-ancestors 'self' http://localhost:5173"
        )

    @pytest.mark.parametrize("method", ["PUT", "PATCH", "DELETE"])
    async def test_write_methods_never_reach_grafana(
        self,
        client: AsyncClient,
        grafana: _FakeGrafana,
        make_keycloak_token: Callable[..., str],
        method: str,
    ) -> None:
        resp = await client.request(
            method,
            "/grafana/api/datasources/uid/prometheus",
            headers=_bearer(make_keycloak_token, "ADMINISTRATOR"),
        )
        assert resp.status_code == 405
        assert grafana.requests == []

    async def test_server_admin_api_is_blocked(
        self,
        client: AsyncClient,
        grafana: _FakeGrafana,
        make_keycloak_token: Callable[..., str],
    ) -> None:
        resp = await client.post(
            "/grafana/api/admin/users",
            headers=_bearer(make_keycloak_token, "ADMINISTRATOR"),
            json={"login": "x"},
        )
        assert resp.status_code == 403
        assert grafana.requests == []

    @pytest.mark.parametrize(
        "raw_path",
        [
            "/grafana/api/%61dmin/users",
            "/grafana/api%2Fadmin/users",
            "/grafana/api/ADMIN/users",
            "/grafana/api/%2561dmin/users",
            "/grafana/api//admin/users",
        ],
    )
    async def test_admin_api_block_cannot_be_dodged_by_encoding(
        self,
        client: AsyncClient,
        grafana: _FakeGrafana,
        make_keycloak_token: Callable[..., str],
        raw_path: str,
    ) -> None:
        resp = await client.get(raw_path, headers=_bearer(make_keycloak_token, "ADMINISTRATOR"))
        assert resp.status_code in (400, 403)
        assert grafana.requests == []

    @pytest.mark.parametrize(
        "raw_path",
        [
            b"/grafana/../grafana/api/admin/users",
            b"/grafana/api/admin/../admin/users",
            b"/grafana/api/%2e%2e/api/admin/users",
        ],
    )
    async def test_dot_segments_never_reach_grafana(
        self,
        client: AsyncClient,
        grafana: _FakeGrafana,
        make_keycloak_token: Callable[..., str],
        raw_path: bytes,
    ) -> None:
        # httpx normalizes "..", so send the raw request the way uvicorn hands it over.
        token = make_keycloak_token(role="ADMINISTRATOR", user_id="usr_administrator")
        status_code = await _raw_asgi_get(create_app(), raw_path, token)
        assert status_code == 400
        assert grafana.requests == []

    async def test_forwarded_path_is_the_checked_one(
        self,
        client: AsyncClient,
        grafana: _FakeGrafana,
        make_keycloak_token: Callable[..., str],
    ) -> None:
        resp = await client.get(
            "/grafana/api/%73earch?query=a%2Fb",
            headers=_bearer(make_keycloak_token, "ADMINISTRATOR"),
        )
        assert resp.status_code == 200
        assert grafana.requests[0].url.raw_path == b"/grafana/api/search?query=a%2Fb"

    async def test_cross_origin_post_is_refused(
        self,
        client: AsyncClient,
        grafana: _FakeGrafana,
        make_keycloak_token: Callable[..., str],
    ) -> None:
        await self._admin_cookie(client, make_keycloak_token)
        resp = await client.post(
            "/grafana/api/ds/query", headers={"Origin": "https://evil.example"}, json={}
        )
        assert resp.status_code == 403
        assert grafana.requests == []

    async def test_same_origin_post_is_proxied(
        self,
        client: AsyncClient,
        grafana: _FakeGrafana,
        make_keycloak_token: Callable[..., str],
    ) -> None:
        await self._admin_cookie(client, make_keycloak_token)
        resp = await client.post(
            "/grafana/api/ds/query", headers={"Origin": "http://api.test"}, json={"q": 1}
        )
        assert resp.status_code == 200
        assert grafana.requests[0].content == b'{"q":1}'


# ---------------------------------------------------------------------------
# HTTP metrics
# ---------------------------------------------------------------------------


class TestHttpMetrics:
    async def test_labels_use_route_templates(self, client: AsyncClient) -> None:
        def count(route: str, status_class: str) -> float:
            return (
                REGISTRY.get_sample_value(
                    "ci_backend_http_requests_total",
                    {"method": "GET", "route": route, "status_class": status_class},
                )
                or 0.0
            )

        health, unmatched = count("/health", "2xx"), count("unmatched", "4xx")
        await client.get("/health")
        await client.get("/no-such-path/contract-of-acme.pdf")
        assert count("/health", "2xx") == health + 1
        assert count("unmatched", "4xx") == unmatched + 1


def test_prod_refuses_dev_monitoring_secret() -> None:
    with pytest.raises(ValueError, match="MONITORING_SESSION_SECRET"):
        Settings(
            env="prod",
            database_url="postgresql+asyncpg://ci:s3cr3t-db@db/ci",
            s3_secret_key="s3-real-secret",
            minio_secret_key="minio-real-secret",
            keycloak_admin_client_secret="kc-real-secret",
            keycloak_webhook_secret="hook-real-secret",
            ai2_service_hmac_secret="ai2-real-secret",
            grafana_upstream_url="http://grafana:3000",
            monitoring_session_secret="ci_monitoring_session_secret_dev",
        )
