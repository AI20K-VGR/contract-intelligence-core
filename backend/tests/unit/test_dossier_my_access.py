"""``my_access`` and the lock/approval state on GET /dossiers and GET /dossiers/{id}."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from contract_intelligence.contract.application.services.contract_service import ContractService
from contract_intelligence.contract.domain.entities.dossier import Dossier
from contract_intelligence.contract.infrastructure.persistence.orm import DossierORM
from contract_intelligence.contract.infrastructure.persistence.repository_impl import (
    DossierRepositoryImpl,
)
from contract_intelligence.main import app
from contract_intelligence.review.infrastructure.persistence.orm_approval import DossierApprovalORM
from contract_intelligence.shared.acl import AclAction, dossier_access_decision, dossier_my_access
from contract_intelligence.shared.auth.schemas import AuthenticatedUser
from contract_intelligence.shared.persistence import Base
from contract_intelligence.shared.persistence.orm_registry import import_all_models

TENANT = "tenant_test"
NOW = datetime(2026, 10, 12, 8, tzinfo=UTC)
OWNER = "usr_owner"

_ACTION_OF = {
    "can_edit": AclAction.DOSSIER_EDIT,
    "can_review": AclAction.REVIEW_MUTATE,
    "can_see_review": AclAction.REVIEW_READ,
    "can_manage": AclAction.DOSSIER_MANAGE,
    "can_approve": AclAction.APPROVE,
}


def _user(user_id: str, role: str, tenant: str = TENANT) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=user_id,
        tenant_id=tenant,
        email=f"{user_id}@test.com",
        display_name=user_id,
        role=role,
    )


def _grant(user_id: str, **fields: Any) -> dict[str, Any]:
    return {"id": user_id, "email": f"{user_id}@test.com", "permission": "edit", **fields}


def _meta(*grants: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {"created_by": OWNER, "shared_with": list(grants), **extra}


def _access(user: AuthenticatedUser, metadata: dict[str, Any] | None) -> dict[str, Any]:
    return dossier_my_access(
        principal=user,
        dossier_id="dos_1",
        dossier_tenant_id=TENANT,
        metadata=metadata,
        now=NOW,
    )


def _flags(access: dict[str, Any]) -> set[str]:
    return {name for name in _ACTION_OF if access[name]}


def test_owner_operator_edits_and_manages_but_does_not_review() -> None:
    access = _access(_user(OWNER, "OPERATOR"), _meta())

    assert access["owner"] is True
    assert access["permission"] is None
    assert _flags(access) == {"can_edit", "can_manage"}


def test_reviewer_with_an_edit_share_reviews_but_does_not_edit_or_approve() -> None:
    until = NOW + timedelta(days=2)
    access = _access(
        _user("usr_rev", "REVIEWER"), _meta(_grant("usr_rev", expires_at=until.isoformat()))
    )

    assert (access["owner"], access["permission"], access["expired"]) == (False, "edit", False)
    assert access["expires_at"] == until
    assert _flags(access) == {"can_review", "can_see_review"}


def test_reviewer_with_a_read_share_only_sees_the_review() -> None:
    access = _access(_user("usr_rev", "REVIEWER"), _meta(_grant("usr_rev", permission="read")))

    assert access["permission"] == "read"
    assert _flags(access) == {"can_see_review"}


def test_operator_with_an_edit_share_edits_but_does_not_manage() -> None:
    access = _access(_user("usr_op", "OPERATOR"), _meta(_grant("usr_op")))

    assert _flags(access) == {"can_edit"}


def test_expired_share_is_reported_and_gives_nothing() -> None:
    ended = NOW - timedelta(hours=1)
    access = _access(
        _user("usr_rev", "REVIEWER"), _meta(_grant("usr_rev", expires_at=ended.isoformat()))
    )

    assert (access["permission"], access["expired"], access["expires_at"]) == ("edit", True, ended)
    assert _flags(access) == set()


def test_disabled_share_and_private_dossier_count_as_no_share() -> None:
    disabled = _access(_user("usr_rev", "REVIEWER"), _meta(_grant("usr_rev", status="disabled")))
    private = _access(_user("usr_rev", "REVIEWER"), _meta(_grant("usr_rev"), access_scope="mine"))

    for access in (disabled, private):
        assert (access["permission"], access["expired"]) == (None, False)
        assert _flags(access) == set()


def test_live_edit_share_wins_over_read_and_expired_ones() -> None:
    later = NOW + timedelta(days=9)
    access = _access(
        _user("usr_rev", "REVIEWER"),
        _meta(
            _grant("usr_rev", expires_at=(NOW - timedelta(days=1)).isoformat()),
            _grant("usr_rev", permission="read"),
            _grant("usr_rev", expires_at=(NOW + timedelta(days=1)).isoformat()),
            _grant("usr_rev", expires_at=later.isoformat()),
            _grant("usr_someone_else"),
        ),
    )

    assert (access["permission"], access["expires_at"], access["expired"]) == ("edit", later, False)


def test_administrator_manages_without_a_share_but_needs_one_to_approve() -> None:
    admin = _user("usr_admin", "ADMINISTRATOR")

    assert _flags(_access(admin, _meta())) == {"can_manage"}
    assert _flags(_access(admin, _meta(_grant("usr_admin")))) == set(_ACTION_OF)


def test_stranger_and_missing_metadata_get_nothing() -> None:
    for metadata in (_meta(), None):
        access = _access(_user("usr_rev", "REVIEWER"), metadata)
        assert access["owner"] is False
        assert _flags(access) == set()


@pytest.mark.parametrize("role", ["OPERATOR", "REVIEWER", "ADMINISTRATOR"])
@pytest.mark.parametrize(
    "metadata",
    [
        _meta(),
        _meta(_grant("usr_x")),
        _meta(_grant("usr_x", permission="read")),
        _meta(_grant("usr_x", expires_at=(NOW - timedelta(days=1)).isoformat())),
        {"created_by": "usr_x"},
    ],
)
def test_every_flag_is_the_acl_decision_for_its_action(role: str, metadata: dict[str, Any]) -> None:
    user = _user("usr_x", role)
    access = _access(user, metadata)

    for name, action in _ACTION_OF.items():
        assert access[name] is dossier_access_decision(
            action=action,
            principal=user,
            dossier_id="dos_1",
            dossier_tenant_id=TENANT,
            metadata=metadata,
            now=NOW,
        )


# ---------------------------------------------------------------------------
# Repository: lock and approval state for a page of dossiers
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def factory(tmp_path: Any) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    import_all_models()
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'lifecycle.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


@pytest.mark.asyncio
async def test_lifecycle_reads_lock_and_approval_time_in_one_call(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    approved_at = datetime(2026, 10, 10, 9, 30, tzinfo=UTC)
    async with factory() as session:
        session.add_all(
            [
                DossierORM(id="dos_open", tenant_id=TENANT, name="Open"),
                DossierORM(id="dos_locked", tenant_id=TENANT, name="Locked", is_locked=True),
                DossierORM(
                    id="dos_approved",
                    tenant_id=TENANT,
                    name="Approved",
                    is_locked=True,
                    is_approved=True,
                ),
                DossierORM(id="dos_foreign", tenant_id="tenant_other", name="X", is_locked=True),
            ]
        )
        await session.flush()
        session.add(
            DossierApprovalORM(
                id="apr_1",
                tenant_id=TENANT,
                dossier_id="dos_approved",
                approved_by="usr_admin",
                checksum="c" * 64,
                approved_at=approved_at,
            )
        )
        await session.commit()

    async with factory() as session:
        repo = DossierRepositoryImpl(session, TENANT)
        found = await repo.lifecycle(["dos_open", "dos_locked", "dos_approved", "dos_foreign"])
        nothing = await repo.lifecycle([])

    assert found == {
        "dos_open": (False, None),
        "dos_locked": (True, None),
        "dos_approved": (True, approved_at),
    }
    assert nothing == {}


# ---------------------------------------------------------------------------
# API: both dossier endpoints carry the fields
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def mock_svc() -> AsyncMock:
    svc = AsyncMock(spec=ContractService)
    svc.review_counts.return_value = (0, 0)
    svc.lifecycle.return_value = {}
    svc.document_summaries.return_value = {}
    return svc


@pytest_asyncio.fixture
async def client(mock_svc: AsyncMock) -> AsyncGenerator[AsyncClient, None]:
    from contract_intelligence.contract.interfaces.api.dependencies import get_contract_service
    from contract_intelligence.shared.auth import get_current_user
    from contract_intelligence.shared.auth.tenant import get_tenant_id

    app.dependency_overrides[get_contract_service] = lambda: mock_svc
    app.dependency_overrides[get_current_user] = lambda: _user("usr_rev", "REVIEWER")
    app.dependency_overrides[get_tenant_id] = lambda: TENANT
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()


def _dossier(dossier_id: str, metadata: dict[str, Any]) -> Dossier:
    return Dossier(
        id=dossier_id, name=dossier_id, batch_id=None, has_conflicts=False, metadata=metadata
    )


@pytest.mark.asyncio
async def test_list_carries_my_access_and_lifecycle_per_dossier(
    client: AsyncClient, mock_svc: AsyncMock
) -> None:
    approved_at = datetime(2026, 10, 10, 9, 30, tzinfo=UTC)
    mock_svc.list_dossiers.return_value = (
        [
            _dossier("dos_edit", _meta(_grant("usr_rev"))),
            _dossier("dos_read", _meta(_grant("usr_rev", permission="read"))),
        ],
        2,
    )
    mock_svc.lifecycle.return_value = {"dos_read": (True, approved_at)}

    response = await client.get("/api/v1/dossiers")

    assert response.status_code == 200
    edit, read = response.json()["data"]
    assert set(edit["my_access"]) == {
        "owner",
        "permission",
        "expires_at",
        "expired",
        "can_edit",
        "can_review",
        "can_see_review",
        "can_manage",
        "can_approve",
    }
    assert (edit["my_access"]["permission"], edit["my_access"]["can_review"]) == ("edit", True)
    assert (edit["locked"], edit["approved_at"]) == (False, None)
    assert (read["my_access"]["permission"], read["my_access"]["can_review"]) == ("read", False)
    assert read["my_access"]["can_see_review"] is True
    assert read["locked"] is True
    assert datetime.fromisoformat(read["approved_at"]) == approved_at
    mock_svc.lifecycle.assert_awaited_once_with(["dos_edit", "dos_read"])


@pytest.mark.asyncio
async def test_detail_carries_my_access_and_lifecycle(
    client: AsyncClient, mock_svc: AsyncMock
) -> None:
    mock_svc.get_dossier.return_value = _dossier("dos_1", _meta(_grant("usr_rev")))
    mock_svc.list_documents.return_value = []
    mock_svc.lifecycle.return_value = {"dos_1": (True, None)}

    response = await client.get("/api/v1/dossiers/dos_1")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["my_access"]["can_review"] is True
    assert data["my_access"]["can_edit"] is False
    assert (data["locked"], data["approved_at"]) == (True, None)


@pytest.mark.asyncio
async def test_my_access_is_computed_before_other_shares_are_hidden(
    client: AsyncClient, mock_svc: AsyncMock
) -> None:
    mock_svc.list_dossiers.return_value = (
        [_dossier("dos_1", _meta(_grant("usr_other"), _grant("usr_rev")))],
        1,
    )

    (item,) = (await client.get("/api/v1/dossiers")).json()["data"]

    assert [grant["id"] for grant in item["metadata"]["shared_with"]] == ["usr_rev"]
    assert item["my_access"]["permission"] == "edit"
