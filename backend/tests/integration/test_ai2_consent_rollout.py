from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from contract_intelligence.contract.infrastructure.persistence.orm import DossierORM
from contract_intelligence.main import app
from contract_intelligence.shared.audit import AuditEventORM
from contract_intelligence.shared.auth import AuthenticatedUser, get_current_user
from contract_intelligence.shared.persistence import Base
from contract_intelligence.shared.persistence.orm_registry import import_all_models
from contract_intelligence.shared.persistence.session import get_async_session

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from backfill_ai2_content_sharing_consent import (
    apply_rollout,
    preview_rollback,
    rollback_rollout,
)

pytestmark = pytest.mark.integration
PG_URL = os.environ.get("CI_TEST_POSTGRES_URL", "")


@pytest_asyncio.fixture
async def session_factory(tmp_path):
    import_all_models()
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'consent.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        session.add_all(
            [
                DossierORM(
                    id="d-false",
                    tenant_id="t",
                    name="private",
                    metadata_json={"ai2_content_sharing_consent": False},
                ),
                DossierORM(
                    id="d-false-stable",
                    tenant_id="t",
                    name="private",
                    metadata_json={"ai2_content_sharing_consent": False},
                ),
                DossierORM(id="d-missing", tenant_id="t", name="private", metadata_json={}),
                DossierORM(
                    id="d-null",
                    tenant_id="t",
                    name="private",
                    metadata_json={"ai2_content_sharing_consent": None},
                ),
                DossierORM(
                    id="d-true",
                    tenant_id="t",
                    name="private",
                    metadata_json={"ai2_content_sharing_consent": True},
                ),
                DossierORM(
                    id="d-malformed",
                    tenant_id="t",
                    name="private",
                    metadata_json={"ai2_content_sharing_consent": "unknown"},
                ),
                DossierORM(
                    id="d-deleted",
                    tenant_id="t",
                    name="private",
                    deleted_at=datetime.now(UTC),
                    metadata_json={},
                ),
                DossierORM(
                    id="d-purged",
                    tenant_id="t",
                    name="private",
                    purge_status="purged",
                    purge_completed_at=datetime.now(UTC),
                    metadata_json={},
                ),
            ]
        )
        await session.commit()
    yield factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_dry_run_apply_is_idempotent_and_excludes_deleted_or_purged(session_factory):
    async with session_factory() as session:
        dry = await apply_rollout(session, rollout_id="r1", actor_id="operator", apply=False)
        assert dry == {"eligible": 6, "updated": 4, "skipped": 2}
        applied = await apply_rollout(session, rollout_id="r1", actor_id="operator", apply=True)
        assert applied == {"eligible": 6, "updated": 4, "skipped": 2}
        opted_out = await session.get(DossierORM, "d-false")
        opted_out.metadata_json = {**opted_out.metadata_json, "ai2_content_sharing_consent": False}
        from contract_intelligence.shared.audit import add_audit_event

        add_audit_event(
            session,
            tenant_id="t",
            actor_id="owner",
            action="ai2.content_sharing_consent_changed",
            entity_type="dossier",
            entity_id="d-false",
            dossier_id="d-false",
            from_state="true",
            to_state="false",
        )
        later_rollout = await apply_rollout(
            session, rollout_id="r2", actor_id="operator", apply=True
        )
        assert later_rollout == {"eligible": 6, "updated": 0, "skipped": 6}
        retried = await apply_rollout(session, rollout_id="r1", actor_id="operator", apply=True)
        assert retried == {"eligible": 6, "updated": 0, "skipped": 6}
        await session.commit()
        rows = (await session.scalars(select(DossierORM))).all()
        values = {
            row.id: (row.metadata_json or {}).get("ai2_content_sharing_consent") for row in rows
        }
        assert values["d-false"] is False
        assert values["d-missing"] is True
        assert values["d-null"] is True
        assert values["d-true"] is True
        assert values["d-malformed"] == "unknown"
        events = (await session.scalars(select(AuditEventORM))).all()
        assert len(events) == 5
        assert all("private" not in (event.detail or "") for event in events)


@pytest.mark.asyncio
async def test_rollback_restores_prior_false_or_absent_but_skips_user_changed_consent(
    session_factory,
):
    async with session_factory() as session:
        await apply_rollout(session, rollout_id="r2", actor_id="operator", apply=True)
        user_edit = await session.get(DossierORM, "d-false")
        user_edit.metadata_json = {**user_edit.metadata_json, "ai2_content_sharing_consent": False}
        session.add(
            AuditEventORM(
                id="user-change",
                tenant_id="t",
                occurred_at=datetime.now(UTC),
                actor_id="owner",
                action="ai2.content_sharing_consent_changed",
                entity_type="dossier",
                entity_id="d-false",
                dossier_id="d-false",
                from_state="true",
                to_state="false",
                detail=json.dumps({"source": "user"}),
            )
        )
        preview = await preview_rollback(session, rollout_id="r2")
        assert preview == {"restorable": 3, "skipped": 1}
        result = await rollback_rollout(session, rollout_id="r2", actor_id="operator")
        await session.commit()
        assert result["restored"] == 3
        assert result["skipped"] == 1
        assert (await session.get(DossierORM, "d-false")).metadata_json[
            "ai2_content_sharing_consent"
        ] is False
        assert (
            "ai2_content_sharing_consent"
            not in (await session.get(DossierORM, "d-missing")).metadata_json
        )
        assert (await session.get(DossierORM, "d-null")).metadata_json[
            "ai2_content_sharing_consent"
        ] is None
        assert (await session.get(DossierORM, "d-false-stable")).metadata_json[
            "ai2_content_sharing_consent"
        ] is False


@pytest.mark.asyncio
async def test_owner_can_toggle_with_audit_and_unrelated_operator_is_denied(session_factory):
    async with session_factory() as session:
        dossier = await session.get(DossierORM, "d-missing")
        dossier.metadata_json = {"created_by": "owner"}
        await session.commit()

    async def override_session():
        async with session_factory() as session:
            yield session
            await session.commit()

    async def owner():
        return AuthenticatedUser("owner", "t", "owner@example.test", "Owner", "OPERATOR")

    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[get_current_user] = owner
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch(
                "/api/v1/dossiers/d-missing/ai2-content-sharing-consent", json={"enabled": True}
            )
        assert response.status_code == 200
        assert response.json()["effective_from"] == "next_request"
        async with session_factory() as session:
            events = (await session.scalars(select(AuditEventORM))).all()
            assert len(events) == 1
            assert events[0].actor_id == "owner"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_audit_failure_rolls_back_consent_change(session_factory, monkeypatch):
    from contract_intelligence.contract.interfaces.api.routers import dossier_consent_router

    async with session_factory() as session:
        dossier = await session.get(DossierORM, "d-missing")
        dossier.metadata_json = {"created_by": "owner", "ai2_content_sharing_consent": False}
        await session.commit()

    async def override_session():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    def fail_audit(*args, **kwargs):
        raise RuntimeError("simulated append-only audit failure")

    async def owner():
        return AuthenticatedUser("owner", "t", "owner@example.test", "Owner", "OPERATOR")

    monkeypatch.setattr(dossier_consent_router, "add_audit_event", fail_audit)
    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[get_current_user] = owner
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
        ) as client:
            response = await client.patch(
                "/api/v1/dossiers/d-missing/ai2-content-sharing-consent", json={"enabled": True}
            )
        assert response.status_code == 500
        async with session_factory() as session:
            dossier = await session.get(DossierORM, "d-missing")
            assert dossier.metadata_json["ai2_content_sharing_consent"] is False
            assert list((await session.scalars(select(AuditEventORM))).all()) == []
    finally:
        app.dependency_overrides.clear()

    async def stranger():
        return AuthenticatedUser("stranger", "t", "stranger@example.test", "Stranger", "OPERATOR")

    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[get_current_user] = stranger
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch(
                "/api/v1/dossiers/d-missing/ai2-content-sharing-consent", json={"enabled": False}
            )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
@pytest.mark.skipif(not PG_URL, reason="CI_TEST_POSTGRES_URL not set")
async def test_postgres_rollback_waits_for_opt_out_and_never_overwrites_it():
    backend_dir = Path(__file__).resolve().parents[2]
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env={**os.environ, "DATABASE_URL": PG_URL},
        check=True,
    )
    engine = create_async_engine(PG_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    dossier_id = f"consent-race-{datetime.now(UTC).timestamp()}"
    rollout_id = f"race-{dossier_id}"
    async with factory.begin() as session:
        session.add(
            DossierORM(id=dossier_id, tenant_id="consent-race", name="race", metadata_json={})
        )
    async with factory() as session:
        await apply_rollout(session, rollout_id=rollout_id, actor_id="operator", apply=True)
        await session.commit()

    locked = asyncio.Event()
    release = asyncio.Event()

    async def user_opt_out():
        async with factory.begin() as session:
            dossier = await session.scalar(
                select(DossierORM).where(DossierORM.id == dossier_id).with_for_update()
            )
            dossier.metadata_json = {**dossier.metadata_json, "ai2_content_sharing_consent": False}
            from contract_intelligence.shared.audit import add_audit_event

            add_audit_event(
                session,
                tenant_id="consent-race",
                actor_id="owner",
                action="ai2.content_sharing_consent_changed",
                entity_type="dossier",
                entity_id=dossier_id,
                dossier_id=dossier_id,
                from_state="true",
                to_state="false",
            )
            locked.set()
            await release.wait()

    async def rollback():
        await locked.wait()
        async with factory.begin() as session:
            return await rollback_rollout(session, rollout_id=rollout_id, actor_id="operator")

    user_task = asyncio.create_task(user_opt_out())
    rollback_task = asyncio.create_task(rollback())
    await locked.wait()
    await asyncio.sleep(0.05)
    release.set()
    await user_task
    result = await rollback_task
    async with factory() as session:
        dossier = await session.get(DossierORM, dossier_id)
        assert dossier.metadata_json["ai2_content_sharing_consent"] is False
        assert result["skipped"] >= 1
    await engine.dispose()
