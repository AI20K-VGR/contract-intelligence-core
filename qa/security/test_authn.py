"""Authentication: the backend accepts only Keycloak-signed RS256 tokens.

Every forged token below is built locally; none of them may get past the
JWT check (OWASP API2:2023 Broken Authentication).
"""

from __future__ import annotations

import base64
import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

pytestmark = pytest.mark.security

PROTECTED = "/api/v1/auth/me"


@pytest.fixture(scope="module")
def attacker_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _kid(token: str) -> str | None:
    return jwt.get_unverified_header(token).get("kid")


def _b64(obj: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()


def test_missing_token_rejected(api, admin):
    """No Authorization header -> 401 on a tenant-scoped route."""
    r = api.get("/api/v1/dossiers", headers={"X-Tenant-Id": admin.tenant_id})
    assert r.status_code == 401


@pytest.mark.parametrize(
    "value",
    ["Bearer", "Bearer abc.def.ghi", "Bearer a.b", "Basic YWRtaW46YWRtaW4=", "Token xyz"],
)
def test_malformed_authorization_rejected(api, value):
    """Malformed or non-Bearer Authorization headers -> 401."""
    r = api.get(PROTECTED, headers={"Authorization": value})
    assert r.status_code == 401


def test_alg_none_rejected(api, admin):
    """Unsigned token (alg=none) carrying admin claims -> 401."""
    token = jwt.encode(admin.claims, key=None, algorithm="none")
    assert api.get(PROTECTED, headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_hs256_algorithm_confusion_rejected(api, admin):
    """HS256 token reusing the real kid (algorithm confusion) -> 401."""
    token = jwt.encode(
        admin.claims, "x" * 32, algorithm="HS256", headers={"kid": _kid(admin.access_token)}
    )
    assert api.get(PROTECTED, headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_token_signed_by_foreign_key_rejected(api, admin, attacker_key):
    """RS256 token signed by an attacker key with the realm's kid -> 401."""
    token = jwt.encode(
        admin.claims, attacker_key, algorithm="RS256", headers={"kid": _kid(admin.access_token)}
    )
    assert api.get(PROTECTED, headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_privilege_escalation_by_editing_claims_rejected(api, reviewer):
    """Reviewer token with realm_access edited to ADMINISTRATOR (signature kept) -> 401."""
    header, payload, signature = reviewer.access_token.split(".")
    claims = dict(reviewer.claims)
    claims["realm_access"] = {"roles": ["ADMINISTRATOR"]}
    forged = f"{header}.{_b64(claims)}.{signature}"
    r = api.get("/api/v1/users", headers={"Authorization": f"Bearer {forged}", "X-Tenant-Id": reviewer.tenant_id})
    assert r.status_code == 401


def test_tenant_claim_swap_rejected(api, admin):
    """Valid signature but tenant_id claim rewritten -> 401."""
    header, _payload, signature = admin.access_token.split(".")
    claims = dict(admin.claims, tenant_id="tenant_attacker")
    forged = f"{header}.{_b64(claims)}.{signature}"
    r = api.get(
        "/api/v1/dossiers",
        headers={"Authorization": f"Bearer {forged}", "X-Tenant-Id": "tenant_attacker"},
    )
    assert r.status_code == 401


def test_wrong_issuer_rejected(api, admin, attacker_key):
    """Token from another issuer -> 401."""
    claims = dict(admin.claims, iss="https://evil.example/realms/contract-intelligence")
    token = jwt.encode(claims, attacker_key, algorithm="RS256", headers={"kid": _kid(admin.access_token)})
    assert api.get(PROTECTED, headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_expired_token_rejected(api, admin, attacker_key):
    """Token whose exp is in the past -> 401."""
    now = int(time.time())
    claims = dict(admin.claims, iat=now - 7200, exp=now - 3600)
    token = jwt.encode(claims, attacker_key, algorithm="RS256", headers={"kid": _kid(admin.access_token)})
    assert api.get(PROTECTED, headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_access_token_lifetime_is_short(admin):
    """Keycloak access tokens live 15 minutes or less."""
    assert admin.claims["exp"] - admin.claims["iat"] <= 15 * 60


def test_token_audience_is_backend(admin, cfg):
    """Access tokens are issued for the backend audience by the realm issuer."""
    aud = admin.claims.get("aud")
    audiences = aud if isinstance(aud, list) else [aud]
    assert "contract-intel-backend" in audiences
    assert admin.claims["iss"].endswith(f"/realms/{cfg.realm}")


def test_wrong_password_rejected(cfg):
    """Keycloak refuses a wrong password (no code issued)."""
    from lib.auth import LoginError, login

    with pytest.raises(LoginError):
        login(cfg.users["REVIEWER"].username, "definitely-wrong-password")
