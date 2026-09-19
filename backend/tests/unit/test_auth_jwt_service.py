"""Unit tests cho shared/auth/jwt_service.py — HS256 local mode."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from contract_intelligence.config.settings import Settings
from contract_intelligence.shared.auth.exceptions import AuthenticationError
from contract_intelligence.shared.auth.jwt_service import JWTService


# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------

@pytest.fixture
def jwt_service(local_settings: Settings) -> JWTService:
    """JWTService với local HS256 mode."""
    return JWTService()


@pytest.fixture
def local_settings() -> Settings:
    """Override settings sang local HS256 mode."""
    return Settings(
        auth_mode="local",
        jwt_secret_key="test-secret-key-for-unit-tests!!",
        jwt_algorithm="HS256",
        jwt_access_token_expire_minutes=60,
        jwt_refresh_token_expire_days=7,
    )


# -----------------------------------------------------------------------
# Tests: encode_access_token
# -----------------------------------------------------------------------

class TestEncodeAccessToken:
    def test_returns_token_and_expires_in(self, jwt_service: JWTService) -> None:
        token, expires_in = jwt_service.encode_access_token(
            user_id="usr_test123",
            tenant_id="tenant_vgr_01",
            email="test@example.com",
            display_name="Test User",
            role="OPERATOR",
        )
        assert isinstance(token, str)
        assert len(token) > 20
        assert expires_in == 60 * 60  # 3600 seconds

    def test_different_users_get_different_tokens(
        self, jwt_service: JWTService
    ) -> None:
        token1, _ = jwt_service.encode_access_token(
            user_id="usr_001", tenant_id="t1", email="a@t.com",
            display_name="A", role="OPERATOR",
        )
        token2, _ = jwt_service.encode_access_token(
            user_id="usr_002", tenant_id="t1", email="b@t.com",
            display_name="B", role="REVIEWER",
        )
        assert token1 != token2


# -----------------------------------------------------------------------
# Tests: encode_refresh_token
# -----------------------------------------------------------------------

class TestEncodeRefreshToken:
    def test_returns_refresh_token(self, jwt_service: JWTService) -> None:
        token = jwt_service.encode_refresh_token(
            user_id="usr_test123",
            tenant_id="tenant_vgr_01",
            token_version=1,
        )
        assert isinstance(token, str)
        assert len(token) > 20

    def test_different_versions_get_different_tokens(
        self, jwt_service: JWTService
    ) -> None:
        t1 = jwt_service.encode_refresh_token("u1", "t1", token_version=1)
        t2 = jwt_service.encode_refresh_token("u1", "t1", token_version=2)
        assert t1 != t2


# -----------------------------------------------------------------------
# Tests: decode_and_validate_access
# -----------------------------------------------------------------------

class TestDecodeAccessToken:
    def test_roundtrip(self, jwt_service: JWTService) -> None:
        token, _ = jwt_service.encode_access_token(
            user_id="usr_roundtrip",
            tenant_id="tenant_demo",
            email="demo@example.com",
            display_name="Demo User",
            role="ADMINISTRATOR",
        )
        user = jwt_service.decode_and_validate_access(token)

        assert user.user_id == "usr_roundtrip"
        assert user.tenant_id == "tenant_demo"
        assert user.email == "demo@example.com"
        assert user.display_name == "Demo User"
        assert user.role == "ADMINISTRATOR"

    def test_wrong_secret_raises(self, jwt_service: JWTService) -> None:
        # Sign với secret khác
        import jwt as _jwt
        bad_token = _jwt.encode(
            {"sub": "u1", "tenant_id": "t1", "token_type": "access",
             "iat": 0, "exp": 9999999999},
            "wrong-secret",
            algorithm="HS256",
        )
        with pytest.raises(AuthenticationError, match="Invalid token"):
            jwt_service.decode_and_validate_access(bad_token)

    def test_expired_token_raises(self, jwt_service: JWTService) -> None:
        import jwt as _jwt
        from datetime import datetime, timedelta, timezone

        expired = _jwt.encode(
            {
                "sub": "u1",
                "tenant_id": "t1",
                "token_type": "access",
                "iat": int((datetime.now(timezone.utc) - timedelta(hours=2)).timestamp()),
                "exp": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),
            },
            "test-secret-key-for-unit-tests!!",
            algorithm="HS256",
        )
        with pytest.raises(AuthenticationError, match="expired"):
            jwt_service.decode_and_validate_access(expired)

    def test_refresh_token_rejected_as_access(
        self, jwt_service: JWTService
    ) -> None:
        refresh = jwt_service.encode_refresh_token("u1", "t1", token_version=1)
        with pytest.raises(
            AuthenticationError, match="Expected access token"
        ):
            jwt_service.decode_and_validate_access(refresh)


# -----------------------------------------------------------------------
# Tests: decode_refresh_token
# -----------------------------------------------------------------------

class TestDecodeRefreshToken:
    def test_roundtrip(self, jwt_service: JWTService) -> None:
        refresh = jwt_service.encode_refresh_token(
            user_id="usr_refresh",
            tenant_id="tenant_vgr_01",
            token_version=3,
        )
        uid, tid, ver = jwt_service.decode_refresh_token(refresh)
        assert uid == "usr_refresh"
        assert tid == "tenant_vgr_01"
        assert ver == 3

    def test_access_token_rejected_as_refresh(
        self, jwt_service: JWTService
    ) -> None:
        access, _ = jwt_service.encode_access_token(
            "u1", "t1", "e@t.com", "Name", "OPERATOR"
        )
        with pytest.raises(
            AuthenticationError, match="Expected refresh token"
        ):
            jwt_service.decode_refresh_token(access)

    def test_wrong_secret_raises(self, jwt_service: JWTService) -> None:
        import jwt as _jwt
        bad = _jwt.encode(
            {"sub": "u1", "tenant_id": "t1", "token_type": "refresh",
             "token_version": 1, "iat": 0, "exp": 9999999999},
            "wrong-secret",
            algorithm="HS256",
        )
        with pytest.raises(AuthenticationError, match="Invalid token"):
            jwt_service.decode_refresh_token(bad)


# -----------------------------------------------------------------------
# Tests: AppUser token version flow
# -----------------------------------------------------------------------

class TestAppUserTokenVersion:
    def test_increment_token_version(self) -> None:
        from contract_intelligence.identity.domain.entities.app_user import (
            AppUser,
            UserRole,
        )

        user = AppUser(
            id="usr_test",
            tenant_id="tenant_demo",
            email="demo@x.com",
            display_name="Demo",
            role=UserRole.OPERATOR,
            password_hash="hash",
            token_version=0,
        )
        assert user.token_version == 0
        v1 = user.increment_token_version()
        assert v1 == 1
        assert user.token_version == 1
        v2 = user.increment_token_version()
        assert v2 == 2
        assert user.token_version == 2

    def test_revoke_all_sessions(self) -> None:
        from contract_intelligence.identity.domain.entities.app_user import (
            AppUser,
            UserRole,
        )

        user = AppUser(
            id="usr_revoke",
            tenant_id="tenant_demo",
            email="demo@x.com",
            display_name="Demo",
            role=UserRole.OPERATOR,
            password_hash="hash",
            token_version=5,
        )
        user.revoke_all_sessions()
        assert user.token_version == 6

    def test_deactivate_also_revokes(self) -> None:
        from contract_intelligence.identity.domain.entities.app_user import (
            AppUser,
            UserRole,
        )

        user = AppUser(
            id="usr_deact",
            tenant_id="tenant_demo",
            email="demo@x.com",
            display_name="Demo",
            role=UserRole.OPERATOR,
            password_hash="hash",
            is_active=True,
            token_version=2,
        )
        user.deactivate()
        assert user.is_active is False
        assert user.token_version == 3


# -----------------------------------------------------------------------
# Helper: override settings for tests
# -----------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _patch_settings(local_settings: Settings) -> None:
    """Auto-apply local_settings cho mọi test trong module này."""
    with patch(
        "contract_intelligence.shared.auth.jwt_service.get_settings",
        return_value=local_settings,
    ):
        yield
