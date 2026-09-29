"""Shared dossier ACL decision seam for reads and review mutations.

A share grant (``dossier.metadata.shared_with[]``) may carry:

- ``permission``: ``"read"`` (view only) or ``"edit"`` (also review, run, change
  the dossier). A grant without it predates the field and keeps full access
  (``"edit"``), so existing shares keep working.
- ``expires_at``: ISO-8601 instant; at or past it the grant gives nothing.
- ``status``: ``"disabled"`` revokes the grant.
- ``roles`` / ``actions``: optional extra restrictions.

Changing who can access a dossier, or deleting it, is never granted by a
share: only the owner (or an ADMINISTRATOR) may do it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from contract_intelligence.shared.auth.schemas import AuthenticatedUser


class AclAction(StrEnum):
    """Operations that must use the same tenant/share/RBAC decision."""

    QUERY = "query"
    SEARCH = "search"
    CITATION_READ = "citation_read"
    FINDING_READ = "finding_read"
    REVIEW_READ = "review_read"
    REVIEW_MUTATE = "review_mutate"
    APPROVE = "approve"
    DOSSIER_EDIT = "dossier_edit"
    DOSSIER_MANAGE = "dossier_manage"


_ALLOWED_ROLES: dict[AclAction, frozenset[str]] = {
    AclAction.QUERY: frozenset({"OPERATOR", "REVIEWER", "ADMINISTRATOR"}),
    AclAction.SEARCH: frozenset({"OPERATOR", "REVIEWER", "ADMINISTRATOR"}),
    AclAction.CITATION_READ: frozenset({"OPERATOR", "REVIEWER", "ADMINISTRATOR"}),
    AclAction.FINDING_READ: frozenset({"OPERATOR", "REVIEWER", "ADMINISTRATOR"}),
    AclAction.REVIEW_READ: frozenset({"REVIEWER", "ADMINISTRATOR"}),
    AclAction.REVIEW_MUTATE: frozenset({"REVIEWER", "ADMINISTRATOR"}),
    AclAction.APPROVE: frozenset({"ADMINISTRATOR"}),
    AclAction.DOSSIER_EDIT: frozenset({"OPERATOR", "ADMINISTRATOR"}),
    AclAction.DOSSIER_MANAGE: frozenset({"OPERATOR", "ADMINISTRATOR"}),
}

# Actions a "read" grant does not cover.
_EDIT_ACTIONS = frozenset({AclAction.REVIEW_MUTATE, AclAction.APPROVE, AclAction.DOSSIER_EDIT})

SHARE_PERMISSIONS = ("read", "edit")


def dossier_access_decision(
    *,
    action: AclAction,
    principal: AuthenticatedUser,
    dossier_id: str,
    dossier_tenant_id: str,
    metadata: dict[str, Any] | None,
    now: datetime | None = None,
) -> bool:
    """Return one fail-closed ACL decision for a dossier operation.

    Tenant membership, role, and actor-specific ownership/sharing are all
    required.  A same-tenant principal with no owner/share grant is denied.
    ``dossier_id`` is part of the seam so callers cannot silently reuse a
    decision for a different resource.
    """
    if not dossier_id or principal.tenant_id != dossier_tenant_id:
        return False
    if principal.role not in _ALLOWED_ROLES[action]:
        return False

    meta = metadata if isinstance(metadata, dict) else {}
    owner_id = meta.get("created_by")
    if isinstance(owner_id, str) and owner_id and owner_id == principal.user_id:
        return True

    if action is AclAction.DOSSIER_MANAGE:
        return principal.role == "ADMINISTRATOR"
    if meta.get("access_scope") == "mine":
        return False
    shared_with = meta.get("shared_with")
    if not isinstance(shared_with, list):
        return False
    email = (principal.email or "").strip().lower()
    moment = now or datetime.now(tz=UTC)
    return any(
        isinstance(grant, dict)
        and (
            grant.get("id") == principal.user_id
            or (email and str(grant.get("email") or "").strip().lower() == email)
        )
        and grant_is_live(grant, moment)
        and _grant_allows(grant, action, principal.role)
        for grant in shared_with
    )


def grant_is_live(grant: dict[str, Any], now: datetime) -> bool:
    """Not disabled and not expired. An unreadable ``expires_at`` counts as expired."""
    if grant.get("status") == "disabled":
        return False
    expires_at = grant.get("expires_at")
    if expires_at in (None, ""):
        return True
    try:
        moment = datetime.fromisoformat(str(expires_at))
    except ValueError:
        return False
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return now < moment


def grant_permission(grant: dict[str, Any]) -> str:
    """``read`` or ``edit``; a grant from before the field existed is ``edit``."""
    permission = grant.get("permission")
    return permission if permission in SHARE_PERMISSIONS else "edit"


def _grant_allows(grant: dict[str, Any], action: AclAction, role: str) -> bool:
    """Honor per-grant permission and optional role/action restrictions."""
    if action in _EDIT_ACTIONS and grant_permission(grant) != "edit":
        return False
    roles = grant.get("roles")
    if isinstance(roles, list) and roles and role not in roles:
        return False
    actions = grant.get("actions")
    return not (isinstance(actions, list) and actions and action.value not in actions)


__all__ = [
    "SHARE_PERMISSIONS",
    "AclAction",
    "dossier_access_decision",
    "grant_is_live",
    "grant_permission",
]
