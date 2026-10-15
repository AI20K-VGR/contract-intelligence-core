"""JWT verify service — chỉ decode + verify Keycloak RS256 tokens.

Đây là cross-cutting service, không belong vào bounded context nào.
Đặt trong shared/auth/ để mọi context đều import được.

QUAN TRỌNG — Kiến trúc SSO:
    Backend TUYỆT ĐỐI KHÔNG issue Access Token / Refresh Token.
    Frontend (React) xử lý toàn bộ auth flow với Keycloak:
        - Login:    frontend → Keycloak → nhận access_token + refresh_token
        - Refresh:  frontend → Keycloak (khi access_token hết hạn)
        - Logout:   frontend → Keycloak (revoke session trên Keycloak)

    Backend chỉ:
        - Decode access_token từ Authorization header
        - Verify chữ ký RS256 bằng public key lấy từ Keycloak JWKS
        - Map Keycloak claims (sub, realm_access.roles, tenant_id, ...) → AuthenticatedUser

Keycloak JWKS caching:
    - Fetch public key từ {keycloak_server_url}/realms/{realm}/protocol/openid-connect/certs
    - Cache trong memory với TTL mặc định 3600s (1 giờ)
    - Tự refresh khi key không verify được (kid mismatch — VD: Keycloak rotate key),
      nhưng tối đa 1 lần / 30s: token giả với ``kid`` ngẫu nhiên không được biến
      mỗi request thành một lần gọi Keycloak
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING, Any

import jwt

from contract_intelligence.config.settings import get_settings
from contract_intelligence.shared.auth.exceptions import (
    AuthenticationError,
    InsufficientRoleError,
    TokenExpiredError,
)
from contract_intelligence.shared.auth.schemas import (
    AuthenticatedUser,
    KeycloakTokenClaims,
)

if TYPE_CHECKING:
    from jwt import PyJWK, PyJWKClient


# -----------------------------------------------------------------------------
# JWKS key cache (thread-safe singleton)
# -----------------------------------------------------------------------------


# An unknown ``kid`` refetches the JWKS (Keycloak may have rotated its key),
# but no more often than this.
_MIN_REFRESH_INTERVAL_SECONDS = 30.0
# Requests wait on a fetch; Keycloak answers in milliseconds when healthy.
_JWKS_FETCH_TIMEOUT_SECONDS = 5.0


class _JWKSCache:
    """In-memory JWKS cache với TTL — singleton dùng chung cho cả process."""

    __slots__ = ("_cached_at", "_client", "_keys", "_lock")

    def __init__(self) -> None:
        self._client: PyJWKClient | None = None
        # Last fetch attempt (time.monotonic), successful or not.
        self._cached_at: float = float("-inf")
        self._keys: dict[str, PyJWK] = {}
        self._lock = threading.Lock()

    def get_signing_key(self, kid: str) -> PyJWK | None:
        """Lấy signing key từ JWKS, tự refresh nếu hết TTL hoặc key not found.

        Args:
            kid: Key ID từ JWT header.

        Returns:
            PyJWK object hoặc None nếu không tìm thấy.
        """
        ttl = get_settings().keycloak_jwks_cache_ttl_seconds
        if time.monotonic() - self._cached_at > ttl:
            self._refresh(min_age=ttl)
        return self._keys.get(kid)

    def force_refresh(self) -> None:
        """Refetch JWKS khi kid không tìm thấy (key rotation) — tối đa 1 lần / 30s."""
        self._refresh(min_age=_MIN_REFRESH_INTERVAL_SECONDS)

    def _refresh(self, *, min_age: float) -> None:
        with self._lock:
            # Another request may have fetched while this one waited for the lock.
            if time.monotonic() - self._cached_at <= min_age:
                return
            self._fetch()

    def _fetch(self) -> None:
        settings = get_settings()
        jwks_uri = settings.keycloak_jwks_uri
        if not jwks_uri:
            server = (settings.keycloak_server_url or "").rstrip("/")
            realm = settings.keycloak_realm
            jwks_uri = f"{server}/realms/{realm}/protocol/openid-connect/certs"

        self._client = jwt.PyJWKClient(jwks_uri, timeout=_JWKS_FETCH_TIMEOUT_SECONDS)
        try:
            keys_data = self._client.get_jwk_set()
            self._keys = {}
            for key in keys_data.keys:
                # PyJWT PyJWK exposes key id as ``key_id`` (not ``kid``).
                kid = getattr(key, "key_id", None) or getattr(key, "kid", None)
                if kid:
                    self._keys[kid] = key
            self._cached_at = time.monotonic()
        except Exception as exc:
            # JWKS fetch fail — log và keep using stale cache nếu có
            import structlog

            logger = structlog.get_logger(__name__)
            logger.warning(
                "jwks_refresh_failed",
                uri=jwks_uri,
                error=str(exc),
            )
            # Vẫn set _cached_at để không spam refresh liên tục
            self._cached_at = time.monotonic()


_jwks_cache = _JWKSCache()


# -----------------------------------------------------------------------------
# JWTService
# -----------------------------------------------------------------------------


class JWTService:
    """JWT verify service — chỉ decode + verify Keycloak RS256 tokens.

    Singleton: dùng ``JWTService()`` trực tiếp, không cần inject.

    Settings (issuer, audience) được đọc LAZY trên mỗi lần decode
    để test có thể monkeypatch ``get_settings`` an toàn.
    """

    __slots__ = ()

    # -------------------------------------------------------------------------
    # Decode + verify — entry point duy nhất
    # -------------------------------------------------------------------------

    def decode_and_validate_access(self, token: str) -> AuthenticatedUser:
        """Decode + verify Keycloak access token, trả về AuthenticatedUser.

        Luồng:
            1. Lấy `kid` từ JWT header (không verify)
            2. Tra JWKS cache để lấy public key
            3. Verify RS256 + issuer + (optional) audience
            4. Map Keycloak claims → AuthenticatedUser

        Args:
            token: JWT access token từ Authorization header.

        Returns:
            AuthenticatedUser chứa user_id (sub), tenant_id, email,
            display_name, role.

        Raises:
            AuthenticationError: Token malformed / signature sai / hết hạn /
                                  issuer sai / audience không khớp /
                                  signing key không tìm thấy trong JWKS.
        """
        claims = self._decode_keycloak_token(token)
        return _map_keycloak_claims_to_user(claims)

    # -------------------------------------------------------------------------
    # Internal — Keycloak RS256 verify
    # -------------------------------------------------------------------------

    def _decode_keycloak_token(self, token: str) -> KeycloakTokenClaims:
        """Decode + verify Keycloak JWT (RS256 via JWKS)."""
        # 0. Đọc settings LAZY (mỗi lần decode) để test có thể monkeypatch
        settings = get_settings()
        server = (settings.keycloak_server_url or "").rstrip("/")
        realm = settings.keycloak_realm
        issuer = f"{server}/realms/{realm}"
        audience = settings.keycloak_audience

        # 1. Lấy header để biết kid
        try:
            unverified_header = jwt.get_unverified_header(token)
        except jwt.exceptions.DecodeError as exc:
            raise AuthenticationError("Malformed token header") from exc

        kid = unverified_header.get("kid")
        if not kid:
            raise AuthenticationError("Token missing 'kid' in header")

        # 2. Tra JWKS cache
        key_data = _jwks_cache.get_signing_key(kid)
        if not key_data:
            # Force refresh (Keycloak có thể đã rotate key) rồi retry
            _jwks_cache.force_refresh()
            key_data = _jwks_cache.get_signing_key(kid)
            if not key_data:
                raise AuthenticationError(f"Signing key 'kid={kid}' not found in JWKS")

        # 3. Verify chữ ký + claims
        try:
            raw: dict[str, Any] = jwt.decode(
                token,
                key_data.key,  # PyJWK exposes .key for jwt.decode
                algorithms=["RS256"],
                issuer=issuer,
                audience=audience,  # None = skip aud check
                options={"require": ["exp", "iat", "sub"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenExpiredError from exc
        except jwt.InvalidIssuerError as exc:
            raise AuthenticationError(f"Invalid token issuer: {exc}") from exc
        except jwt.InvalidAudienceError as exc:
            raise AuthenticationError(f"Invalid token audience: {exc}") from exc
        except jwt.InvalidTokenError as exc:
            raise AuthenticationError(f"Invalid token: {exc}") from exc

        # 4. Map Keycloak claims → unified format
        realm_roles: list[str] = []
        raw_realm_access = raw.get("realm_access", {})
        if isinstance(raw_realm_access, dict):
            realm_roles = raw_realm_access.get("roles", []) or []

        mapped_role = _map_keycloak_role(realm_roles)

        # tenant_id: ưu tiên custom claim, fallback về realm
        tenant_id = raw.get("tenant_id") or raw.get("tenant")
        if not tenant_id:
            tenant_id = f"kc_{realm}"

        # Chuẩn hóa raw để build KeycloakTokenClaims
        raw["tenant_id"] = tenant_id
        raw["role"] = mapped_role
        raw["token_type"] = "access"  # chỉ verify access token
        raw["display_name"] = raw.get("name") or raw.get("preferred_username") or ""
        raw["email"] = raw.get("email") or raw.get("preferred_username") or ""
        raw["realm_access_roles"] = realm_roles
        # is_active: từ custom claim (Keycloak protocol mapper). Default True.
        raw["is_active"] = bool(raw.get("is_active", True))

        return KeycloakTokenClaims(**raw)


# -----------------------------------------------------------------------------
# Helpers — pure functions, dễ test
# -----------------------------------------------------------------------------


_APP_ROLES = ("OPERATOR", "REVIEWER", "ADMINISTRATOR")


def _map_keycloak_role(realm_roles: list[str]) -> str:
    """Map Keycloak realm_access.roles[] → RBAC role nội bộ.

    Thứ tự ưu tiên: ADMINISTRATOR > REVIEWER > OPERATOR (admin bao trùm),
    xét trên role đã map, không phụ thuộc thứ tự role trong token.

    Args:
        realm_roles: Danh sách role names từ Keycloak realm_access.roles.

    Returns:
        Một trong "OPERATOR" | "REVIEWER" | "ADMINISTRATOR".

    Raises:
        InsufficientRoleError: token không có role ứng dụng nào (403). Trước đây
            mặc định là OPERATOR, nên một tài khoản trong realm chưa được gán
            role vẫn tải lên và xử lý được hồ sơ.
    """
    settings = get_settings()
    role_map = settings.keycloak_role_map

    mapped = {role_map[r] for r in realm_roles if r in role_map}
    for rbac_role in ("ADMINISTRATOR", "REVIEWER", "OPERATOR"):
        if rbac_role in mapped:
            return rbac_role

    # Không match role nào: thường do token thiếu realm_access.roles hoặc
    # KEYCLOAK_ROLE_MAP không chứa tên realm role → log để dễ phát hiện.
    import structlog

    structlog.get_logger(__name__).warning(
        "keycloak_role_unmapped_denied",
        realm_roles=realm_roles,
        role_map_keys=sorted(role_map),
    )
    raise InsufficientRoleError(_APP_ROLES)


def _map_keycloak_claims_to_user(claims: KeycloakTokenClaims) -> AuthenticatedUser:
    """Convert KeycloakTokenClaims → AuthenticatedUser (shared across codebase)."""
    return AuthenticatedUser(
        user_id=claims.sub,
        tenant_id=claims.tenant_id,
        email=claims.email or "",
        display_name=claims.display_name or "",
        role=claims.role or "OPERATOR",
        is_active=claims.is_active,
    )


# -----------------------------------------------------------------------------
# Module-level singleton accessor
# -----------------------------------------------------------------------------


_jwt_service: JWTService | None = None


def get_jwt_service() -> JWTService:
    """Get JWTService singleton."""
    global _jwt_service  # noqa: PLW0603
    if _jwt_service is None:
        _jwt_service = JWTService()
    return _jwt_service
