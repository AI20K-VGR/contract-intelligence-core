"""Unit tests cho shared/auth/dependencies.py — FastAPI dependency injection."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from contract_intelligence.shared.auth.dependencies import (
    get_current_user,
    require_role,
)
from contract_intelligence.shared.auth.exceptions import (
    AuthenticationError,
    InsufficientRoleError,
)
from contract_intelligence.shared.auth.schemas import AuthenticatedUser, TokenType


# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------

@pytest.fixture
def valid_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="usr_test_reviewer",
        tenant_id="tenant_vgr_01",
        email="reviewer@vgr.vn",
        display_name="Trần Phê Duyệt",
        role="REVIEWER",
        token_type=TokenType.ACCESS,
    )


@pytest.fixture
def mock_request(valid_user: AuthenticatedUser) -> MagicMock:
    req = MagicMock()
    req.state = MagicMock()
    req.state.authenticated_user = valid_user
    return req


# -----------------------------------------------------------------------
# get_current_user tests
# -----------------------------------------------------------------------

class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_missing_authorization_header(self) -> None:
        req = MagicMock()
        req.state = MagicMock()
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(req, authorization=None)
        assert exc_info.value.status_code == 401
        assert "Missing Authorization header" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_invalid_bearer_format(self) -> None:
        req = MagicMock()
        req.state = MagicMock()
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(req, authorization="Basic dXNlcjpwYXNz")
        assert exc_info.value.status_code == 401
        assert "Bearer" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_valid_token_returns_user(
        self, mock_request: MagicMock, valid_user: AuthenticatedUser
    ) -> None:
        with patch(
            "contract_intelligence.shared.auth.dependencies.get_jwt_service"
        ) as mock_jwt:
            mock_jwt.return_value.decode_and_validate_access.return_value = (
                valid_user
            )
            result = await get_current_user(
                mock_request, authorization="Bearer valid.jwt.token"
            )
            assert result.user_id == valid_user.user_id
            assert result.tenant_id == valid_user.tenant_id
            assert result.role == valid_user.role
            # Attach to request state
            assert mock_request.state.authenticated_user == valid_user

    @pytest.mark.asyncio
    async def test_expired_token_returns_401(self, mock_request: MagicMock) -> None:
        with patch(
            "contract_intelligence.shared.auth.dependencies.get_jwt_service"
        ) as mock_jwt:
            mock_jwt.return_value.decode_and_validate_access.side_effect = (
                AuthenticationError("Token has expired")
            )
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(
                    mock_request, authorization="Bearer expired.jwt.token"
                )
            assert exc_info.value.status_code == 401
            assert "expired" in exc_info.value.detail


# -----------------------------------------------------------------------
# require_role tests
# -----------------------------------------------------------------------

class TestRequireRole:
    @pytest.mark.asyncio
    async def test_allowed_role_passes(
        self, mock_request: MagicMock, valid_user: AuthenticatedUser
    ) -> None:
        # require_role returns Depends-wrapped closure. Call inner directly
        # with explicit user injection to bypass Depends resolution.
        with patch(
            "contract_intelligence.shared.auth.dependencies.get_current_user",
            return_value=valid_user,
        ):
            checker = require_role("REVIEWER", "ADMINISTRATOR")
            # The inner closure is stored as __wrapped__ attribute by functools
            inner = getattr(checker, "__wrapped__", checker)
            result = await inner(user=valid_user)
            assert result.role == "REVIEWER"

    @pytest.mark.asyncio
    async def test_disallowed_role_raises_403(
        self, mock_request: MagicMock, valid_user: AuthenticatedUser
    ) -> None:
        with patch(
            "contract_intelligence.shared.auth.dependencies.get_current_user",
            return_value=valid_user,
        ):
            checker = require_role("ADMINISTRATOR")  # REVIEWER không đủ
            inner = getattr(checker, "__wrapped__", checker)
            with pytest.raises(HTTPException) as exc_info:
                await inner(user=valid_user)
            assert exc_info.value.status_code == 403
            assert "Insufficient role" in exc_info.value.detail


# -----------------------------------------------------------------------
# AuthenticatedUser helper tests
# -----------------------------------------------------------------------

class TestAuthenticatedUser:
    def test_has_role_single(self, valid_user: AuthenticatedUser) -> None:
        assert valid_user.has_role("REVIEWER") is True
        assert valid_user.has_role("ADMINISTRATOR") is False

    def test_has_role_multiple(
        self, valid_user: AuthenticatedUser
    ) -> None:
        assert valid_user.has_role("OPERATOR", "REVIEWER") is True
        assert valid_user.has_role("ADMINISTRATOR", "OPERATOR") is False
