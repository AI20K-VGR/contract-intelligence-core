"""keycloak_configure.configure_frontend: localhost redirects only when kept on purpose."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
from typing import Any

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "keycloak_configure.py"
_spec = importlib.util.spec_from_file_location("keycloak_configure", _SCRIPT)
assert _spec and _spec.loader
kc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(kc)

ONLINE = "https://contract-intelligence.tech"
LOCAL = "http://localhost:5173"


@pytest.fixture
def keycloak(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """The frontend client as realm-export.json leaves it, and what gets PUT back."""
    state: dict[str, Any] = {
        "client": {
            "id": "c1",
            "redirectUris": [f"{LOCAL}/", "http://127.0.0.1:5173/auth/callback", f"{ONLINE}/"],
            "webOrigins": [LOCAL, "+"],
            "attributes": {"post.logout.redirect.uris": f"{LOCAL}/*##{ONLINE}/*"},
        },
        "sent": None,
    }
    monkeypatch.setattr(kc, "_client", lambda _token, _cid: copy.deepcopy(state["client"]))

    def _request(_method: str, _path: str, _token: Any = None, body: Any = None) -> None:
        state["sent"] = body
        state["client"] = copy.deepcopy(body)

    monkeypatch.setattr(kc, "_request", _request)
    return state


def _all_urls(client: dict[str, Any]) -> list[str]:
    logout = client["attributes"]["post.logout.redirect.uris"].split("##")
    return [*client["redirectUris"], *client["webOrigins"], *logout]


def test_localhost_is_dropped_by_default(
    keycloak: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("KEYCLOAK_KEEP_LOCAL_REDIRECTS", raising=False)

    kc.configure_frontend("token", [ONLINE, LOCAL])

    urls = _all_urls(keycloak["sent"])
    assert not [u for u in urls if "localhost" in u or "127.0.0.1" in u]
    assert f"{ONLINE}/auth/callback" in keycloak["sent"]["redirectUris"]
    assert "+" in keycloak["sent"]["webOrigins"]


def test_localhost_is_kept_when_asked(
    keycloak: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KEYCLOAK_KEEP_LOCAL_REDIRECTS", "true")

    kc.configure_frontend("token", [ONLINE, LOCAL])

    assert f"{LOCAL}/auth/callback" in keycloak["sent"]["redirectUris"]
    assert LOCAL in keycloak["sent"]["webOrigins"]
    assert f"{LOCAL}/*" in keycloak["sent"]["attributes"]["post.logout.redirect.uris"]


def test_running_twice_changes_nothing(
    keycloak: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("KEYCLOAK_KEEP_LOCAL_REDIRECTS", raising=False)

    kc.configure_frontend("token", [ONLINE, LOCAL])
    first = copy.deepcopy(keycloak["sent"])
    kc.configure_frontend("token", [ONLINE, LOCAL])

    assert keycloak["sent"] == first


def test_backchannel_logout_points_at_the_backend(
    keycloak: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("KEYCLOAK_BACKCHANNEL_LOGOUT_URL", raising=False)
    keycloak["client"]["frontchannelLogout"] = True

    kc.configure_frontend("token", [ONLINE])

    sent = keycloak["sent"]
    attributes = sent["attributes"]
    assert attributes["backchannel.logout.url"] == (
        "http://backend:8000/api/v1/auth/backchannel-logout"
    )
    assert attributes["backchannel.logout.session.required"] == "true"
    assert attributes["backchannel.logout.revoke.offline.tokens"] == "false"
    # A front-channel client would skip the back-channel call on browser logout.
    assert sent["frontchannelLogout"] is False
    # Existing attributes survive.
    assert f"{ONLINE}/*" in attributes["post.logout.redirect.uris"]


def test_backchannel_logout_url_can_be_overridden(
    keycloak: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KEYCLOAK_BACKCHANNEL_LOGOUT_URL", "http://api.internal:9000/logout")

    kc.configure_frontend("token", [ONLINE])

    assert keycloak["sent"]["attributes"]["backchannel.logout.url"] == (
        "http://api.internal:9000/logout"
    )


def test_refresh_token_rotation_is_turned_on_and_other_realm_settings_kept(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    realm: dict[str, Any] = {
        "realm": "contract-intelligence",
        "revokeRefreshToken": False,
        "accessTokenLifespan": 900,
        "bruteForceProtected": True,
    }
    sent: list[tuple[str, str, Any]] = []

    def _request(method: str, path: str, _token: Any = None, body: Any = None) -> Any:
        sent.append((method, path, copy.deepcopy(body)))
        return copy.deepcopy(realm) if method == "GET" else None

    monkeypatch.setattr(kc, "_request", _request)

    kc.enable_refresh_token_rotation("token")

    method, path, body = sent[-1]
    assert (method, path) == ("PUT", "/admin/realms/contract-intelligence")
    assert body["revokeRefreshToken"] is True
    assert body["refreshTokenMaxReuse"] == 0
    assert body["accessTokenLifespan"] == 900 and body["bruteForceProtected"] is True
