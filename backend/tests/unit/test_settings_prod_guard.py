"""Staging/prod refuse the dev default and placeholder secrets (Gate 1 review, item 5)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from contract_intelligence.config.settings import Settings

REAL_SECRETS: dict[str, Any] = {
    "database_url": "postgresql+asyncpg://ci:Zq8v3LkP0w@backend-db:5432/contract_intelligence",
    "s3_secret_key": "m1n10-Root-9f2c",
    "minio_secret_key": "m1n10-Root-9f2c",
    "keycloak_admin_client_secret": "kc-admin-4be1d7",
    "keycloak_webhook_secret": "kc-hook-77a0e2",
    "ai2_service_hmac_secret": "ai2-hmac-1c93ab",
    "keycloak_webhook_verify_signature": True,
}

DEV_DEFAULTS: dict[str, Any] = {
    "database_url": "postgresql+asyncpg://ci:ci_secret_dev@localhost:5434/contract_intelligence",
    "s3_secret_key": "password123",
    "minio_secret_key": "password123",
    "keycloak_admin_client_secret": "backend_secret_dev",
    "keycloak_webhook_secret": "ci_webhook_shared_secret_dev",
    "ai2_service_hmac_secret": None,
}


def _settings(env: str, **overrides: Any) -> Settings:
    # Explicit kwargs win over OS env vars; _env_file=None ignores a local .env.
    return Settings(_env_file=None, env=env, **{**REAL_SECRETS, **overrides})  # type: ignore[call-arg]


@pytest.mark.parametrize("env", ["dev", "test"])
def test_dev_and_test_keep_the_local_defaults(env: str) -> None:
    settings = _settings(env, **DEV_DEFAULTS, keycloak_webhook_verify_signature=False)
    assert settings.s3_secret_key == "password123"


@pytest.mark.parametrize("env", ["staging", "prod"])
def test_real_secrets_start_in_staging_and_prod(env: str) -> None:
    assert _settings(env).env == env


@pytest.mark.parametrize("env", ["staging", "prod"])
def test_every_dev_default_is_named_in_the_error(env: str) -> None:
    with pytest.raises(ValidationError) as caught:
        _settings(env, **DEV_DEFAULTS)
    message = str(caught.value)
    for name in (
        "DATABASE_URL (password)",
        "S3_SECRET_KEY",
        "MINIO_SECRET_KEY",
        "KEYCLOAK_ADMIN_CLIENT_SECRET",
        "KEYCLOAK_WEBHOOK_SECRET",
        "AI2_SERVICE_HMAC_SECRET",
    ):
        assert name in message


def test_error_never_echoes_secret_values() -> None:
    with pytest.raises(ValidationError) as caught:
        _settings("prod", **DEV_DEFAULTS)
    message = str(caught.value)
    for value in ("password123", "backend_secret_dev", "ci_webhook_shared_secret_dev"):
        assert value not in message


@pytest.mark.parametrize(
    ("field", "value", "reported"),
    [
        ("s3_secret_key", "generate", "S3_SECRET_KEY"),
        ("minio_secret_key", "  ", "MINIO_SECRET_KEY"),
        ("keycloak_admin_client_secret", "CHANGEME", "KEYCLOAK_ADMIN_CLIENT_SECRET"),
        ("keycloak_webhook_secret", "prod_hook_dev", "KEYCLOAK_WEBHOOK_SECRET"),
        ("ai2_service_hmac_secret", "", "AI2_SERVICE_HMAC_SECRET"),
        (
            "database_url",
            "postgresql+asyncpg://ci@backend-db:5432/contract_intelligence",
            "DATABASE_URL (password)",
        ),
    ],
)
def test_one_placeholder_is_enough_to_refuse(field: str, value: str, reported: str) -> None:
    with pytest.raises(ValidationError, match=r"refuses dev default") as caught:
        _settings("prod", **{field: value})
    assert reported in str(caught.value)


def test_prod_requires_webhook_signature_verification() -> None:
    with pytest.raises(ValidationError, match="KEYCLOAK_WEBHOOK_VERIFY_SIGNATURE"):
        _settings("prod", keycloak_webhook_verify_signature=False)
