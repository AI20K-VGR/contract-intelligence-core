"""Log in like the browser does: Authorization Code + PKCE against Keycloak.

The frontend client has Direct Access Grants disabled, so the password grant
is not an option. The script fetches the login form, posts the credentials,
catches the redirect carrying `code`, and exchanges it for tokens.

Keycloak marks its login cookies `Secure`, and httpx will not send a Secure
cookie over plain http, so the cookies are forwarded by hand.
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import re
import secrets
import urllib.parse
from dataclasses import dataclass

import httpx

from .config import CONFIG, Config


@dataclass(frozen=True)
class Session:
    role: str
    access_token: str
    tenant_id: str
    claims: dict

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}", "X-Tenant-Id": self.tenant_id}


class LoginError(RuntimeError):
    pass


def decode_claims(token: str) -> dict:
    """Read JWT claims without verifying; the backend is what verifies."""
    segment = token.split(".")[1]
    segment += "=" * (-len(segment) % 4)
    return json.loads(base64.urlsafe_b64decode(segment))


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode()).digest()
    return verifier, base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def login(username: str, password: str, *, role: str = "", cfg: Config = CONFIG) -> Session:
    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(8)
    with httpx.Client(follow_redirects=False, timeout=20) as client:
        page = client.get(
            f"{cfg.oidc_base}/auth",
            params={
                "client_id": cfg.client_id,
                "redirect_uri": cfg.redirect_uri,
                "response_type": "code",
                "scope": "openid",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "state": state,
            },
        )
        match = re.search(r'id="kc-form-login"[^>]*action="([^"]+)"', page.text) or re.search(
            r'action="([^"]+)"', page.text
        )
        if page.status_code != 200 or not match:
            raise LoginError(f"Keycloak login page unavailable (HTTP {page.status_code})")
        cookie = "; ".join(f"{k}={v}" for k, v in page.cookies.items())
        posted = client.post(
            html.unescape(match.group(1)),
            data={"username": username, "password": password},
            headers={"Cookie": cookie},
        )
        location = posted.headers.get("location", "")
        query = urllib.parse.parse_qs(urllib.parse.urlparse(location).query)
        if posted.status_code != 302 or "code" not in query:
            raise LoginError(f"login rejected for {username} (HTTP {posted.status_code})")
        if query.get("state") != [state]:
            raise LoginError("state mismatch on the login redirect")
        tokens = client.post(
            f"{cfg.oidc_base}/token",
            data={
                "grant_type": "authorization_code",
                "client_id": cfg.client_id,
                "code": query["code"][0],
                "redirect_uri": cfg.redirect_uri,
                "code_verifier": verifier,
            },
        )
    if tokens.status_code != 200:
        raise LoginError(f"token exchange failed (HTTP {tokens.status_code})")
    access = tokens.json()["access_token"]
    claims = decode_claims(access)
    return Session(role=role, access_token=access, tenant_id=claims.get("tenant_id", ""), claims=claims)


def login_as(role: str, cfg: Config = CONFIG) -> Session:
    user = cfg.users[role]
    return login(user.username, user.password, role=role, cfg=cfg)
