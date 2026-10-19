"""Make the imported realm safe and usable online. Idempotent; stdlib only.

Runs inside the running backend container on ci-network (deploy/deploy.sh does it):

    docker compose ... exec -T -e KEYCLOAK_ADMIN_PASSWORD=... \
        backend python - < deploy/keycloak_configure.py

- realm frontend URL: KEYCLOAK_PUBLIC_URL replaces the http://localhost:8080 of
  realm-export.json, which overrides --hostname and makes Keycloak answer
  "HTTPS required" to every caller from the Internet;
- frontend client: add FRONTEND_ORIGINS to redirect URIs, web origins and
  post-logout redirects, and drop the localhost / 127.0.0.1 ones realm-export.json
  brings for local work (a token must not be sent to a page on the user's own
  machine). KEYCLOAK_KEEP_LOCAL_REDIRECTS=true keeps them. Back-channel logout
  points at the backend (KEYCLOAK_BACKCHANNEL_LOGOUT_URL, default
  http://backend:8000/api/v1/auth/backchannel-logout). No refresh tokens: the
  SPA renews through silent SSO;
- backend client: replace the repo's dev secret with BACKEND_KEYCLOAK_ADMIN_SECRET;
- seeded demo users: replace the passwords committed in realm-export.json with
  DEMO_*_PASSWORD from deploy/.env.prod;
- realm SMTP: point at SMTP_* when a real mail server is configured;
- brute-force protection on: the login page is public (off in the dev realm).
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

BASE = os.environ.get("KEYCLOAK_INTERNAL_URL", "http://keycloak:8080").rstrip("/")
REALM = os.environ.get("KEYCLOAK_REALM", "contract-intelligence")
FRONTEND_CLIENT = "contract-intel-frontend"
BACKEND_CLIENT = "contract-intel-backend"
DEFAULT_BACKCHANNEL_LOGOUT_URL = "http://backend:8000/api/v1/auth/backchannel-logout"
DEMO_USERS = {
    "admin@ci.local": "DEMO_ADMIN_PASSWORD",
    "reviewer@ci.local": "DEMO_REVIEWER_PASSWORD",
    "operator@ci.local": "DEMO_OPERATOR_PASSWORD",
}


def _env(name: str, *, required: bool = True) -> str:
    value = os.environ.get(name, "").strip()
    if required and not value:
        sys.exit(f"[keycloak] missing {name}")
    return value


def _request(method: str, path: str, token: str | None = None, body: Any = None) -> Any:
    data = None
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if isinstance(body, dict | list):
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    elif isinstance(body, str):
        data = body.encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = urllib.request.Request(f"{BASE}{path}", data=data, method=method, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read()
    return json.loads(raw) if raw else None


def _admin_token() -> str:
    form = urllib.parse.urlencode(
        {
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": os.environ.get("KEYCLOAK_ADMIN_USER", "admin"),
            "password": _env("KEYCLOAK_ADMIN_PASSWORD"),
        }
    )
    deadline = time.monotonic() + 300
    while True:
        try:
            payload = _request("POST", "/realms/master/protocol/openid-connect/token", body=form)
            token = payload.get("access_token") if isinstance(payload, dict) else None
            if not token:
                sys.exit("[keycloak] admin token response did not contain access_token")
            return str(token)
        except urllib.error.HTTPError as exc:
            if 400 <= exc.code < 500 and exc.code != 429:
                sys.exit(
                    f"[keycloak] admin token request rejected ({exc.code}); "
                    "check Keycloak URL and credentials"
                )
            _wait_for_keycloak_retry(deadline, exc)
        except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
            _wait_for_keycloak_retry(deadline, exc)


def _wait_for_keycloak_retry(deadline: float, error: BaseException) -> None:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        sys.exit(
            f"[keycloak] not ready after 300s ({type(error).__name__}); "
            "check service health and internal URL"
        )
    if isinstance(error, urllib.error.HTTPError):
        print(f"[keycloak] server returned HTTP {error.code}; retrying readiness", flush=True)
    else:
        print("[keycloak] waiting for Keycloak readiness", flush=True)
    time.sleep(min(5, remaining))


def _client(token: str, client_id: str) -> dict[str, Any]:
    found = _request(
        "GET",
        f"/admin/realms/{REALM}/clients?clientId={urllib.parse.quote(client_id)}",
        token,
    )
    if not found:
        sys.exit(f"[keycloak] client {client_id} not found in realm {REALM}")
    return dict(found[0])


def _merge(existing: list[str] | None, extra: list[str]) -> list[str]:
    merged = list(existing or [])
    for item in extra:
        if item not in merged:
            merged.append(item)
    return merged


_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1"})


def _is_local(url: str) -> bool:
    return (urllib.parse.urlsplit(url).hostname or "") in _LOCAL_HOSTS


def _online(urls: list[str] | None, keep_local: bool) -> list[str]:
    return [u for u in urls or [] if keep_local or not _is_local(u)]


def configure_frontend(token: str, origins: list[str]) -> None:
    client = _client(token, FRONTEND_CLIENT)
    keep_local = _env("KEYCLOAK_KEEP_LOCAL_REDIRECTS", required=False).lower() == "true"
    # FRONTEND_ORIGINS may list localhost for CORS (team frontend against this
    # API); Keycloak gets it only when kept on purpose.
    origins = _online(origins, keep_local)
    client["redirectUris"] = _merge(
        _online(client.get("redirectUris"), keep_local),
        [f"{o}/" for o in origins]
        + [f"{o}/auth/callback" for o in origins]
        + [f"{o}/auth/silent-callback" for o in origins],
    )
    client["webOrigins"] = _merge(_online(client.get("webOrigins"), keep_local), origins)
    attributes = dict(client.get("attributes") or {})
    logout = [u for u in attributes.get("post.logout.redirect.uris", "").split("##") if u]
    attributes["post.logout.redirect.uris"] = "##".join(
        _merge(_online(logout, keep_local), [f"{o}/*" for o in origins])
    )
    attributes.update(_backchannel_logout_attributes())
    # No refresh token for the SPA (#130, #133): it renews through a prompt=none
    # iframe on Keycloak's HttpOnly SSO cookie, so a refresh token would only be
    # one more long-lived credential sitting in page memory for a script to take.
    attributes["use.refresh.tokens"] = "false"
    client["attributes"] = attributes
    # Keycloak skips the back-channel call for a client marked front-channel
    # on a browser logout; this client has no front-channel URL anyway.
    client["frontchannelLogout"] = False
    _request("PUT", f"/admin/realms/{REALM}/clients/{client['id']}", token, client)
    local = "kept" if keep_local else "removed"
    print(f"[keycloak] frontend client allows {', '.join(origins)}; localhost redirects {local}")
    print(f"[keycloak] back-channel logout: {attributes['backchannel.logout.url']}")
    print("[keycloak] frontend client: no refresh tokens (renews through silent SSO)")


def _backchannel_logout_attributes() -> dict[str, str]:
    """Keycloak POSTs a logout token here when a session ends, so the API stops
    accepting that session's access tokens at once instead of up to 15 minutes later.
    The backend is reached inside ci-network; Caddy refuses the path from outside.
    """
    url = _env("KEYCLOAK_BACKCHANNEL_LOGOUT_URL", required=False) or DEFAULT_BACKCHANNEL_LOGOUT_URL
    return {
        "backchannel.logout.url": url,
        "backchannel.logout.session.required": "true",
        "backchannel.logout.revoke.offline.tokens": "false",
    }


def configure_frontend_url(token: str, public_url: str) -> None:
    realm = _request("GET", f"/admin/realms/{REALM}", token)
    attributes = realm.setdefault("attributes", {})
    attributes["frontendUrl"] = public_url
    _request("PUT", f"/admin/realms/{REALM}", token, realm)
    print(f"[keycloak] realm frontend URL: {public_url}")


def configure_backend_secret(token: str, secret: str) -> None:
    client = _client(token, BACKEND_CLIENT)
    client["secret"] = secret
    _request("PUT", f"/admin/realms/{REALM}/clients/{client['id']}", token, client)
    print("[keycloak] backend client secret rotated")


def reset_demo_passwords(token: str) -> None:
    for username, variable in DEMO_USERS.items():
        password = _env(variable)
        users = _request(
            "GET",
            f"/admin/realms/{REALM}/users?exact=true&username={urllib.parse.quote(username)}",
            token,
        )
        if not users:
            print(f"[keycloak] demo user {username} absent, skipped")
            continue
        _request(
            "PUT",
            f"/admin/realms/{REALM}/users/{users[0]['id']}/reset-password",
            token,
            {"type": "password", "value": password, "temporary": False},
        )
        print(f"[keycloak] demo user {username}: password replaced")


def configure_smtp(token: str) -> None:
    host = _env("SMTP_HOST", required=False)
    if not host or host == "mailpit":
        print("[keycloak] SMTP: keeping mailpit (no real mail server configured)")
        return
    realm = _request("GET", f"/admin/realms/{REALM}", token)
    smtp: dict[str, str] = {
        "host": host,
        "port": _env("SMTP_PORT", required=False) or "587",
        "from": _env("SMTP_FROM"),
        "fromDisplayName": "Lexis Contract Intelligence",
        "starttls": "true" if _env("SMTP_STARTTLS", required=False) == "true" else "false",
        "ssl": "false",
        "auth": "false",
    }
    user = _env("SMTP_USER", required=False)
    if user:
        smtp.update({"auth": "true", "user": user, "password": _env("SMTP_PASSWORD")})
    realm["smtpServer"] = smtp
    _request("PUT", f"/admin/realms/{REALM}", token, realm)
    print(f"[keycloak] SMTP: {host}")


def enable_brute_force_protection(token: str) -> None:
    realm = _request("GET", f"/admin/realms/{REALM}", token)
    realm.update(
        {
            "bruteForceProtected": True,
            "failureFactor": 5,  # lock after 5 wrong passwords
            "waitIncrementSeconds": 60,
            "maxFailureWaitSeconds": 900,
            "maxDeltaTimeSeconds": 43200,
            "permanentLockout": False,
        }
    )
    _request("PUT", f"/admin/realms/{REALM}", token, realm)
    print("[keycloak] brute-force protection on (5 failures, up to 15 min lockout)")


def main() -> None:
    origins = [o.strip().rstrip("/") for o in _env("FRONTEND_ORIGINS").split(",") if o.strip()]
    token = _admin_token()
    configure_frontend_url(token, _env("KEYCLOAK_PUBLIC_URL").rstrip("/"))
    configure_frontend(token, origins)
    configure_backend_secret(token, _env("BACKEND_KEYCLOAK_ADMIN_SECRET"))
    reset_demo_passwords(token)
    configure_smtp(token)
    enable_brute_force_protection(token)
    print("[keycloak] done")


if __name__ == "__main__":
    main()
