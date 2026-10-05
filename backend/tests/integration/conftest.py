"""Pytest fixtures for tests/integration/ — import Keycloak fixtures from root conftest."""

import pytest
from tests.conftest import (  # noqa: F401
    AuthenticationError,
    admin_user,
    cached_keycloak_jwks,
    keycloak_test_settings,
    make_keycloak_token,
    mock_keycloak_settings,
    operator_user,
    reviewer_user,
    rsa_keypair,
    sample_document_id,
    sample_dossier_id,
)

__all__ = [
    "AuthenticationError",
    "admin_user",
    "cached_keycloak_jwks",
    "keycloak_test_settings",
    "make_keycloak_token",
    "mock_keycloak_settings",
    "operator_user",
    "reviewer_user",
    "rsa_keypair",
    "sample_dossier_id",
    "sample_document_id",
]


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Tag tests that spawn the local AI2 HTTP service (``ai_http``).

    They need ``AI2_FRAME_TEST_DATABASE_URL`` and the Windows-only
    ``ai-service/.venv-ai2-frame`` interpreter (see docs/ai2 runbooks), so CI
    deselects them with ``-m "not ai2_local_e2e"``; run locally they still fail
    loudly instead of skipping.
    """
    for item in items:
        if "ai_http" in getattr(item, "fixturenames", ()):
            item.add_marker(pytest.mark.ai2_local_e2e)
