"""Make the imported realm safe and usable online. Idempotent; stdlib only.

Runs inside the running backend container on ci-network (deploy/deploy.sh does it):

    docker compose ... exec -T -e KEYCLOAK_ADMIN_PASSWORD=... \
        backend python - < deploy/keycloak_configure.py

- realm frontend URL: KEYCLOAK_PUBLIC_URL replaces the http://localhost:8080 of
  realm-export.json, which overrides --hostname and makes Keycloak answer
  "HTTPS required" to every caller from the Internet;
- frontend client: add FRONTEND_ORIGINS to redirect URIs, web origins and
  post-logout redirects (localhost:5173 stays for local frontend work);
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
            return str(
                _request("POST", "/realms/master/protocol/openid-connect/token", body=form)[
                    "access_token"
                ]
            )
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 401, 403):
                sys.exit(
                    f"[keycloak] admin login refused ({exc.code}): check KEYCLOAK_ADMIN_PASSWORD"
                )
            if time.monotonic() > deadline:
                sys.exit(f"[keycloak] not ready after 300s: {exc}")
            time.sleep(5)
        except (urllib.error.URLError, ConnectionError, KeyError) as exc:
            if time.monotonic() > deadline:
                sys.exit(f"[keycloak] not ready after 300s: {exc}")
            print("[keycloak] waiting for Keycloak...", flush=True)
            time.sleep(5)


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


def configure_frontend(token: str, origins: list[str]) -> None:
    client = _client(token, FRONTEND_CLIENT)
    client["redirectUris"] = _merge(
        client.get("redirectUris"),
        [f"{o}/" for o in origins]
        + [f"{o}/auth/callback" for o in origins]
        + [f"{o}/auth/silent-callback" for o in origins],
    )
    client["webOrigins"] = _merge(client.get("webOrigins"), origins)
    attributes = dict(client.get("attributes") or {})
    logout = [u for u in attributes.get("post.logout.redirect.uris", "").split("##") if u]
    attributes["post.logout.redirect.uris"] = "##".join(_merge(logout, [f"{o}/*" for o in origins]))
    client["attributes"] = attributes
    _request("PUT", f"/admin/realms/{REALM}/clients/{client['id']}", token, client)
    print(f"[keycloak] frontend client allows {', '.join(origins)}")


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
