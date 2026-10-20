"""ST-038 hardening for POST /review-items/{id}/actions (sqlite, offline).

- every accepted action writes an ``audit_event`` in the same transaction
- locked / approved dossier → 409, nothing written
- ``base_version`` starts at 1 (0 is rejected)
- a racing action on the same base_version → 409 with the winner's state
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tests.integration.test_ai2_review_fixes_flow import (
    DOSSIER_ID,
    REVIEWER,
    RUN_ID,
    TENANT_ID,
    _seed_dossier,
)

from contract_intelligence.contract.infrastructure.persistence.orm import DossierORM
from contract_intelligence.main import app
from contract_intelligence.review.infrastructure.persistence.orm import (
    ReviewActionORM,
    ReviewItemORM,
)
from contract_intelligence.shared.audit import AuditEventORM
from contract_intelligence.shared.auth import get_current_user
from contract_intelligence.shared.auth.tenant import get_tenant_id
from contract_intelligence.shared.persistence import Base
from contract_intelligence.shared.persistence.orm_registry import import_all_models
from contract_intelligence.shared.persistence.session import get_async_session

ITEM_ID = "ri_hardening"


@pytest_asyncio.fixture
async def factory(tmp_path: Any) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    import_all_models()
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'review-actions.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await _seed_dossier(session_factory)
    async with session_factory() as session:
        session.add(
            ReviewItemORM(
                id=ITEM_ID,
                tenant_id=TENANT_ID,
                dossier_id=DOSSIER_ID,
                run_id=RUN_ID,
                target_type="finding",
                target_id="finding-1",
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
    app.dependency_overrides[get_current_user] = lambda: REVIEWER
    app.dependency_overrides[get_tenant_id] = lambda: TENANT_ID
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def _post(client: AsyncClient, body: dict[str, Any]) -> Any:
    return await client.post(
        f"/api/v1/review-items/{ITEM_ID}/actions",
        json=body,
        headers={"Idempotency-Key": "hardening"},
    )


async def _action_count(factory: async_sessionmaker[AsyncSession]) -> int:
    async with factory() as session:
        return int(await session.scalar(select(func.count()).select_from(ReviewActionORM)) or 0)


@pytest.mark.asyncio
async def test_action_writes_audit_event(
    factory: async_sessionmaker[AsyncSession], client: AsyncClient
) -> None:
    response = await _post(
        client, {"action": "correct", "base_version": 1, "corrected_value": {"v": 2}}
    )

    assert response.status_code == 200, response.text
    async with factory() as session:
        audits = list(
            (
                await session.execute(
                    select(AuditEventORM).where(AuditEventORM.action == "review.action_submitted")
                )
            ).scalars()
        )
    assert len(audits) == 1
    audit = audits[0]
    assert audit.actor_id == REVIEWER.user_id
    assert audit.entity_id == ITEM_ID and audit.dossier_id == DOSSIER_ID
    assert (audit.from_state, audit.to_state) == ("open", "resolved")
    detail = json.loads(audit.detail or "{}")
    assert detail["base_version"] == 1 and detail["new_version"] == 2
    assert detail["review_action_id"] == response.json()["data"]["review_action_id"]
    assert detail["has_correction"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("flag", ["is_locked", "is_approved"])
async def test_action_refused_on_locked_or_approved_dossier(
    factory: async_sessionmaker[AsyncSession], client: AsyncClient, flag: str
) -> None:
    async with factory() as session:
        dossier = await session.get(DossierORM, DOSSIER_ID)
        assert dossier is not None
        setattr(dossier, flag, True)
        await session.commit()

    response = await _post(client, {"action": "confirm", "base_version": 1})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVARIANT_VIOLATION"
    assert await _action_count(factory) == 0
    async with factory() as session:
        item = await session.get(ReviewItemORM, ITEM_ID)
    assert item is not None and item.version == 1


@pytest.mark.asyncio
async def test_base_version_zero_is_rejected(
    factory: async_sessionmaker[AsyncSession], client: AsyncClient
) -> None:
    response = await _post(client, {"action": "confirm", "base_version": 0})
    assert response.status_code == 422
    assert await _action_count(factory) == 0


@pytest.mark.asyncio
async def test_racing_action_on_same_base_version_returns_409(
    factory: async_sessionmaker[AsyncSession], client: AsyncClient
) -> None:
    # The winner's action row is committed but (as seen by the loser) the item
    # still reads version 1 — the unique (item, base_version) index must catch it.
    async with factory() as session:
        session.add(
            ReviewActionORM(
                id="ra_winner",
                tenant_id=TENANT_ID,
                review_item_id=ITEM_ID,
                target_type="finding",
                target_id="finding-1",
                action="reject",
                base_version=1,
                reviewer_id="user-other-reviewer",
            )
        )
        await session.commit()

    response = await _post(client, {"action": "confirm", "base_version": 1})

    assert response.status_code == 409, response.text
    body = response.json()
    assert body["error"]["code"] == "VERSION_CONFLICT"
    assert body["current_state"]["id"] == ITEM_ID
    assert await _action_count(factory) == 1
