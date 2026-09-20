"""Shared pytest fixtures cho auth module tests.

Sau refactor Keycloak SSO:
    - Không còn `auth_settings` (local HS256 mode đã bị bỏ).
    - Test sử dụng mock Keycloak JWKS + sign JWT với RSA private key
      thay vì gọi /auth/login để lấy token.
"""

from __future__ import annotations

import json
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWK

from contract_intelligence.config.settings import Settings
from contract_intelligence.shared.auth.exceptions import AuthenticationError
from contract_intelligence.shared.auth.jwt_service import _JWKSCache
from contract_intelligence.shared.auth.schemas import AuthenticatedUser


@pytest.fixture
def sample_dossier_id() -> str:
    return "dos_01HZ1234567890ABCDEFGHIJ"


@pytest.fixture
def sample_document_id() -> str:
    return "doc_01HZ1234567890ABCDEFGHIJ"


@pytest.fixture
def keycloak_test_settings() -> Settings:
    """Settings cho Keycloak test mode — chỉ dùng trong test."""
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
def rsa_keypair() -> tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
    """RSA keypair trong memory cho test."""
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private, private.public_key()


@pytest.fixture
def cached_keycloak_jwks(
    monkeypatch: pytest.MonkeyPatch,
    rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey],
) -> str:
    """Patch global JWKS cache với test public key.

    Returns:
        kid (key ID) của key trong cache — dùng để sign JWT trong test.
    """
    _, public_key = rsa_keypair
    from jwt.algorithms import RSAAlgorithm

    jwk_dict = json.loads(RSAAlgorithm.to_jwk(public_key))
    jwk_dict["kid"] = "test-kid-1"
    jwk_dict["alg"] = "RS256"
    jwk_dict["use"] = "sig"
    pyjwk = PyJWK.from_dict(jwk_dict)

    fake_cache = _JWKSCache()
    fake_cache._keys = {"test-kid-1": pyjwk}  # noqa: SLF001
    fake_cache._cached_at = float("inf")  # never expire

    monkeypatch.setattr(
        "contract_intelligence.shared.auth.jwt_service._jwks_cache",
        fake_cache,
    )
    return "test-kid-1"


@pytest.fixture
def mock_keycloak_settings(
    monkeypatch: pytest.MonkeyPatch,
    keycloak_test_settings: Settings,
) -> Settings:
    """Patch get_settings() to return Keycloak test settings."""
    monkeypatch.setattr(
        "contract_intelligence.shared.auth.jwt_service.get_settings",
        lambda: keycloak_test_settings,
    )
    return keycloak_test_settings


@pytest.fixture
def make_keycloak_token(
    rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey],
    keycloak_test_settings: Settings,
    cached_keycloak_jwks: str,
    mock_keycloak_settings: Settings,
):
    """Factory function tạo Keycloak JWT cho test.

    Args:
        rsa_keypair: RSA private + public key trong memory.
        keycloak_test_settings: Keycloak test settings.
        cached_keycloak_jwks: Patch JWKS cache với public key tương ứng.
        mock_keycloak_settings: Patch get_settings() để trả về Keycloak test settings.

    Returns:
        Hàm tạo JWT đã sign với private key, phù hợp để verify qua mock JWKS.

    Usage:
        def test_xxx(make_keycloak_token):
            token = make_keycloak_token(role="REVIEWER", user_id="usr_123")
            headers = {"Authorization": f"Bearer {token}"}
    """
    private_key, _ = rsa_keypair
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    def _make(
        *,
        kid: str = "test-kid-1",
        user_id: str = "usr_01HZ_TEST",
        tenant_id: str = "tenant_vgr_01",
        email: str = "test@vgr.vn",
        display_name: str = "Test User",
        role: str = "OPERATOR",
        exp_delta_seconds: int = 3600,
        audience: str | None = None,
        issuer: str | None = None,
        extra_claims: dict[str, Any] | None = None,
    ) -> str:
        from datetime import UTC, datetime, timedelta

        now = datetime.now(UTC)
        kc_role_map = {
            "OPERATOR": "ci_operator",
            "REVIEWER": "ci_reviewer",
            "ADMINISTRATOR": "ci_administrator",
        }
        realm_roles = [kc_role_map[role]] if role in kc_role_map else []

        claims: dict[str, Any] = {
            "sub": user_id,
            "email": email,
            "name": display_name,
            "preferred_username": email.split("@")[0],
            "iss": (
                issuer
                or (
                    f"{keycloak_test_settings.keycloak_server_url}"
                    f"/realms/{keycloak_test_settings.keycloak_realm}"
                )
            ),
            "aud": audience or keycloak_test_settings.keycloak_client_id,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=exp_delta_seconds)).timestamp()),
            "tenant_id": tenant_id,
            "realm_access": {"roles": realm_roles},
        }
        if extra_claims:
            claims.update(extra_claims)
        return jwt.encode(claims, pem, algorithm="RS256", headers={"kid": kid})

    return _make


@pytest.fixture
def operator_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="usr_test_operator",
        tenant_id="tenant_vgr_01",
        email="operator@vgr.vn",
        display_name="Lê Văn Vận Hành",
        role="OPERATOR",
    )


@pytest.fixture
def reviewer_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="usr_test_reviewer",
        tenant_id="tenant_vgr_01",
        email="reviewer@vgr.vn",
        display_name="Trần Thị Phê Duyệt",
        role="REVIEWER",
    )


@pytest.fixture
def admin_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="usr_test_admin",
        tenant_id="tenant_vgr_01",
        email="admin@vgr.vn",
        display_name="Nguyễn Quản Trị",
        role="ADMINISTRATOR",
    )


# Re-export AuthenticationError cho test sử dụng
__all__ = ["AuthenticationError"]
