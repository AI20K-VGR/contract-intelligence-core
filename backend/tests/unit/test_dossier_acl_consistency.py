"""Phase 1 shared ACL decision matrix."""

from __future__ import annotations

import pytest

from contract_intelligence.shared.acl import AclAction, dossier_access_decision
from contract_intelligence.shared.auth.schemas import AuthenticatedUser


def _principal(
    *, user_id: str, tenant_id: str = "tenant_a", role: str = "REVIEWER"
) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=user_id,
        tenant_id=tenant_id,
        email=f"{user_id}@test.com",
        display_name=user_id,
        role=role,
    )


@pytest.mark.parametrize(
    ("action", "user", "dossier_tenant", "metadata", "allowed"),
    [
        (
            "query",
            _principal(user_id="owner"),
            "tenant_a",
            {"created_by": "owner", "access_scope": "mine"},
            True,
        ),
        (
            "search",
            _principal(user_id="shared"),
            "tenant_a",
            {
                "created_by": "owner",
                "access_scope": "shared_out",
                "shared_with": [{"id": "shared"}],
            },
            True,
        ),
        (
            "review_read",
            _principal(user_id="reader"),
            "tenant_a",
            {
                "created_by": "owner",
                "access_scope": "shared_out",
                "shared_with": [{"id": "reader"}],
            },
            True,
        ),
        (
            "review_mutate",
            _principal(user_id="reviewer"),
            "tenant_a",
            {
                "created_by": "owner",
                "access_scope": "shared_out",
                "shared_with": [{"id": "reviewer"}],
            },
            True,
        ),
        (
            "approve",
            _principal(user_id="admin", role="ADMINISTRATOR"),
            "tenant_a",
            {
                "created_by": "owner",
                "access_scope": "shared_out",
                "shared_with": [{"id": "admin"}],
            },
            True,
        ),
        (
            "query",
            _principal(user_id="other"),
            "tenant_b",
            {"created_by": "other"},
            False,
        ),
        (
            "query",
            _principal(user_id="reader"),
            "tenant_a",
            {"created_by": "owner", "access_scope": "mine"},
            False,
        ),
        (
            "search",
            _principal(user_id="reader"),
            "tenant_a",
            {
                "created_by": "owner",
                "access_scope": "shared_out",
                "shared_with": [],
            },
            False,
        ),
        (
            "review_mutate",
            _principal(user_id="operator", role="OPERATOR"),
            "tenant_a",
            {"created_by": "operator"},
            False,
        ),
    ],
)
def test_all_dossier_operations_use_tenant_share_role_and_actor_acl(
    action: str,
    user: AuthenticatedUser,
    dossier_tenant: str,
    metadata: dict[str, object],
    allowed: bool,
) -> None:
    assert (
        dossier_access_decision(
            action=AclAction(action),
            principal=user,
            dossier_id="dos_1",
            dossier_tenant_id=dossier_tenant,
            metadata=metadata,
        )
        is allowed
    )


def test_same_tenant_without_owner_or_share_is_denied() -> None:
    user = _principal(user_id="reader")
    assert (
        dossier_access_decision(
            action=AclAction.SEARCH,
            principal=user,
            dossier_id="dos_1",
            dossier_tenant_id="tenant_a",
            metadata={"access_scope": "shared_out", "shared_with": []},
        )
        is False
    )


def test_administrator_query_only_share_can_read_external_approvals() -> None:
    admin = _principal(user_id="admin", role="ADMINISTRATOR")
    assert dossier_access_decision(
        action=AclAction.QUERY,
        principal=admin,
        dossier_id="dos_1",
        dossier_tenant_id="tenant_a",
        metadata={
            "created_by": "owner",
            "access_scope": "shared_out",
            "shared_with": [{"id": "admin", "actions": ["query"]}],
        },
    ) is True
