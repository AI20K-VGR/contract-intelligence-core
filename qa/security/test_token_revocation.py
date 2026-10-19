"""Token lifecycle: disabled users, and the stateless-JWT revocation window.

The backend verifies RS256 access tokens statelessly. This suite documents what
that means: a disabled user cannot get a NEW token, but an already-issued access
token keeps working until it expires unless the backend checks a denylist /
user-active flag per request. Local only (provisions a Keycloak user).
"""

from __future__ import annotations

import time

import pytest

from lib.auth import LoginError, login

pytestmark = pytest.mark.security


@pytest.fixture
def disposable_user(cfg):
    if cfg.is_prod:
        pytest.skip("provisions a Keycloak user; local only")
    from lib.kc_admin import KcAdmin, KcAdminError

    try:
        kc = KcAdmin(cfg)
        user = kc.create_user(f"qa-revoke-{int(time.time())}@ci.local", "Qa-Revoke-2026", "tenant_vgr_01", "OPERATOR")
    except KcAdminError as exc:
        pytest.skip(f"Keycloak admin unavailable: {exc}")
    yield kc, user
    kc.cleanup()


def test_disabled_user_cannot_get_new_token(disposable_user, cfg):
    """After an admin disables the account, the user can no longer log in."""
    kc, user = disposable_user
    assert login(user.username, user.password, cfg=cfg).access_token  # works while enabled
    kc.set_enabled(user.id, False)
    with pytest.raises(LoginError):
        login(user.username, user.password, cfg=cfg)


def test_existing_token_after_disable(disposable_user, api, cfg):
    """Record whether an already-issued token keeps working after the user is disabled.

    Pass = backend rejects it immediately (denylist/active check). If it still
    works, this xfails as FINDING AUTH-01: revocation waits up to the token TTL
    (<=15 min); mitigate with short TTL + back-channel logout or a denylist.
    """
    kc, user = disposable_user
    session = login(user.username, user.password, cfg=cfg)
    assert api.get("/api/v1/auth/me", headers=session.headers).status_code == 200
    kc.set_enabled(user.id, False)
    time.sleep(2)
    after = api.get("/api/v1/auth/me", headers=session.headers)
    if after.status_code == 200:
        pytest.xfail("FINDING AUTH-01: access token still valid after the user was disabled (stateless JWT, no denylist)")
    assert after.status_code == 401
