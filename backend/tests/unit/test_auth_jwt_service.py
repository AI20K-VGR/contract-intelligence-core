"""Unit tests cho shared/auth/jwt_service.py — Keycloak RS256 verify.

Sau refactor Keycloak SSO, JWT service chỉ verify (KHÔNG encode).
Test approach:
    - Tạo 1 RSA keypair trong bộ nhớ (cryptography lib)
    - Build JWKS response từ public key
    - Mock JWKS cache để trả về public key
    - Sign test JWT với private key
    - Verify JWT → expect AuthenticatedUser đúng

Cần cài `cryptography` lib — đã có sẵn vì Keycloak service yêu cầu.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from contract_intelligence.config.settings import Settings
from contract_intelligence.shared.auth.exceptions import AuthenticationError
from contract_intelligence.shared.auth.jwt_service import (
    JWTService,
    _JWKSCache,
    _map_keycloak_role,
)

# -----------------------------------------------------------------------------
# Helpers — tạo RSA keypair + JWKS cho test
# -----------------------------------------------------------------------------


def _make_keypair() -> tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
    """Tạo RSA keypair trong memory."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    return private_key, public_key


def _public_key_to_jwk(public_key: rsa.RSAPublicKey, kid: str = "test-key-1") -> dict[str, Any]:
    """Convert public key → JWK dict (format Keycloak trả về)."""
    # PyJWT sẽ parse PEM thành JWK tự động khi gọi from_jwk
    # Nhưng để test thực tế với cache, ta build dict manually
    from jwt.algorithms import RSAAlgorithm

    jwk_dict = json.loads(RSAAlgorithm.to_jwk(public_key))
    jwk_dict["kid"] = kid
    jwk_dict["alg"] = "RS256"
    jwk_dict["use"] = "sig"
    return jwk_dict


import json  # noqa: E402  — placed after helpers for readability

# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def keypair() -> tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
    """RSA keypair cho mỗi test — đảm bảo isolation."""
    return _make_keypair()


@pytest.fixture
def keycloak_settings(keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]) -> Settings:
    """Settings cho Keycloak test mode."""
    return Settings(
        env="test",
        auth_mode="keycloak",
        keycloak_server_url="https://test-keycloak.local",
        keycloak_realm="test-realm",
        keycloak_client_id="ci-backend",
        keycloak_audience="ci-backend",
        keycloak_role_map={
            "ci_operator": "OPERATOR",
            "ci_reviewer": "REVIEWER",
            "ci_administrator": "ADMINISTRATOR",
        },
    )


@pytest.fixture
def jwt_service(keycloak_settings: Settings) -> JWTService:
    """JWTService với Keycloak test settings."""
    return JWTService()


@pytest.fixture
def cached_jwks(
    monkeypatch: pytest.MonkeyPatch,
    keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey],
) -> None:
    """Patch JWKS cache để trả về public key mà không cần HTTP call.

    Inject 1 PyJWK thẳng vào cache.
    """
    _, public_key = keypair
    jwk_dict = _public_key_to_jwk(public_key, kid="test-key-1")

    from jwt import PyJWK

    pyjwk = PyJWK.from_dict(jwk_dict)

    fake_cache = _JWKSCache()
    fake_cache._keys = {"test-key-1": pyjwk}  # noqa: SLF001
    fake_cache._cached_at = float("inf")  # never expire

    # Patch global cache
    monkeypatch.setattr(
        "contract_intelligence.shared.auth.jwt_service._jwks_cache",
        fake_cache,
    )


def _sign_keycloak_token(
    private_key: rsa.RSAPrivateKey,
    *,
    kid: str = "test-key-1",
    issuer: str = "https://test-keycloak.local/realms/test-realm",
    audience: str = "ci-backend",
    sub: str = "usr_01HZ_TEST_USER",
    email: str = "test@vgr.vn",
    name: str = "Test User",
    realm_roles: list[str] | None = None,
    tenant_id: str = "tenant_vgr_01",
    exp_delta: timedelta = timedelta(hours=1),
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Sign JWT với private key theo format Keycloak."""
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        "sub": sub,
        "email": email,
        "name": name,
        "preferred_username": email.split("@")[0],
        "iss": issuer,
        "aud": audience,
        "iat": int(now.timestamp()),
        "exp": int((now + exp_delta).timestamp()),
        "tenant_id": tenant_id,
        "realm_access": {"roles": realm_roles or []},
    }
    if extra_claims:
        claims.update(extra_claims)
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return jwt.encode(claims, pem, algorithm="RS256", headers={"kid": kid})


# -----------------------------------------------------------------------------
# Tests — decode_and_validate_access (happy path)
# -----------------------------------------------------------------------------


class TestDecodeAccessToken:
    def test_roundtrip_returns_authenticated_user(
        self,
        keycloak_settings: Settings,
        keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey],
        cached_jwks: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Sign → verify → expect AuthenticatedUser fields đúng."""
        private_key, _ = keypair
        monkeypatch.setattr(
            "contract_intelligence.shared.auth.jwt_service.get_settings",
            lambda: keycloak_settings,
        )

        token = _sign_keycloak_token(
            private_key,
            realm_roles=["ci_reviewer"],
            email="reviewer@vgr.vn",
            name="Trần Thị Phê Duyệt",
        )

        svc = JWTService()
        user = svc.decode_and_validate_access(token)

        assert user.user_id == "usr_01HZ_TEST_USER"
        assert user.email == "reviewer@vgr.vn"
        assert user.display_name == "Trần Thị Phê Duyệt"
        assert user.role == "REVIEWER"
        assert user.tenant_id == "tenant_vgr_01"

    def test_administrator_role_higher_priority(
        self,
        keycloak_settings: Settings,
        keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey],
        cached_jwks: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """User có cả operator + administrator → role phải là ADMINISTRATOR."""
        private_key, _ = keypair
        monkeypatch.setattr(
            "contract_intelligence.shared.auth.jwt_service.get_settings",
            lambda: keycloak_settings,
        )

        token = _sign_keycloak_token(
            private_key,
            realm_roles=["ci_operator", "ci_administrator"],
        )
        svc = JWTService()
        user = svc.decode_and_validate_access(token)
        assert user.role == "ADMINISTRATOR"

    def test_fallback_to_operator_when_no_known_role(
        self,
        keycloak_settings: Settings,
        keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey],
        cached_jwks: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """User không có role nào match → fallback OPERATOR."""
        private_key, _ = keypair
        monkeypatch.setattr(
            "contract_intelligence.shared.auth.jwt_service.get_settings",
            lambda: keycloak_settings,
        )

        token = _sign_keycloak_token(
            private_key,
            realm_roles=["some_other_role"],
        )
        svc = JWTService()
        user = svc.decode_and_validate_access(token)
        assert user.role == "OPERATOR"


# -----------------------------------------------------------------------------
# Tests — error paths
# -----------------------------------------------------------------------------


class TestDecodeAccessTokenErrors:
    def test_expired_token_raises(
        self,
        keycloak_settings: Settings,
        keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey],
        cached_jwks: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        private_key, _ = keypair
        monkeypatch.setattr(
            "contract_intelligence.shared.auth.jwt_service.get_settings",
            lambda: keycloak_settings,
        )

        token = _sign_keycloak_token(private_key, exp_delta=timedelta(hours=-1))
        svc = JWTService()
        with pytest.raises(AuthenticationError, match="expired"):
            svc.decode_and_validate_access(token)

    def test_wrong_issuer_raises(
        self,
        keycloak_settings: Settings,
        keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey],
        cached_jwks: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        private_key, _ = keypair
        monkeypatch.setattr(
            "contract_intelligence.shared.auth.jwt_service.get_settings",
            lambda: keycloak_settings,
        )

        token = _sign_keycloak_token(private_key, issuer="https://attacker.com")
        svc = JWTService()
        with pytest.raises(AuthenticationError, match="issuer"):
            svc.decode_and_validate_access(token)

    def test_wrong_audience_raises(
        self,
        keycloak_settings: Settings,
        keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey],
        cached_jwks: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        private_key, _ = keypair
        monkeypatch.setattr(
            "contract_intelligence.shared.auth.jwt_service.get_settings",
            lambda: keycloak_settings,
        )

        token = _sign_keycloak_token(private_key, audience="some-other-client")
        svc = JWTService()
        with pytest.raises(AuthenticationError, match="audience"):
            svc.decode_and_validate_access(token)

    def test_wrong_signature_raises(
        self,
        keycloak_settings: Settings,
        keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey],
        cached_jwks: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Token sign với key khác (không phải public key trong JWKS) → 401."""
        # Tạo key khác, sign với nó nhưng cùng kid để cache lookup OK
        # → JWT decode sẽ tìm thấy key nhưng signature sai
        other_private, _ = _make_keypair()
        monkeypatch.setattr(
            "contract_intelligence.shared.auth.jwt_service.get_settings",
            lambda: keycloak_settings,
        )

        token = _sign_keycloak_token(other_private, kid="test-key-1")
        svc = JWTService()
        with pytest.raises(AuthenticationError, match="Signature verification failed"):
            svc.decode_and_validate_access(token)

    def test_unknown_kid_raises(
        self,
        keycloak_settings: Settings,
        keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey],
        cached_jwks: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Token có kid không có trong JWKS cache → 401."""
        # Tạo key khác + kid khác → không có trong cache
        other_private, _ = _make_keypair()
        monkeypatch.setattr(
            "contract_intelligence.shared.auth.jwt_service.get_settings",
            lambda: keycloak_settings,
        )

        token = _sign_keycloak_token(other_private, kid="unknown-kid-999")
        svc = JWTService()
        with pytest.raises(AuthenticationError, match="not found"):
            svc.decode_and_validate_access(token)

    def test_malformed_token_raises(
        self,
        keycloak_settings: Settings,
        cached_jwks: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            "contract_intelligence.shared.auth.jwt_service.get_settings",
            lambda: keycloak_settings,
        )
        svc = JWTService()
        with pytest.raises(AuthenticationError, match="Malformed"):
            svc.decode_and_validate_access("not.a.jwt")

    def test_missing_kid_raises(
        self,
        keycloak_settings: Settings,
        keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Token không có kid trong header → 401."""
        private_key, _ = keypair
        monkeypatch.setattr(
            "contract_intelligence.shared.auth.jwt_service.get_settings",
            lambda: keycloak_settings,
        )

        pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        token = jwt.encode(
            {"sub": "u1", "exp": 9999999999, "iat": 0},
            pem,
            algorithm="RS256",
            # NO kid header
        )
        svc = JWTService()
        with pytest.raises(AuthenticationError, match="kid"):
            svc.decode_and_validate_access(token)


# -----------------------------------------------------------------------------
# Tests — helper _map_keycloak_role
# -----------------------------------------------------------------------------


class TestMapKeycloakRole:
    def test_priority_admin_over_reviewer_over_operator(
        self,
        keycloak_settings: Settings,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            "contract_intelligence.shared.auth.jwt_service.get_settings",
            lambda: keycloak_settings,
        )
        assert _map_keycloak_role(["ci_administrator"]) == "ADMINISTRATOR"
        assert _map_keycloak_role(["ci_administrator", "ci_operator"]) == "ADMINISTRATOR"
        assert _map_keycloak_role(["ci_reviewer"]) == "REVIEWER"
        assert _map_keycloak_role(["ci_reviewer", "ci_operator"]) == "REVIEWER"
        assert _map_keycloak_role(["ci_operator"]) == "OPERATOR"

    def test_empty_roles_fallback_operator(
        self,
        keycloak_settings: Settings,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            "contract_intelligence.shared.auth.jwt_service.get_settings",
            lambda: keycloak_settings,
        )
        assert _map_keycloak_role([]) == "OPERATOR"

    def test_unknown_role_fallback_operator(
        self,
        keycloak_settings: Settings,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            "contract_intelligence.shared.auth.jwt_service.get_settings",
            lambda: keycloak_settings,
        )
        assert _map_keycloak_role(["some_other_role"]) == "OPERATOR"


# -----------------------------------------------------------------------------
# Helper: auto-patch settings cho mọi test
# -----------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _patch_settings(keycloak_settings: Settings) -> None:
    """Auto-apply keycloak_settings cho các test không tự patch."""
    with patch(
        "contract_intelligence.shared.auth.jwt_service.get_settings",
        return_value=keycloak_settings,
    ):
        yield
