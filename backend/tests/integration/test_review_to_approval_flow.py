"""pending_review → reviewed → approved through the real API (sqlite, offline).

Nothing here presets ``reviewed``: the dossier gets there only by review
actions closing every item, and approval then moves it (and its job, which
the frontend reads) to ``approved``. Each human step leaves an audit event.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tests.integration.test_ai2_review_fixes_flow import (
    DOSSIER_ID,
    OPERATOR,
    REVIEWER,
    RUN_ID,
    TENANT_ID,
    _seed_dossier,
)

from contract_intelligence.contract.infrastructure.persistence.orm import (
    DocumentORM,
    DossierORM,
    JobORM,
)
from contract_intelligence.main import app
from contract_intelligence.review.infrastructure.persistence.orm import ReviewItemORM
from contract_intelligence.shared.audit import AuditEventORM
from contract_intelligence.shared.auth import AuthenticatedUser, get_current_user
from contract_intelligence.shared.auth.tenant import get_tenant_id
from contract_intelligence.shared.persistence import Base
from contract_intelligence.shared.persistence.orm_registry import import_all_models
from contract_intelligence.shared.persistence.session import get_async_session

pytestmark = pytest.mark.integration

ITEMS = ("ri_flow_1", "ri_flow_2")
# The dossier owner, as ADMINISTRATOR: approval needs both the role and the ACL.
APPROVER = AuthenticatedUser(
    user_id=OPERATOR.user_id,
    tenant_id=TENANT_ID,
    email="approver@vsf.test",
    display_name="VSF Approver",
    role="ADMINISTRATOR",
)


@pytest_asyncio.fixture
async def factory(tmp_path: Any) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    import_all_models()
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'review-flow.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await _seed_dossier(session_factory)
    async with session_factory() as session:
        # Where the worker leaves a dossier once AI2's result is persisted.
        await session.execute(
            update(DossierORM).where(DossierORM.id == DOSSIER_ID).values(status="pending_review")
        )
        await session.execute(
            update(JobORM).where(JobORM.dossier_id == DOSSIER_ID).values(status="pending_review")
        )
        # The shared seed writes upper-case roles; the domain enum is lower-case.
        for document in (await session.scalars(select(DocumentORM))).all():
            document.role = document.role.lower()
        for item_id in ITEMS:
            session.add(
                ReviewItemORM(
                    id=item_id,
                    tenant_id=TENANT_ID,
                    dossier_id=DOSSIER_ID,
                    run_id=RUN_ID,
                    target_type="finding",
                    target_id=f"finding-{item_id}",
                    reason="conflict",
                    priority="P1",
                    status="open",
                    version=1,
                )
            )
        await session.commit()
    yield session_factory
    await engine.dispose()


@pytest_asyncio.fixture
async def client(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncClient, None]:
    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[get_tenant_id] = lambda: TENANT_ID
    _act_as(REVIEWER)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def _act_as(user: AuthenticatedUser) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


async def _act(client: AsyncClient, item_id: str, action: str = "confirm") -> None:
    response = await client.post(
        f"/api/v1/review-items/{item_id}/actions",
        json={"action": action, "base_version": 1},
    )
    assert response.status_code == 200, response.text


async def _approve(client: AsyncClient) -> Any:
    _act_as(APPROVER)
    return await client.post(f"/api/v1/dossiers/{DOSSIER_ID}/approve", json={"comment": "ok"})


async def _statuses(factory: async_sessionmaker[AsyncSession]) -> tuple[str, str]:
    async with factory() as session:
        dossier = await session.get(DossierORM, DOSSIER_ID)
        job = await session.scalar(select(JobORM).where(JobORM.dossier_id == DOSSIER_ID))
    assert dossier is not None and job is not None
    return dossier.status, job.status


async def _audits(factory: async_sessionmaker[AsyncSession], action: str) -> list[AuditEventORM]:
    async with factory() as session:
        return list(
            (
                await session.execute(select(AuditEventORM).where(AuditEventORM.action == action))
            ).scalars()
        )


@pytest.mark.asyncio
async def test_closing_the_last_item_marks_the_dossier_reviewed(
    factory: async_sessionmaker[AsyncSession], client: AsyncClient
) -> None:
    await _act(client, ITEMS[0])
    assert await _statuses(factory) == ("pending_review", "pending_review")

    await _act(client, ITEMS[1], "reject")
    assert await _statuses(factory) == ("reviewed", "reviewed")

    (audit,) = await _audits(factory, "dossier.reviewed")
    assert audit.actor_id == REVIEWER.user_id and audit.run_id == RUN_ID
    assert (audit.from_state, audit.to_state) == ("pending_review", "reviewed")


@pytest.mark.asyncio
async def test_awaiting_evidence_keeps_the_dossier_in_review(
    factory: async_sessionmaker[AsyncSession], client: AsyncClient
) -> None:
    await _act(client, ITEMS[0])
    await _act(client, ITEMS[1], "needs_more_evidence")

    assert await _statuses(factory) == ("pending_review", "pending_review")
    assert await _audits(factory, "dossier.reviewed") == []
    response = await _approve(client)
    assert response.status_code == 409, response.text


@pytest.mark.asyncio
async def test_review_then_approve_end_to_end(
    factory: async_sessionmaker[AsyncSession], client: AsyncClient
) -> None:
    for item_id in ITEMS:
        await _act(client, item_id)

    response = await _approve(client)

    assert response.status_code == 200, response.text
    assert response.json()["data"]["latest_job_status"] == "approved"
    assert await _statuses(factory) == ("approved", "approved")
    (audit,) = await _audits(factory, "dossier.approved")
    assert audit.actor_id == APPROVER.user_id
    assert (audit.from_state, audit.to_state) == ("reviewed", "approved")
    detail = await client.get(f"/api/v1/dossiers/{DOSSIER_ID}")
    assert detail.json()["data"]["latest_job_status"] == "approved"


@pytest.mark.asyncio
async def test_approve_refused_while_an_item_is_open(
    factory: async_sessionmaker[AsyncSession], client: AsyncClient
) -> None:
    await _act(client, ITEMS[0])

    response = await _approve(client)

    assert response.status_code == 409, response.text
    assert await _statuses(factory) == ("pending_review", "pending_review")


@pytest.mark.asyncio
async def test_dossier_closed_before_this_rule_can_still_be_approved(
    factory: async_sessionmaker[AsyncSession], client: AsyncClient
) -> None:
    # Items closed while nothing moved the dossier on (data from before the fix).
    async with factory() as session:
        await session.execute(update(ReviewItemORM).values(status="resolved"))
        await session.commit()

    response = await _approve(client)

    assert response.status_code == 200, response.text
    assert await _statuses(factory) == ("approved", "approved")
    (reviewed,) = await _audits(factory, "dossier.reviewed")
    assert reviewed.actor_id == APPROVER.user_id


@pytest.mark.asyncio
async def test_lock_is_audited(
    factory: async_sessionmaker[AsyncSession], client: AsyncClient
) -> None:
    _act_as(APPROVER)
    response = await client.post(f"/api/v1/dossiers/{DOSSIER_ID}/lock")

    assert response.status_code == 200, response.text
    (audit,) = await _audits(factory, "dossier.locked")
    assert audit.actor_id == APPROVER.user_id and audit.dossier_id == DOSSIER_ID
