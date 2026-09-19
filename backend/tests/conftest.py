"""Shared pytest fixtures cho auth module tests."""

from __future__ import annotations

import pytest

from contract_intelligence.config.settings import Settings
from contract_intelligence.shared.auth.schemas import AuthenticatedUser, TokenType


@pytest.fixture
def sample_dossier_id() -> str:
    return "dos_01HZ1234567890ABCDEFGHIJ"


@pytest.fixture
def sample_document_id() -> str:
    return "doc_01HZ1234567890ABCDEFGHIJ"


@pytest.fixture
def auth_settings() -> Settings:
    """Settings cho auth module tests — local HS256 mode."""
    return Settings(
        env="test",
        auth_mode="local",
        jwt_secret_key="test-secret-key-for-unit-tests!!",
        jwt_algorithm="HS256",
        jwt_access_token_expire_minutes=60,
        jwt_refresh_token_expire_days=7,
    )


@pytest.fixture
def operator_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="usr_test_operator",
        tenant_id="tenant_vgr_01",
        email="operator@vgr.vn",
        display_name="Lê Văn Vận Hành",
        role="OPERATOR",
        token_type=TokenType.ACCESS,
    )


@pytest.fixture
def reviewer_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="usr_test_reviewer",
        tenant_id="tenant_vgr_01",
        email="reviewer@vgr.vn",
        display_name="Trần Thị Phê Duyệt",
        role="REVIEWER",
        token_type=TokenType.ACCESS,
    )


@pytest.fixture
def admin_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="usr_test_admin",
        tenant_id="tenant_vgr_01",
        email="admin@vgr.vn",
        display_name="Nguyễn Quản Trị",
        role="ADMINISTRATOR",
        token_type=TokenType.ACCESS,
    )
