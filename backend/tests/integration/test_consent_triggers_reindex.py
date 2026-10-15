"""Turning AI2 consent on rebuilds the dossier in AI2 when its last run has finished."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from contract_intelligence.contract.infrastructure.persistence.orm import DossierORM, JobORM
from contract_intelligence.infrastructure import messaging
from contract_intelligence.main import app
from contract_intelligence.shared.audit import AuditEventORM
from contract_intelligence.shared.auth import AuthenticatedUser, get_current_user
from contract_intelligence.shared.persistence import Base
from contract_intelligence.shared.persistence.orm_registry import import_all_models
from contract_intelligence.shared.persistence.session import get_async_session

pytestmark = pytest.mark.integration

DOSSIER = "d-1"
RUN = "run-1"
PATH = f"/api/v1/dossiers/{DOSSIER}/ai2-content-sharing-consent"


@pytest_asyncio.fixture
async def factory(tmp_path: Path) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    import_all_models()
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'consent.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield session_factory
    await engine.dispose()


async def _seed(
    factory: async_sessionmaker[AsyncSession],
    *,
    consent: Any = "absent",
    job_status: str | None = "pending_review",
    run_id: str | None = RUN,
) -> None:
    metadata: dict[str, Any] = {"created_by": "owner"}
    if consent != "absent":
        metadata["ai2_content_sharing_consent"] = consent
    async with factory() as session:
        session.add(DossierORM(id=DOSSIER, tenant_id="t", name="hd", metadata_json=metadata))
        if job_status is not None:
            session.add(
                JobORM(
                    id="j-1",
                    tenant_id="t",
                    dossier_id=DOSSIER,
                    status=job_status,
                    current_run_id=run_id,
                )
            )
        await session.commit()


@pytest_asyncio.fixture
async def client(factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncClient]:
    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def owner() -> AuthenticatedUser:
        return AuthenticatedUser("owner", "t", "owner@example.test", "Owner", "OPERATOR")

    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[get_current_user] = owner
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.clear()


async def _audit_actions(factory: async_sessionmaker[AsyncSession]) -> list[str]:
    async with factory() as session:
        return sorted(e.action for e in (await session.scalars(select(AuditEventORM))).all())


async def test_enabling_consent_queues_a_reindex_after_the_consent_is_committed(
    factory: async_sessionmaker[AsyncSession], client: AsyncClient
) -> None:
    await _seed(factory)
    seen_at_publish: list[Any] = []

    async def publish(topic: str, message: dict[str, Any], **_: Any) -> None:
        # What the worker would read the moment it gets the event.
        async with factory() as session:
            dossier = await session.get(DossierORM, DOSSIER)
            seen_at_publish.append(dossier.metadata_json.get("ai2_content_sharing_consent"))

    messaging.publish_event.reset_mock()
    messaging.publish_event.side_effect = publish
    try:
        response = await client.patch(PATH, json={"enabled": True})
    finally:
        messaging.publish_event.side_effect = None

    assert response.status_code == 200
    assert response.json()["ai2_reindex_queued"] is True
    messaging.publish_event.assert_awaited_once_with(
        "dossier_events",
        {"event": "dossier.ai2.reindex", "dossier_id": DOSSIER, "run_id": RUN},
    )
    assert seen_at_publish == [True]
    assert await _audit_actions(factory) == [
        "ai2.content_sharing_consent_changed",
        "ai2.reindex_on_consent",
    ]


@pytest.mark.parametrize(
    ("job_status", "run_id"),
    [("ocr_running", RUN), ("failed", RUN), ("pending_review", None), (None, None)],
)
async def test_no_reindex_while_ai2_has_not_finished_the_run(
    factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    job_status: str | None,
    run_id: str | None,
) -> None:
    await _seed(factory, job_status=job_status, run_id=run_id)
    messaging.publish_event.reset_mock()

    response = await client.patch(PATH, json={"enabled": True})

    assert response.status_code == 200
    assert response.json()["ai2_reindex_queued"] is False
    messaging.publish_event.assert_not_awaited()
    assert await _audit_actions(factory) == ["ai2.content_sharing_consent_changed"]


@pytest.mark.parametrize(("consent", "enabled"), [(True, True), (True, False), (False, False)])
async def test_no_reindex_unless_consent_turns_on(
    factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    consent: bool,
    enabled: bool,
) -> None:
    await _seed(factory, consent=consent)
    messaging.publish_event.reset_mock()

    response = await client.patch(PATH, json={"enabled": enabled})

    assert response.status_code == 200
    assert response.json()["ai2_reindex_queued"] is False
    messaging.publish_event.assert_not_awaited()


async def test_a_broker_failure_keeps_the_consent_and_says_nothing_was_queued(
    factory: async_sessionmaker[AsyncSession], client: AsyncClient
) -> None:
    await _seed(factory)
    messaging.publish_event.reset_mock()
    messaging.publish_event.side_effect = ConnectionError("kafka down")
    try:
        response = await client.patch(PATH, json={"enabled": True})
    finally:
        messaging.publish_event.side_effect = None

    assert response.status_code == 200
    assert response.json()["ai2_reindex_queued"] is False
    async with factory() as session:
        dossier = await session.get(DossierORM, DOSSIER)
        assert dossier.metadata_json["ai2_content_sharing_consent"] is True
