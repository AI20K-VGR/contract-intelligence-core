"""Share grants: read/edit permission, expiry, revocation — DOC-11 §4.2 #10.

- the ACL decision (shared.acl) for read vs edit actions, expiry and status
- the dossier list filter (SQL) applies the same expiry/status rule
- PUT /dossiers/{id}/access: owner/admin only, expiry must be in the future,
  stored as UTC ISO; a plain PATCH cannot inject ACL fields
- the extraction guard resolves run/document ids and enforces edit
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from contract_intelligence.api.dossier_guard import require_dossier_action
from contract_intelligence.contract.application.services.contract_service import (
    ContractService,
)
from contract_intelligence.contract.infrastructure.persistence.orm import (
    DocumentORM,
    DossierORM,
    JobORM,
)
from contract_intelligence.contract.infrastructure.persistence.repository_impl import (
    DossierRepositoryImpl,
    JobRepositoryImpl,
)
from contract_intelligence.extraction.infrastructure.persistence.orm import PipelineRunORM
from contract_intelligence.shared.acl import (
    AclAction,
    dossier_access_decision,
    dossier_denied_detail,
    dossier_denied_message,
    grant_is_live,
    visible_dossier_metadata,
)
from contract_intelligence.shared.auth.schemas import AuthenticatedUser
from contract_intelligence.shared.persistence import Base
from contract_intelligence.shared.persistence.orm_registry import import_all_models

TENANT = "tenant_a"
NOW = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


def _user(user_id: str, role: str = "OPERATOR", tenant: str = TENANT) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=user_id,
        tenant_id=tenant,
        email=f"{user_id}@test.vn",
        display_name=user_id,
        role=role,
    )


def _meta(**grant: Any) -> dict[str, Any]:
    return {
        "created_by": "owner",
        "access_scope": "shared_out",
        "shared_with": [{"id": "guest", **grant}],
    }


def _allowed(action: AclAction, user: AuthenticatedUser, meta: dict[str, Any]) -> bool:
    return dossier_access_decision(
        action=action,
        principal=user,
        dossier_id="dos_1",
        dossier_tenant_id=TENANT,
        metadata=meta,
        now=NOW,
    )


# ──────────────────────────────────────────────────────────────────────────────
# ACL decision
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("grant", "action", "role", "allowed"),
    [
        ({"permission": "read"}, AclAction.QUERY, "OPERATOR", True),
        ({"permission": "read"}, AclAction.REVIEW_READ, "REVIEWER", True),
        ({"permission": "read"}, AclAction.REVIEW_MUTATE, "REVIEWER", False),
        ({"permission": "read"}, AclAction.DOSSIER_EDIT, "OPERATOR", False),
        ({"permission": "edit"}, AclAction.REVIEW_MUTATE, "REVIEWER", True),
        ({"permission": "edit"}, AclAction.DOSSIER_EDIT, "OPERATOR", True),
        # Grants written before the field existed keep full access.
        ({}, AclAction.DOSSIER_EDIT, "OPERATOR", True),
        ({"permission": "bogus"}, AclAction.DOSSIER_EDIT, "OPERATOR", True),
        # Expiry and revocation remove every action, read included.
        (
            {"permission": "edit", "expires_at": "2026-10-01T11:59:59+00:00"},
            AclAction.QUERY,
            "OPERATOR",
            False,
        ),
        (
            {"permission": "edit", "expires_at": "2026-10-01T12:00:00+00:00"},
            AclAction.QUERY,
            "OPERATOR",
            False,
        ),
        (
            {"permission": "edit", "expires_at": "2026-10-02T00:00:00+00:00"},
            AclAction.DOSSIER_EDIT,
            "OPERATOR",
            True,
        ),
        ({"expires_at": "not-a-date"}, AclAction.QUERY, "OPERATOR", False),
        ({"status": "disabled"}, AclAction.QUERY, "OPERATOR", False),
        ({"status": "invited"}, AclAction.QUERY, "OPERATOR", True),
        # Sharing never hands out ownership actions.
        ({"permission": "edit"}, AclAction.DOSSIER_MANAGE, "OPERATOR", False),
    ],
)
def test_grant_decision(grant: dict[str, Any], action: AclAction, role: str, allowed: bool) -> None:
    assert _allowed(action, _user("guest", role), _meta(**grant)) is allowed


def test_manage_is_owner_or_administrator_only() -> None:
    meta = _meta(permission="edit")
    assert _allowed(AclAction.DOSSIER_MANAGE, _user("owner"), meta)
    assert _allowed(AclAction.DOSSIER_MANAGE, _user("admin", "ADMINISTRATOR"), meta)
    assert not _allowed(AclAction.DOSSIER_MANAGE, _user("guest"), meta)
    assert not dossier_access_decision(
        action=AclAction.DOSSIER_MANAGE,
        principal=_user("admin", "ADMINISTRATOR", tenant="tenant_b"),
        dossier_id="dos_1",
        dossier_tenant_id=TENANT,
        metadata=meta,
    )


def test_naive_expiry_is_read_as_utc() -> None:
    assert grant_is_live({"expires_at": "2026-10-01T12:30:00"}, NOW)
    assert not grant_is_live({"expires_at": "2026-10-01T11:30:00"}, NOW)


# ──────────────────────────────────────────────────────────────────────────────
# Dossier list (SQL filter) and the extraction guard — sqlite
# ──────────────────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def factory(tmp_path: Any) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    import_all_models()
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'share.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


def _iso(delta: timedelta) -> str:
    return (datetime.now(tz=UTC) + delta).isoformat(timespec="seconds")


async def test_list_hides_expired_and_disabled_grants(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    grants = {
        "dos_live": {"permission": "read", "expires_at": _iso(timedelta(days=1))},
        "dos_forever": {"permission": "edit"},
        "dos_expired": {"permission": "edit", "expires_at": _iso(-timedelta(minutes=1))},
        "dos_disabled": {"permission": "edit", "status": "disabled"},
    }
    async with factory() as session:
        for dossier_id, grant in grants.items():
            session.add(
                DossierORM(
                    id=dossier_id, tenant_id=TENANT, name=dossier_id, metadata_json=_meta(**grant)
                )
            )
        await session.commit()

    async with factory() as session:
        page = await DossierRepositoryImpl(session, TENANT).list(
            viewer_id="guest", viewer_email="guest@test.vn"
        )
    assert sorted(d.id for d in page.items) == ["dos_forever", "dos_live"]


async def test_list_hides_dossiers_without_an_owner(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    """The ACL denies every read of an ownerless dossier, so the list must not offer it."""
    rows: dict[str, dict[str, Any] | None] = {
        "dos_mine": {"created_by": "guest"},
        "dos_no_metadata": None,
        "dos_no_owner": {},
        "dos_empty_owner": {"created_by": ""},
    }
    async with factory() as session:
        for dossier_id, metadata in rows.items():
            session.add(
                DossierORM(id=dossier_id, tenant_id=TENANT, name=dossier_id, metadata_json=metadata)
            )
        await session.commit()

    async with factory() as session:
        page = await DossierRepositoryImpl(session, TENANT).list(viewer_id="guest")
    listed = [d.id for d in page.items]

    assert listed == ["dos_mine"]
    for dossier_id, metadata in rows.items():
        assert _allowed(AclAction.QUERY, _user("guest"), metadata or {}) == (dossier_id in listed)


@pytest_asyncio.fixture
async def seeded(factory: async_sessionmaker[AsyncSession]) -> async_sessionmaker[AsyncSession]:
    async with factory() as session:
        session.add(
            DossierORM(
                id="dos_1", tenant_id=TENANT, name="d", metadata_json=_meta(permission="read")
            )
        )
        await session.flush()
        session.add(JobORM(id="job_1", tenant_id=TENANT, dossier_id="dos_1"))
        session.add(
            DocumentORM(
                id="doc_1",
                tenant_id=TENANT,
                dossier_id="dos_1",
                role="CONTRACT",
                order_index=0,
                filename="a.pdf",
                sha256="0" * 64,
            )
        )
        await session.flush()
        session.add(
            PipelineRunORM(id="run_1", tenant_id=TENANT, job_id="job_1", dossier_id="dos_1")
        )
        await session.commit()
    return factory


@pytest.mark.parametrize(
    "target", [{"dossier_id": "dos_1"}, {"run_id": "run_1"}, {"document_id": "doc_1"}]
)
async def test_guard_resolves_ids_and_refuses_read_only_edits(
    seeded: async_sessionmaker[AsyncSession], target: dict[str, str]
) -> None:
    async with seeded() as session:
        dossier = await require_dossier_action(
            session, _user("guest"), action=AclAction.QUERY, **target
        )
        assert dossier.id == "dos_1"
        with pytest.raises(HTTPException) as denied:
            await require_dossier_action(
                session, _user("guest"), action=AclAction.DOSSIER_EDIT, **target
            )
        assert denied.value.status_code == 403
        await require_dossier_action(
            session, _user("owner"), action=AclAction.DOSSIER_EDIT, **target
        )


async def test_guard_hides_other_tenants_and_unknown_ids(
    seeded: async_sessionmaker[AsyncSession],
) -> None:
    async with seeded() as session:
        for kwargs, user in (
            ({"run_id": "run_1"}, _user("owner", tenant="tenant_b")),
            ({"document_id": "doc_missing"}, _user("owner")),
            ({"dossier_id": "dos_missing"}, _user("owner")),
        ):
            with pytest.raises(HTTPException) as missing:
                await require_dossier_action(session, user, action=AclAction.QUERY, **kwargs)
            assert missing.value.status_code == 404


async def test_plain_patch_cannot_add_acl_fields(seeded: async_sessionmaker[AsyncSession]) -> None:
    async with seeded() as session:
        repo = DossierRepositoryImpl(session, TENANT)
        svc = ContractService.__new__(ContractService)
        # patch_dossier only touches the dossier and job repositories.
        svc._dossier_repo = repo
        svc._job_repo = JobRepositoryImpl(session, TENANT)
        dossier = await svc.patch_dossier(
            "dos_1",
            name=None,
            metadata={
                "note": "ok",
                "created_by": "guest",
                "shared_with": [{"id": "guest", "permission": "edit"}],
            },
        )
        await session.commit()
    assert dossier.metadata is not None
    assert dossier.metadata["note"] == "ok"
    assert dossier.metadata["created_by"] == "owner"
    assert dossier.metadata["shared_with"] == [{"id": "guest", "permission": "read"}]


# ──────────────────────────────────────────────────────────────────────────────
# Denial message and grant visibility
# ──────────────────────────────────────────────────────────────────────────────


def _denied(action: AclAction, user: AuthenticatedUser, meta: dict[str, Any]) -> str:
    return dossier_denied_message(
        action=action,
        principal=user,
        dossier_id="dos_1",
        dossier_tenant_id=TENANT,
        metadata=meta,
    )


def test_denial_tells_read_grantee_they_can_only_view() -> None:
    reviewer = _user("guest", role="REVIEWER")
    meta = _meta(permission="read")
    assert not _allowed(AclAction.REVIEW_MUTATE, reviewer, meta)
    assert _denied(AclAction.REVIEW_MUTATE, reviewer, meta) == "Bạn chỉ có quyền xem hồ sơ này."


def test_denial_names_role_before_grant() -> None:
    operator = _user("guest")
    assert _denied(AclAction.REVIEW_MUTATE, operator, _meta(permission="edit")).startswith(
        "Chỉ người thẩm định"
    )
    assert _denied(AclAction.APPROVE, operator, _meta()) == "Chỉ quản trị viên được duyệt hồ sơ."


def test_denial_for_expired_or_missing_grant() -> None:
    expired = _meta(permission="read", expires_at="2020-01-01T00:00:00+00:00")
    message = "Bạn không có quyền trên hồ sơ này, hoặc quyền đã hết hạn."
    assert _denied(AclAction.DOSSIER_EDIT, _user("guest"), expired) == message
    assert _denied(AclAction.QUERY, _user("stranger"), _meta()) == message


def _denied_code(action: AclAction, user: AuthenticatedUser, meta: dict[str, Any]) -> str:
    return dossier_denied_detail(
        action=action,
        principal=user,
        dossier_id="dos_1",
        dossier_tenant_id=TENANT,
        metadata=meta,
    )["code"]


def test_denial_code_says_why() -> None:
    """The frontend branches on ``code``, never on the Vietnamese text."""
    operator, reviewer = _user("guest"), _user("guest", role="REVIEWER")
    expired = _meta(permission="edit", expires_at="2020-01-01T00:00:00+00:00")
    assert _denied_code(AclAction.REVIEW_MUTATE, operator, _meta(permission="edit")) == (
        "ROLE_DENIED"
    )
    assert _denied_code(AclAction.APPROVE, operator, _meta()) == "ROLE_DENIED"
    assert _denied_code(AclAction.REVIEW_MUTATE, reviewer, _meta(permission="read")) == (
        "READ_ONLY"
    )
    assert _denied_code(AclAction.DOSSIER_EDIT, operator, expired) == "ACL_DENIED"
    assert _denied_code(AclAction.QUERY, _user("stranger"), _meta()) == "ACL_DENIED"


def test_grantee_sees_only_own_grant_by_id_or_email() -> None:
    meta = {
        "created_by": "owner",
        "shared_with": [
            {"id": "guest", "permission": "read"},
            {"id": "pending", "email": "Other@test.vn"},
            {"id": "third", "email": "third@test.vn"},
        ],
    }
    assert [g["id"] for g in visible_dossier_metadata(meta, _user("guest"))["shared_with"]] == [
        "guest"
    ]
    other = AuthenticatedUser(
        user_id="other", tenant_id=TENANT, email="other@test.vn", display_name="", role="OPERATOR"
    )
    assert [g["id"] for g in visible_dossier_metadata(meta, other)["shared_with"]] == ["pending"]
    assert visible_dossier_metadata(meta, _user("owner")) == meta
    assert visible_dossier_metadata(meta, _user("admin", role="ADMINISTRATOR")) == meta
