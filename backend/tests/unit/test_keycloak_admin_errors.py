"""Keycloak admin errors map to messages an operator can act on (PR #31 review #5)."""

from __future__ import annotations

import pytest
from keycloak.exceptions import KeycloakAuthenticationError, KeycloakError

from contract_intelligence.infrastructure.keycloak_admin import _translate_keycloak_error


def test_401_points_at_the_client_secret_not_at_roles() -> None:
    # A wrong or rotated client secret fails the service-account login with 401.
    error = _translate_keycloak_error(
        KeycloakAuthenticationError(error_message="invalid_client", response_code=401)
    )
    assert error.code == "keycloak_unauthenticated"
    assert "KEYCLOAK_ADMIN_CLIENT_SECRET" in error.message
    assert "manage-users" not in error.message


def test_403_points_at_the_missing_realm_management_role() -> None:
    error = _translate_keycloak_error(KeycloakError(error_message="forbidden", response_code=403))
    assert error.code == "keycloak_forbidden"
    assert "manage-users" in error.message


@pytest.mark.parametrize("code", [401, 403])
def test_both_surface_as_bad_gateway_with_the_keycloak_code(code: int) -> None:
    error = _translate_keycloak_error(KeycloakError(error_message="x", response_code=code))
    assert error.status_code == 502
    assert error.details == {"response_code": code}
