"""GET /review-queue: dossiers waiting for the caller's review."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from contract_intelligence.contract.infrastructure.persistence.orm import DossierORM
from contract_intelligence.main import app
from contract_intelligence.review.infrastructure.persistence.orm import ReviewItemORM
from contract_intelligence.review.interfaces.api.review_queue import load_review_queue
from contract_intelligence.shared.auth import get_current_user
from contract_intelligence.shared.auth.schemas import AuthenticatedUser
from contract_intelligence.shared.persistence import Base, get_async_session
from contract_intelligence.shared.persistence.orm_registry import import_all_models

TENANT = "tenant_a"
NOW = datetime(2026, 10, 12, 8, tzinfo=UTC)
OWNER = "usr_owner"
RITA = "usr_rita"


def _user(user_id: str, role: str, tenant: str = TENANT) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=user_id,
        tenant_id=tenant,
        email=f"{user_id}@example.com",
        display_name=user_id,
        role=role,
    )


def _grant(user_id: str, **fields: Any) -> dict[str, Any]:
    return {"id": user_id, "email": f"{user_id}@example.com", "permission": "edit", **fields}


def _dossier(
    dossier_id: str,
    *,
    day: int,
    grants: list[dict[str, Any]] | None = None,
    tenant: str = TENANT,
    owner: str = OWNER,
    deleted: bool = False,
) -> DossierORM:
    return DossierORM(
        id=dossier_id,
        tenant_id=tenant,
        name=f"Dossier {dossier_id}",
        metadata_json={"created_by": owner, "shared_with": grants or []},
        created_at=datetime(2026, 10, day, tzinfo=UTC),
        deleted_at=NOW if deleted else None,
    )


def _items(
    dossier_id: str,
    *,
    p1: int = 0,
    p2: int = 0,
    p3: int = 0,
    findings: int = 0,
    status: str = "open",
    tenant: str = TENANT,
) -> list[ReviewItemORM]:
    priorities = ["P1"] * p1 + ["P2"] * p2 + ["P3"] * p3
    return [
        ReviewItemORM(
            id=f"rev_{dossier_id}_{status}_{index}",
            tenant_id=tenant,
            dossier_id=dossier_id,
            run_id="run_1",
            target_type="finding" if index < findings else "clause_node",
            target_id=f"target_{index}",
            reason="check",
            priority=priority,
            status=status,
        )
        for index, priority in enumerate(priorities)
    ]


@pytest_asyncio.fixture
async def factory(tmp_path: Any) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    import_all_models()
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'queue.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


async def _seed(factory: async_sessionmaker[AsyncSession], *rows: Any) -> None:
    flat: list[Any] = []
    for row in rows:
        flat.extend(row if isinstance(row, list) else [row])
    async with factory() as session:
        session.add_all(flat)
        await session.commit()


async def _queue(
    factory: async_sessionmaker[AsyncSession],
    user: AuthenticatedUser,
    *,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Any], int]:
    async with factory() as session:
        return await load_review_queue(session, user, limit=limit, offset=offset, now=NOW)


@pytest.mark.asyncio
async def test_reviewer_sees_dossiers_shared_for_edit_with_open_items(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(
        factory,
        _dossier("d_shared", day=1, grants=[_grant(RITA)]),
        _items("d_shared", p1=1, p2=2, p3=3, findings=2),
        _dossier("d_not_shared", day=2),
        _items("d_not_shared", p1=5),
    )

    entries, total = await _queue(factory, _user(RITA, "REVIEWER"))

    assert total == 1
    (entry,) = entries
    assert entry.dossier_id == "d_shared"
    assert (entry.p1, entry.p2, entry.p3) == (1, 2, 3)
    assert entry.open_review_items == 6
    assert entry.pending_conflicts == 2
    assert entry.is_owner is False


@pytest.mark.asyncio
async def test_read_only_expired_and_disabled_grants_give_nothing(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    past = (NOW - timedelta(hours=1)).isoformat()
    await _seed(
        factory,
        _dossier("d_read", day=1, grants=[_grant(RITA, permission="read")]),
        _items("d_read", p1=1),
        _dossier("d_expired", day=2, grants=[_grant(RITA, expires_at=past)]),
        _items("d_expired", p1=1),
        _dossier("d_disabled", day=3, grants=[_grant(RITA, status="disabled")]),
        _items("d_disabled", p1=1),
    )

    entries, total = await _queue(factory, _user(RITA, "REVIEWER"))

    assert (entries, total) == ([], 0)


@pytest.mark.asyncio
async def test_dossiers_without_open_items_are_left_out(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(
        factory,
        _dossier("d_done", day=1, grants=[_grant(RITA)]),
        _items("d_done", p1=2, status="confirmed"),
        _dossier("d_empty", day=2, grants=[_grant(RITA)]),
        _dossier("d_waiting", day=3, grants=[_grant(RITA)]),
        _items("d_waiting", p2=1, status="awaiting_evidence"),
    )

    entries, _ = await _queue(factory, _user(RITA, "REVIEWER"))

    assert [entry.dossier_id for entry in entries] == ["d_waiting"]


@pytest.mark.asyncio
async def test_more_p1_first_then_the_oldest_dossier(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    grants = [_grant(RITA)]
    await _seed(
        factory,
        _dossier("d_new_no_p1", day=9, grants=grants),
        _items("d_new_no_p1", p2=4),
        _dossier("d_old_no_p1", day=2, grants=grants),
        _items("d_old_no_p1", p3=1),
        _dossier("d_one_p1", day=8, grants=grants),
        _items("d_one_p1", p1=1),
        _dossier("d_two_p1", day=7, grants=grants),
        _items("d_two_p1", p1=2),
    )

    entries, total = await _queue(factory, _user(RITA, "REVIEWER"))
    page, _ = await _queue(factory, _user(RITA, "REVIEWER"), limit=2, offset=1)

    order = ["d_two_p1", "d_one_p1", "d_old_no_p1", "d_new_no_p1"]
    assert [entry.dossier_id for entry in entries] == order
    assert total == 4
    assert [entry.dossier_id for entry in page] == order[1:3]


@pytest.mark.asyncio
async def test_grant_expiry_is_reported(factory: async_sessionmaker[AsyncSession]) -> None:
    soon = NOW + timedelta(days=1)
    later = NOW + timedelta(days=5)
    await _seed(
        factory,
        _dossier("d_until", day=1, grants=[_grant(RITA, expires_at=soon.isoformat())]),
        _items("d_until", p1=1),
        _dossier(
            "d_two_grants",
            day=2,
            grants=[
                _grant(RITA, expires_at=soon.isoformat()),
                _grant(RITA, expires_at=later.isoformat()),
            ],
        ),
        _items("d_two_grants", p1=1),
        _dossier("d_open_ended", day=3, grants=[_grant(RITA)]),
        _items("d_open_ended", p1=1),
    )

    entries, _ = await _queue(factory, _user(RITA, "REVIEWER"))

    expiry = {entry.dossier_id: entry.grant_expires_at for entry in entries}
    assert expiry == {"d_until": soon, "d_two_grants": later, "d_open_ended": None}


@pytest.mark.asyncio
async def test_owner_sees_own_dossier_without_a_grant(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(factory, _dossier("d_own", day=1, owner=RITA), _items("d_own", p3=1))

    (entry,), _ = await _queue(factory, _user(RITA, "REVIEWER"))

    assert entry.is_owner is True
    assert entry.grant_expires_at is None


@pytest.mark.asyncio
async def test_administrator_needs_a_grant_too(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(
        factory,
        _dossier("d_granted", day=1, grants=[_grant("usr_admin")]),
        _items("d_granted", p1=1),
        _dossier("d_other", day=2),
        _items("d_other", p1=1),
    )

    entries, _ = await _queue(factory, _user("usr_admin", "ADMINISTRATOR"))

    assert [entry.dossier_id for entry in entries] == ["d_granted"]


@pytest.mark.asyncio
async def test_other_tenants_and_deleted_dossiers_are_invisible(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(
        factory,
        _dossier("d_foreign", day=1, grants=[_grant(RITA)], tenant="tenant_b"),
        _items("d_foreign", p1=1, tenant="tenant_b"),
        _dossier("d_deleted", day=2, grants=[_grant(RITA)], deleted=True),
        _items("d_deleted", p1=1),
    )

    entries, total = await _queue(factory, _user(RITA, "REVIEWER"))

    assert (entries, total) == ([], 0)


@pytest_asyncio.fixture
async def client(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncClient, None]:
    async def _session() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_async_session] = _session
    app.dependency_overrides[get_current_user] = lambda: _user(RITA, "REVIEWER")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_endpoint_returns_the_queue_with_meta(
    client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed(
        factory, _dossier("d_api", day=1, grants=[_grant(RITA)]), _items("d_api", p1=1, p3=2)
    )

    response = await client.get("/api/v1/review-queue", params={"limit": 5})

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 1
    (entry,) = body["data"]
    assert set(entry) == {
        "dossier_id",
        "dossier_name",
        "dossier_status",
        "created_at",
        "is_owner",
        "grant_expires_at",
        "open_review_items",
        "pending_conflicts",
        "p1",
        "p2",
        "p3",
    }
    assert (entry["dossier_id"], entry["p1"], entry["p3"]) == ("d_api", 1, 2)


@pytest.mark.asyncio
async def test_operator_is_refused(client: AsyncClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: _user("usr_op", "OPERATOR")

    assert (await client.get("/api/v1/review-queue")).status_code == 403
