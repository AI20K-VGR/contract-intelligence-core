from dataclasses import dataclass

from app.domain import require


@dataclass(frozen=True)
class Actor:
    id: str
    role: str


# No login: this API is a local, single-operator tool, so every request acts as a
# fixed admin actor. Kept as a FastAPI dependency (rather than a module constant)
# so the audit trail, idempotency keys and role checks below don't need to change
# if per-user authentication is reintroduced later.
def authenticate() -> Actor:
    return Actor("local", "admin")


def allowed(actor: Actor, *roles: str):
    require(actor.role in (*roles, "admin"), "ROLE_FORBIDDEN", 403)
