from dataclasses import dataclass
from secrets import compare_digest

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.domain import require

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Actor:
    id: str
    role: str


def authenticate(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> Actor:
    require(bool(settings.accounts), "ACCOUNTS_NOT_CONFIGURED", 503)
    require(credentials is not None, "AUTHENTICATION_REQUIRED", 401)
    for token, identity in settings.accounts.items():
        if compare_digest(credentials.credentials, token):
            return Actor(identity["id"], identity["role"])
    require(False, "INVALID_CREDENTIALS", 401)


def allowed(actor: Actor, *roles: str):
    require(actor.role in (*roles, "admin"), "ROLE_FORBIDDEN", 403)
