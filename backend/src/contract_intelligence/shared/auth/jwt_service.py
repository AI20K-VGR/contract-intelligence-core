r"""JWT encode/decode service — supports HS256 (local) and RS256 (Keycloak).

Đây là cross-cutting service, không belong vào bounded context nào.
Đặt trong shared/auth/ để mọi context đều import được.

Mode detection:
    settings.auth_mode == "local"  → HS256, self-issued JWT
    settings.auth_mode == "keycloak" → RS256, verify via Keycloak JWKS

Keycloak JWKS caching:
    - Fetch public key từ {keycloak_server_url}/realms/{realm}/protocol/openid-connect/certs
    - Cache trong memory với TTL 3600s (1 giờ)
    - Tự refresh khi key không verify được (kid mismatch)
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import jwt

from contract_intelligence.config.settings import get_settings
from contract_intelligence.shared.auth.exceptions import AuthenticationError
from contract_intelligence.shared.auth.schemas import (
    AuthenticatedUser,
    KeycloakTokenClaims,
    LocalTokenClaims,
    TokenType,
)

if TYPE_CHECKING:
    from jwt import PyJWKClient

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

_ACCESS_EXP_MINUTES: int = 60       # 1 hour
_REFRESH_EXP_DAYS: int = 7          # 7 days
_JWKS_CACHE_TTL_SECONDS: int = 3600  # 1 hour

# Header keys
_HEADER_TYP: str = "typ"
_HEADER_KID: str = "kid"


# -----------------------------------------------------------------------------
# JWKS key cache (thread-safe singleton)
# -----------------------------------------------------------------------------

class _JWKSCache:
    """In-memory JWKS cache với TTL.

    Singleton dùng chung cho cả process.
    """

    __slots__ = ("_client", "_cached_at", "_keys")

    def __init__(self) -> None:
        self._client: PyJWKClient | None = None
        self._cached_at: float = 0.0
        self._keys: dict[str, Any] = {}

    def get_signing_key(self, kid: str) -> Any:
        """Lấy signing key từ JWKS, tự refresh nếu hết TTL hoặc key not found."""
        now = time.monotonic()
        if (
            self._client is None
            or (now - self._cached_at) > _JWKS_CACHE_TTL_SECONDS
        ):
            self._refresh()
        return self._keys.get(kid)

    def _refresh(self) -> None:
        settings = get_settings()
        jwks_uri = settings.keycloak_jwks_uri
        if not jwks_uri:
            realm = settings.keycloak_realm
            server = settings.keycloak_server_url or ""
            jwks_uri = f"{server.rstrip('/')}/realms/{realm}/protocol/openid-connect/certs"

        self._client = jwt.PyJWKClient(jwks_uri)
        try:
            keys_data = self._client.get_jwk_set()
            # keys_data is a PyJWKSet, iterate .keys
            self._keys = {}
            for key in keys_data.keys:
                kid = getattr(key, "kid", None)
                if kid:
                    self._keys[kid] = key
            self._cached_at = time.monotonic()
        except Exception as exc:
            # JWKS fetch fail — log và keep using stale cache
            import structlog
            logger = structlog.get_logger(__name__)
            logger.warning(
                "jwks_refresh_failed",
                uri=jwks_uri,
                error=str(exc),
            )
            # Still try stale cache
            self._cached_at = time.monotonic()


_jwks_cache = _JWKSCache()


# -----------------------------------------------------------------------------
# JWTService
# -----------------------------------------------------------------------------

class JWTService:
    """JWT encode/decode service — local HS256 hoặc Keycloak RS256.

    Singleton: dùng ``JWTService()`` trực tiếp, không cần inject.
    """

    __slots__ = ("_secret_key", "_algorithm", "_auth_mode", "_keycloak_issuer")

    def __init__(self) -> None:
        settings = get_settings()
        self._auth_mode = settings.auth_mode
        self._secret_key = settings.jwt_secret_key
        self._algorithm = settings.jwt_algorithm

        # Keycloak issuer for RS256 mode
        if self._auth_mode == "keycloak":
            server = settings.keycloak_server_url or ""
            realm = settings.keycloak_realm
            self._keycloak_issuer = f"{server.rstrip('/')}/realms/{realm}"
        else:
            self._keycloak_issuer = ""

    # -------------------------------------------------------------------------
    # Encode — tạo token (chỉ dùng trong auth_service.py)
    # -------------------------------------------------------------------------

    def encode_access_token(
        self,
        user_id: str,
        tenant_id: str,
        email: str,
        display_name: str,
        role: str,
    ) -> tuple[str, int]:
        """Tạo access token JWT.

        Args:
            user_id: "usr_..."
            tenant_id: "tenant_vgr_01"
            email: user email
            display_name: full name
            role: "OPERATOR" | "REVIEWER" | "ADMINISTRATOR"

        Returns:
            (token_string, expires_in_seconds)
        """
        now = datetime.now(UTC)
        exp = now + timedelta(minutes=_ACCESS_EXP_MINUTES)
        payload: dict[str, Any] = {
            "sub": user_id,
            "email": email,
            "display_name": display_name,
            "role": role,
            "tenant_id": tenant_id,
            "token_type": TokenType.ACCESS.value,
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
        }
        return (
            jwt.encode(payload, self._secret_key, algorithm=self._algorithm),
            _ACCESS_EXP_MINUTES * 60,
        )

    def encode_refresh_token(
        self,
        user_id: str,
        tenant_id: str,
        token_version: int,
    ) -> str:
        """Tạo refresh token JWT.

        Args:
            user_id: "usr_..."
            tenant_id: "tenant_vgr_01"
            token_version: Số version hiện tại của user — dùng revoke.

        Returns:
            token_string
        """
        now = datetime.now(UTC)
        exp = now + timedelta(days=_REFRESH_EXP_DAYS)
        payload: dict[str, Any] = {
            "sub": user_id,
            "tenant_id": tenant_id,
            "token_type": TokenType.REFRESH.value,
            "token_version": token_version,
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
        }
        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

    # -------------------------------------------------------------------------
    # Decode — xác thực và parse token
    # -------------------------------------------------------------------------

    def decode_and_validate_access(
        self, token: str
    ) -> AuthenticatedUser:
        """Decode + validate access token, trả về AuthenticatedUser.

        Raises:
            AuthenticationError: Token hết hạn, sai secret, hoặc không phải access token.
        """
        claims = self._decode_token(token, for_token_type=TokenType.ACCESS)

        return AuthenticatedUser(
            user_id=claims.sub,
            tenant_id=claims.tenant_id,
            email=claims.email or "",
            display_name=claims.display_name or "",
            role=claims.role or "",
            token_type=TokenType.ACCESS,
        )

    def decode_refresh_token(self, token: str) -> tuple[str, str, int]:
        """Decode refresh token, trả về (user_id, tenant_id, token_version).

        Raises:
            AuthenticationError: Token không hợp lệ / hết hạn.
        """
        claims = self._decode_token(token, for_token_type=TokenType.REFRESH)

        return (
            claims.sub,
            claims.tenant_id,
            claims.token_version,
        )

    # -------------------------------------------------------------------------
    # Internal decode — mode-aware
    # -------------------------------------------------------------------------

    def _decode_token(
        self, token: str, *, for_token_type: TokenType
    ) -> LocalTokenClaims | KeycloakTokenClaims:
        """Decode token theo auth mode.

        Local mode:    verify HS256/RS256 với secret/public key
        Keycloak mode: verify RS256 với JWKS public key
        """
        if self._auth_mode == "keycloak":
            return self._decode_keycloak_token(token, for_token_type)
        return self._decode_local_token(token, for_token_type)

    def _decode_local_token(
        self, token: str, for_token_type: TokenType
    ) -> LocalTokenClaims:
        """Decode + verify local JWT (HS256)."""
        try:
            raw = jwt.decode(
                token,
                self._secret_key,
                algorithms=[self._algorithm],
                options={"require": ["sub", "exp", "iat"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise AuthenticationError("Token has expired") from exc
        except jwt.InvalidTokenError as exc:
            raise AuthenticationError(f"Invalid token: {exc}") from exc

        # Validate token_type
        actual_type = raw.get("token_type")
        if actual_type != for_token_type.value:
            raise AuthenticationError(
                f"Expected {for_token_type.value} token, got {actual_type!r}"
            )

        return LocalTokenClaims(**raw)

    def _decode_keycloak_token(
        self, token: str, for_token_type: TokenType
    ) -> KeycloakTokenClaims:
        """Decode + verify Keycloak JWT (RS256 via JWKS)."""
        # Get header để lấy kid
        try:
            unverified_header = jwt.get_unverified_header(token)
        except jwt.exceptions.DecodeError as exc:
            raise AuthenticationError("Malformed token header") from exc

        kid = unverified_header.get("kid")
        if not kid:
            raise AuthenticationError("Token missing 'kid' in header")

        # Get signing key from JWKS cache
        key_data = _jwks_cache.get_signing_key(kid)
        if not key_data:
            # Force JWKS refresh and retry once
            _jwks_cache._refresh()  # noqa: SLF001
            key_data = _jwks_cache.get_signing_key(kid)
            if not key_data:
                raise AuthenticationError(
                    f"Signing key 'kid={kid}' not found in JWKS"
                )

        try:
            # key_data is already a PyJWK from the cached JWKS — pass directly
            raw = jwt.decode(
                token,
                key_data,
                algorithms=["RS256"],
                issuer=self._keycloak_issuer,
                options={"require": ["exp", "iat", "sub"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise AuthenticationError("Token has expired") from exc
        except jwt.InvalidIssuerError as exc:
            raise AuthenticationError(f"Invalid token issuer: {exc}") from exc
        except jwt.InvalidTokenError as exc:
            raise AuthenticationError(f"Invalid token: {exc}") from exc

        # Map Keycloak claims → unified format
        realm_roles: list[str] = []
        raw_realm_access = raw.get("realm_access", {})
        if isinstance(raw_realm_access, dict):
            realm_roles = raw_realm_access.get("roles", [])

        # Map Keycloak role → our RBAC roles
        keycloak_role_map: dict[str, str] = {
            "ci_operator": "OPERATOR",
            "ci_reviewer": "REVIEWER",
            "ci_administrator": "ADMINISTRATOR",
        }
        mapped_role = ""
        for kr in realm_roles:
            if kr in keycloak_role_map:
                mapped_role = keycloak_role_map[kr]
                break
        if not mapped_role:
            mapped_role = "OPERATOR"  # fallback

        # tenant_id from custom claim hoặc Keycloak realm
        tenant_id = raw.get(
            "tenant_id",
            raw.get("tenant", "default"),
        )
        if tenant_id == "default":
            # Fallback: dùng Keycloak realm làm tenant
            realm = get_settings().keycloak_realm
            tenant_id = f"kc_{realm}"

        raw["tenant_id"] = tenant_id
        raw["role"] = mapped_role
        raw["token_type"] = for_token_type.value
        raw["display_name"] = raw.get("name") or raw.get("preferred_username") or ""
        raw["email"] = raw.get("email") or raw.get("preferred_username") or ""

        return KeycloakTokenClaims(**raw)


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
