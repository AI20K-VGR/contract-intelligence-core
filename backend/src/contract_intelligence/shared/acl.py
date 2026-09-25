"""Shared dossier ACL decision seam for reads and review mutations."""

from __future__ import annotations

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


_ALLOWED_ROLES: dict[AclAction, frozenset[str]] = {
    AclAction.QUERY: frozenset({"OPERATOR", "REVIEWER", "ADMINISTRATOR"}),
    AclAction.SEARCH: frozenset({"OPERATOR", "REVIEWER", "ADMINISTRATOR"}),
    AclAction.CITATION_READ: frozenset({"OPERATOR", "REVIEWER", "ADMINISTRATOR"}),
    AclAction.FINDING_READ: frozenset({"OPERATOR", "REVIEWER", "ADMINISTRATOR"}),
    AclAction.REVIEW_READ: frozenset({"REVIEWER", "ADMINISTRATOR"}),
    AclAction.REVIEW_MUTATE: frozenset({"REVIEWER", "ADMINISTRATOR"}),
    AclAction.APPROVE: frozenset({"ADMINISTRATOR"}),
}


def dossier_access_decision(
    *,
    action: AclAction,
    principal: AuthenticatedUser,
    dossier_id: str,
    dossier_tenant_id: str,
    metadata: dict[str, Any] | None,
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

    if meta.get("access_scope") == "mine":
        return False
    shared_with = meta.get("shared_with")
    if not isinstance(shared_with, list):
        return False
    return any(
        isinstance(grant, dict)
        and grant.get("id") == principal.user_id
        and _grant_allows(grant, action, principal.role)
        for grant in shared_with
    )


def _grant_allows(grant: dict[str, Any], action: AclAction, role: str) -> bool:
    """Honor optional per-grant role/action restrictions without weakening ACL."""
    roles = grant.get("roles")
    if isinstance(roles, list) and roles and role not in roles:
        return False
    actions = grant.get("actions")
    return not (isinstance(actions, list) and actions and action.value not in actions)


__all__ = ["AclAction", "dossier_access_decision"]
