"""Create and delete throwaway Keycloak users for local isolation tests.

Local only. Uses the master-realm admin account (admin/admin on the dev stack,
override with QA_KC_ADMIN_USER / QA_KC_ADMIN_PASSWORD). Users get a `tenant_id`
attribute (the backend reads it as the tenant claim via a protocol mapper) and a
realm role, so a brand-new user is auto-provisioned on its first API call.

Creating a user here does NOT send email (unlike POST /api/v1/users), so it is
safe against the real Gmail SMTP the local backend is wired to.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

from .config import CONFIG, Config


class KcAdminError(RuntimeError):
    pass


@dataclass
class KcUser:
    id: str
    username: str
    password: str
    tenant_id: str
    role: str


def _token(cfg: Config) -> str:
    user = os.getenv("QA_KC_ADMIN_USER", "admin")
    password = os.getenv("QA_KC_ADMIN_PASSWORD", "admin")
    r = httpx.post(
        f"{cfg.keycloak_url}/realms/master/protocol/openid-connect/token",
        data={"grant_type": "password", "client_id": "admin-cli", "username": user, "password": password},
        timeout=15,
    )
    if r.status_code != 200:
        raise KcAdminError(f"Keycloak master admin login failed (HTTP {r.status_code})")
    return r.json()["access_token"]


class KcAdmin:
    def __init__(self, cfg: Config = CONFIG):
        self.cfg = cfg
        self.base = f"{cfg.keycloak_url}/admin/realms/{cfg.realm}"
        self._c = httpx.Client(headers={"Authorization": f"Bearer {_token(cfg)}"}, timeout=20)
        self._created: list[str] = []

    def _role(self, name: str) -> dict:
        r = self._c.get(f"{self.base}/roles/{name}")
        if r.status_code != 200:
            raise KcAdminError(f"realm role {name} not found")
        return r.json()

    def create_user(self, username: str, password: str, tenant_id: str, role: str) -> KcUser:
        r = self._c.post(
            f"{self.base}/users",
            json={
                "username": username,
                "email": username,
                "enabled": True,
                "emailVerified": True,
                "firstName": username.split("@")[0],
                "lastName": "QA",
                "attributes": {"tenant_id": [tenant_id]},
                "credentials": [{"type": "password", "value": password, "temporary": False}],
            },
        )
        if r.status_code not in (201, 409):
            raise KcAdminError(f"create user {username} failed (HTTP {r.status_code}): {r.text[:200]}")
        found = self._c.get(f"{self.base}/users", params={"username": username, "exact": "true"}).json()
        if not found:
            raise KcAdminError(f"user {username} not found after create")
        uid = found[0]["id"]
        self._c.post(f"{self.base}/users/{uid}/role-mappings/realm", json=[self._role(role)])
        self._created.append(uid)
        return KcUser(id=uid, username=username, password=password, tenant_id=tenant_id, role=role)

    def set_enabled(self, user_id: str, enabled: bool) -> None:
        r = self._c.put(f"{self.base}/users/{user_id}", json={"enabled": enabled})
        if r.status_code not in (204, 200):
            raise KcAdminError(f"set_enabled({enabled}) failed (HTTP {r.status_code})")

    def delete_user(self, user_id: str) -> None:
        self._c.delete(f"{self.base}/users/{user_id}")

    def cleanup(self) -> None:
        for uid in self._created:
            self.delete_user(uid)
        self._created.clear()
        self._c.close()
