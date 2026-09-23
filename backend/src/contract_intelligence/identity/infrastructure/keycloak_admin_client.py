"""Keycloak Admin REST API client — fetch user profile for webhook sync.

Layer: infrastructure (HTTP client). Wraps Keycloak's ``/admin/realms/{realm}/users``
endpoint behind a small async API.

Why this exists:
    Phase Two ``keycloak-events`` extension sends the raw Keycloak ``Event`` payload
    to our webhook, which contains ``userId`` (Keycloak UUID) but NOT the user's
    ``firstName`` / ``lastName`` / ``email`` / attributes. To upsert the local
    ``app_user`` cache we need to follow up with ``GET /admin/realms/{realm}/users/{id}``.

Auth flow:
    1. Service Account (Client Credentials Grant) → access token
       POST {keycloak_server_url}/realms/{realm}/protocol/openid-connect/token
       body: grant_type=client_credentials
       auth: Basic <client_id:client_secret>
    2. Cache token + re-use until 60s before expiry.
    3. Refresh proactively when stale.

Required Keycloak setup (xem ``keycloak/realm-export.json``):
    - Client ``contract-intel-backend`` có ``serviceAccountsEnabled: true``
    - Service account có realm-management client role ``view-users``

Errors:
    - 401/403 from Keycloak → propagate as ``KeycloakAdminAuthError`` so caller
      can distinguish infra failure from business logic.
    - 404 from Keycloak → ``KeycloakAdminUserNotFoundError`` (user vừa bị xoá).
    - Network/timeout → ``KeycloakAdminRequestError``.

Layer purity:
    Chỉ chứa HTTP + token-cache logic. KHÔNG biết về AppUser/UserRepository.
    Caller (``KeycloakUserSyncService``) chịu trách nhiệm map Keycloak
    UserRepresentation → AppUser fields.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Protocol, cast, runtime_checkable
from urllib.parse import quote

import httpx
import structlog

from contract_intelligence.config.settings import get_settings

# -----------------------------------------------------------------------------
# Protocol (Port) — application layer type-hints qua đây
# -----------------------------------------------------------------------------


@runtime_checkable
class KeycloakAdminClientPort(Protocol):
    """Port cho Keycloak Admin API — application layer (sync service) dùng."""

    async def get_user_profile(self, user_id: str) -> dict[str, Any]:
        """Fetch full user representation từ Keycloak Admin API.

        Args:
            user_id: Keycloak user UUID (``sub`` claim).

        Returns:
            UserRepresentation dict:
                {
                    "id": "...",
                    "username": "...",
                    "email": "...",
                    "firstName": "...",
                    "lastName": "...",
                    "enabled": true,
                    "attributes": {"tenant_id": ["..."], ...},
                    ...
                }

        Raises:
            KeycloakAdminUserNotFoundError: user không tồn tại.
            KeycloakAdminAuthError: token invalid / thiếu permission.
            KeycloakAdminRequestError: network / timeout / 5xx.
        """
        ...

    async def get_user_realm_roles(self, user_id: str) -> list[str]:
        """Fetch realm-level role names của user.

        Returns:
            List các role names, VD ["OPERATOR"] hoặc ["ADMINISTRATOR"].

        Raises:
            Same as ``get_user_profile``.
        """
        ...

    async def close(self) -> None:
        """Close underlying httpx client — gọi khi shutdown."""
        ...


# -----------------------------------------------------------------------------
# Exceptions — domain-level, no HTTP / framework deps
# -----------------------------------------------------------------------------


class KeycloakAdminError(Exception):
    """Base class cho mọi lỗi từ Keycloak Admin client."""


class KeycloakAdminAuthError(KeycloakAdminError):
    """401/403 từ Keycloak — token invalid hoặc service account thiếu permission."""


class KeycloakAdminUserNotFoundError(KeycloakAdminError):
    """404 từ Keycloak — user không tồn tại (có thể vừa bị xoá)."""


class KeycloakAdminRequestError(KeycloakAdminError):
    """Network error, timeout, hoặc 5xx từ Keycloak."""


# -----------------------------------------------------------------------------
# Token cache — module-level singleton
# -----------------------------------------------------------------------------


class _ServiceAccountTokenCache:
    """In-memory cache cho Client Credentials token."""

    __slots__ = ("_expires_at", "_http", "_lock", "_token")

    def __init__(self) -> None:
        self._token: str | None = None
        self._expires_at: float = 0.0
        self._lock = asyncio.Lock()

    async def get_token(self, fetcher: _TokenFetcher) -> str:
        """Trả về token hiện tại (cached) hoặc fetch mới nếu sắp hết hạn.

        Args:
            fetcher: Callable async lấy token mới từ Keycloak (inject để test).
        """
        # Fast path — token còn hạn (>60s buffer)
        if self._token is not None and (self._expires_at - time.monotonic()) > 60:
            return self._token

        # Slow path — lock để không thunder-herd khi nhiều coroutine refresh cùng lúc
        async with self._lock:
            if self._token is not None and (self._expires_at - time.monotonic()) > 60:
                return self._token

            logger = structlog.get_logger(__name__)
            logger.info("keycloak_admin_token_fetch")
            token_data = await fetcher()
            self._token = token_data["access_token"]
            # Keycloak trả ``expires_in`` (giây) — refresh sớm hơn TTL config
            settings = get_settings()
            actual_lifespan = float(token_data.get("expires_in", 300))
            cached_lifespan = min(actual_lifespan, settings.keycloak_admin_token_ttl_seconds)
            self._expires_at = time.monotonic() + cached_lifespan
            return self._token

    def invalidate(self) -> None:
        """Force refresh ở lần kế tiếp — gọi khi nhận 401."""
        self._token = None
        self._expires_at = 0.0


class _TokenFetcher(Protocol):
    async def __call__(self) -> dict[str, Any]: ...


_token_cache = _ServiceAccountTokenCache()


# -----------------------------------------------------------------------------
# HTTP client implementation
# -----------------------------------------------------------------------------


class KeycloakAdminClient:
    """Async HTTP client cho Keycloak Admin REST API.

    Args:
        server_url: Base URL của Keycloak server (VD ``http://localhost:8080``).
        realm: Realm name.
        client_id: Service Account client ID (mặc định = ``contract-intel-backend``).
        client_secret: Service Account client secret.
        timeout: HTTP timeout (giây).
    """

    def __init__(
        self,
        *,
        server_url: str,
        realm: str,
        client_id: str,
        client_secret: str,
        timeout: float = 10.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._server_url = server_url.rstrip("/")
        self._realm = realm
        self._client_id = client_id
        self._client_secret = client_secret
        self._timeout = timeout
        # Caller có thể inject AsyncClient (test fixture) — otherwise tạo mới
        self._http = http_client or httpx.AsyncClient(timeout=timeout)
        self._owns_http = http_client is None

    # ------------------------------------------------------------------
    # Public API (Protocol methods)
    # ------------------------------------------------------------------

    async def get_user_profile(self, user_id: str) -> dict[str, Any]:
        """GET /admin/realms/{realm}/users/{id}.

        Xem :class:`KeycloakAdminClientPort` cho docs.
        """
        if not user_id:
            raise ValueError("user_id is required")

        path = f"/admin/realms/{self._realm}/users/{quote(user_id, safe='')}"
        return cast("dict[str, Any]", await self._authenticated_get(path))

    async def get_user_realm_roles(self, user_id: str) -> list[str]:
        """GET /admin/realms/{realm}/users/{id}/role-mappings/realm.

        Returns:
            List of ``{"name": "OPERATOR", ...}`` → chỉ lấy ``name``.
        """
        if not user_id:
            raise ValueError("user_id is required")

        path = f"/admin/realms/{self._realm}/users/{quote(user_id, safe='')}/role-mappings/realm"
        data = await self._authenticated_get(path)
        if not isinstance(data, list):
            return []
        return [r.get("name", "") for r in data if isinstance(r, dict) and r.get("name")]

    async def close(self) -> None:
        """Close underlying httpx client."""
        if self._owns_http and self._http is not None:
            await self._http.aclose()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch_token(self) -> dict[str, Any]:
        """Client Credentials Grant → access token."""
        url = f"{self._server_url}/realms/{self._realm}/protocol/openid-connect/token"
        try:
            response = await self._http.post(
                url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        except httpx.TimeoutException as exc:
            raise KeycloakAdminRequestError(f"Keycloak token endpoint timeout: {exc}") from exc
        except httpx.HTTPError as exc:
            raise KeycloakAdminRequestError(
                f"Keycloak token endpoint network error: {exc}"
            ) from exc

        if response.status_code >= 400:
            raise KeycloakAdminAuthError(
                f"Token endpoint returned {response.status_code}: {response.text[:500]}"
            )

        try:
            data: dict[str, Any] = response.json()
        except Exception as exc:
            raise KeycloakAdminRequestError(f"Token endpoint returned non-JSON: {exc}") from exc

        if "access_token" not in data:
            raise KeycloakAdminAuthError(f"Token endpoint response missing access_token: {data}")

        return data

    async def _authenticated_get(self, path: str) -> dict[str, Any] | list[Any]:
        """GET với Bearer token — auto refresh token trên 401."""
        token = await _token_cache.get_token(self._fetch_token)
        url = f"{self._server_url}{path}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

        try:
            response = await self._http.get(url, headers=headers)
        except httpx.TimeoutException as exc:
            raise KeycloakAdminRequestError(f"GET {path} timeout: {exc}") from exc
        except httpx.HTTPError as exc:
            raise KeycloakAdminRequestError(f"GET {path} network error: {exc}") from exc

        if response.status_code == 401:
            # Token rejected — invalidate cache rồi thử lại 1 lần
            _token_cache.invalidate()
            token = await _token_cache.get_token(self._fetch_token)
            headers["Authorization"] = f"Bearer {token}"
            try:
                response = await self._http.get(url, headers=headers)
            except httpx.TimeoutException as exc:
                raise KeycloakAdminRequestError(f"GET {path} timeout (retry): {exc}") from exc
            except httpx.HTTPError as exc:
                raise KeycloakAdminRequestError(f"GET {path} network error (retry): {exc}") from exc

        if response.status_code == 404:
            raise KeycloakAdminUserNotFoundError(f"User not found at {path}")
        if response.status_code in (401, 403):
            raise KeycloakAdminAuthError(
                f"GET {path} forbidden ({response.status_code}): {response.text[:500]}"
            )
        if response.status_code >= 400:
            raise KeycloakAdminRequestError(
                f"GET {path} failed ({response.status_code}): {response.text[:500]}"
            )

        try:
            return cast("dict[str, Any] | list[Any]", response.json())
        except Exception as exc:
            raise KeycloakAdminRequestError(f"GET {path} returned non-JSON: {exc}") from exc


# -----------------------------------------------------------------------------
# Module-level singleton accessor (cho FastAPI Depends)
# -----------------------------------------------------------------------------


_admin_client: KeycloakAdminClient | None = None


def get_keycloak_admin_client() -> KeycloakAdminClient:
    """Singleton factory — đọc settings tại thời điểm first call.

    Returns:
        ``KeycloakAdminClient`` bound to current settings.

    Test:
        Override bằng cách monkeypatch attribute này trước khi gọi.
    """
    global _admin_client  # noqa: PLW0603
    if _admin_client is None:
        settings = get_settings()
        _admin_client = KeycloakAdminClient(
            server_url=settings.keycloak_admin_base_url(),
            realm=settings.keycloak_realm,
            client_id=settings.keycloak_admin_client_id,
            client_secret=settings.keycloak_admin_client_secret,
            timeout=settings.keycloak_admin_http_timeout_seconds,
        )
    return _admin_client


def reset_keycloak_admin_client() -> None:
    """Reset singleton — gọi trong lifespan shutdown + test teardown."""
    global _admin_client  # noqa: PLW0603
    if _admin_client is not None:
        # Best-effort close — không await (sync context)
        # httpx.AsyncClient.aclose() cần event loop
        _admin_client = None


__all__ = [
    "KeycloakAdminClient",
    "KeycloakAdminClientPort",
    "KeycloakAdminAuthError",
    "KeycloakAdminError",
    "KeycloakAdminRequestError",
    "KeycloakAdminUserNotFoundError",
    "get_keycloak_admin_client",
    "reset_keycloak_admin_client",
]
