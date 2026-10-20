"""Governance checked against a disposable PostgreSQL; no SQLite CAS substitute."""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from contract_intelligence.shared.ai.tenant_lexicon_contracts import (
    ActivationPolicy,
    LexiconCommand,
)
from contract_intelligence.shared.ai.tenant_lexicon_service import (
    ApprovedLabelMeasurementReader,
    LexiconError,
    TenantLexiconService,
)
from contract_intelligence.shared.ai.tenant_lexicon_store import LEXICON_TABLES, AliasProposalORM
from contract_intelligence.shared.auth.schemas import AuthenticatedUser
from contract_intelligence.shared.persistence import Base


def user(actor="admin", tenant="tenant-a", role="ADMINISTRATOR"):
    return AuthenticatedUser(
        user_id=actor,
        tenant_id=tenant,
        role=role,
        email=f"{actor}@test.example",
        display_name=actor,
    )


def command(action, version, key, **payload):
    return LexiconCommand(action=action, base_version=version, idempotency_key=key, payload=payload)


def migrate(connection, direction):
    spec = importlib.util.spec_from_file_location(
        "lexicon_migration", Path(__file__).parents[2] / "alembic/versions/v21__tenant_lexicon.py"
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with Operations.context(MigrationContext.configure(connection)):
        getattr(migration, direction)()


@pytest_asyncio.fixture
async def database():
    url = os.environ.get("LEXICON_TEST_DATABASE_URL")
    if not url:
        pytest.fail("LEXICON_TEST_DATABASE_URL phải trỏ tới PostgreSQL dùng riêng cho test")
    engine = create_async_engine(url)
    if engine.dialect.name != "postgresql":
        pytest.fail("Governance CAS cần PostgreSQL")
    async with engine.begin() as connection:
        await connection.run_sync(lambda conn: Base.metadata.drop_all(conn, tables=LEXICON_TABLES))
        await connection.execute(text("DROP FUNCTION IF EXISTS tenant_lexicon_immutable()"))
        await connection.run_sync(lambda conn: migrate(conn, "upgrade"))
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    async with engine.begin() as connection:
        await connection.run_sync(lambda conn: migrate(conn, "downgrade"))
    await engine.dispose()


async def execute(database, actor, cmd, tenant="tenant-a"):
    async with database() as session:
        return await TenantLexiconService(session).execute(tenant, actor, cmd)


async def designate(database, version=0, expires=None):
    return await execute(
        database,
        user(),
        command(
            "ASSIGN",
            version,
            "assignment",
            expert_id="expert",
            expertise_ref="attestation-1",
            expires_at=(expires or datetime.now(UTC) + timedelta(days=1)).isoformat(),
        ),
    )


async def propose(database, version=1, key="proposal", source="trả tiền", symbol="PAY"):
    return await execute(
        database,
        user("operator", role="OPERATOR"),
        command(
            "PROPOSE",
            version,
            key,
            source=source,
            symbol=symbol,
            kind="action",
            source_ref="abstract-source-1",
        ),
    )


async def test_named_expert_draft_only_history_retry_and_restart(database):
    assert (await designate(database))["version"] == 1
    proposal = await propose(database)
    cmd = command("APPROVE", 2, "approve", proposal_id=proposal["proposal_id"])
    with pytest.raises(LexiconError) as denied:
        await execute(database, user(), cmd)
    assert denied.value.status == 403
    receipt = await execute(database, user("expert", role="REVIEWER"), cmd)
    assert receipt["version"] == 3
    assert receipt["activation_state"] == "DRAFT_ONLY"
    assert receipt == await execute(database, user("expert", role="REVIEWER"), cmd)
    with pytest.raises(LexiconError) as conflict:
        await execute(
            database,
            user("expert", role="REVIEWER"),
            command("REJECT", 2, "approve", proposal_id=proposal["proposal_id"]),
        )
    assert conflict.value.status == 409
    async with database() as session:
        service = TenantLexiconService(session)
        current = await service.read_profile("tenant-a", user("expert", role="REVIEWER"))
        assert current["version"] == 3
        assert current["active_aliases"] == []
        assert current["aliases"][0]["method"] == "TENANT_ALIAS"
    await execute(
        database,
        user("expert", role="REVIEWER"),
        command("REVOKE", 3, "revoke", proposal_id=proposal["proposal_id"]),
    )
    async with database() as session:
        service = TenantLexiconService(session)
        assert (await service.read_profile("tenant-a", user(), version=3))["aliases"]
        assert (await service.read_profile("tenant-a", user()))["aliases"] == []


async def test_scope_expiry_and_operator_cannot_approve(database):
    await designate(database, expires=datetime.now(UTC) - timedelta(seconds=1))
    proposal = await propose(database)
    for actor in (
        user("expert", role="REVIEWER"),
        user("operator", role="OPERATOR"),
        user("expert", tenant="tenant-b", role="REVIEWER"),
    ):
        with pytest.raises(LexiconError) as denied:
            await execute(
                database,
                actor,
                command("APPROVE", 2, actor.user_id, proposal_id=proposal["proposal_id"]),
            )
        assert denied.value.status == 403


async def test_concurrent_cas_has_one_receipt(database):
    await designate(database)
    proposal = await propose(database)

    async def race(action, key):
        try:
            return await execute(
                database,
                user("expert", role="REVIEWER"),
                command(action, 2, key, proposal_id=proposal["proposal_id"]),
            )
        except LexiconError as exc:
            return exc.status

    results = await asyncio.gather(race("APPROVE", "race-a"), race("REJECT", "race-b"))
    assert sum(isinstance(result, dict) for result in results) == 1
    assert 409 in results


@pytest.mark.parametrize(
    "source,symbol",
    [("trả", "PAY"), ("thực hiện", "PERFORM"), ("trả tiền", "INVENTED"), ("raw\ncontract", "PAY")],
)
async def test_invalid_proposal_rejected(database, source, symbol):
    await designate(database)
    with pytest.raises(LexiconError) as invalid:
        await propose(database, source=source, symbol=symbol)
    assert invalid.value.status == 422


async def test_collision_and_promotion_default_deny(database):
    await designate(database)
    first = await propose(database)
    await execute(
        database,
        user("expert", role="REVIEWER"),
        command("APPROVE", 2, "a", proposal_id=first["proposal_id"]),
    )
    second = await propose(database, version=3, key="proposal-b", symbol="DELIVER")
    with pytest.raises(LexiconError) as collision:
        await execute(
            database,
            user("expert", role="REVIEWER"),
            command("APPROVE", 4, "b", proposal_id=second["proposal_id"]),
        )
    assert collision.value.status == 409
    with pytest.raises(LexiconError) as promotion:
        await execute(
            database, user(), command("PROMOTE", 4, "promotion", proposal_id=first["proposal_id"])
        )
    assert promotion.value.status == 403


async def test_frozen_policy_independent_errors_zero_denominator_and_expired_editor(
    database, tmp_path
):
    await designate(database)
    first = await propose(database)
    await execute(
        database,
        user("expert", role="REVIEWER"),
        command("APPROVE", 2, "a", proposal_id=first["proposal_id"]),
    )
    measurement = {
        "proposal_id": first["proposal_id"],
        "errors": 0,
        "denominator": 0,
        "labels_ref": "independently-reviewed-labels",
    }
    with pytest.raises(LexiconError) as denied:
        await execute(
            database, user("expert", role="REVIEWER"), command("MEASURE", 3, "m", **measurement)
        )
    assert denied.value.status == 403
    await execute(
        database,
        user(),
        command(
            "ASSIGN",
            3,
            "assign-evaluator",
            expert_id="evaluator",
            expertise_ref="expertise-evaluator",
            expires_at=(datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        ),
    )
    policy = ActivationPolicy(
        policy_digest="f" * 64,
        minimum_length=4,
        revoke_error_rate=0.05,
        assignment_sla_ref="sla",
        backlog_policy_ref="backlog",
        activation_review_ref="owner-freeze",
        promotion_consent_text_ref="consent-text",
    )
    async with database() as session:
        receipt = await TenantLexiconService(session, policy).execute(
            "tenant-a",
            user("evaluator", role="REVIEWER"),
            command("MEASURE", 4, "zero", **measurement),
        )
    assert receipt["activation_state"] == "DRAFT_ONLY"
    measurement["denominator"] = 20
    async with database() as session:
        receipt = await TenantLexiconService(session, policy).execute(
            "tenant-a",
            user("evaluator", role="REVIEWER"),
            command("MEASURE", 5, "nonzero", **measurement),
        )
    # Client counts/ref never activate, even with a trusted frozen policy.
    assert receipt["activation_state"] == "DRAFT_ONLY"
    artifact = {
        "schema_version": "tenant_alias.labels.v1",
        "status": "APPROVED",
        "tenant_id": "tenant-a",
        "proposal_id": first["proposal_id"],
        "proposal_version": 2,
        "source": "trả tiền",
        "kind": "action",
        "symbol": "PAY",
        "producer_id": "operator",
        "reviewer_id": "evaluator",
        "approval_ref": "synthetic-test-approval",
        "labels": [
            {
                "unit_id": f"u-{i}",
                "expected_symbol": "PAY",
                "source_ref": f"source-{i}",
                "source_digest": "a" * 64,
            }
            for i in range(20)
        ],
    }
    raw = json.dumps(artifact, ensure_ascii=False).encode()
    digest = hashlib.sha256(raw).hexdigest()
    (tmp_path / f"{digest}.json").write_bytes(raw)
    reader = ApprovedLabelMeasurementReader(tmp_path)
    measurement.update(labels_ref=digest, errors=19, denominator=20)
    async with database() as session:
        receipt = await TenantLexiconService(session, policy, reader).execute(
            "tenant-a",
            user("evaluator", role="REVIEWER"),
            command("MEASURE", 6, "verified-bytes", **measurement),
        )
    assert receipt["activation_state"] == "ACTIVE"
    async with database() as session:
        profile = await TenantLexiconService(session, policy).read_profile("tenant-a", user())
        ledger = profile["measurements"][first["proposal_id"]]
        assert ledger["errors"] == 0  # Computed from bytes, not supplied 19.
        assert ledger["denominator"] == 20
        assert ledger["labels_digest"] == digest
        assert ledger["verified"] is True
    async with database() as session:
        snapshot = await TenantLexiconService(session, policy).resolve_for_run("tenant-a")
    assert snapshot["aliases"][0]["symbol"] == "PAY"
    async with database() as session:
        await TenantLexiconService(session, policy, reader).execute(
            "tenant-a",
            user(),
            command("OPT_IN", 7, "consent", enabled=True, consent_ref="owner-consent"),
        )
    async with database() as session:
        promoted = await TenantLexiconService(session, policy, reader).execute(
            "tenant-a",
            user(),
            command("PROMOTE", 8, "approved-promotion", proposal_id=first["proposal_id"]),
        )
        assert promoted["abstract_alias"] == {
            "source": "trả tiền",
            "symbol": "PAY",
            "kind": "action",
        }
    async with database() as session:
        await TenantLexiconService(session, policy).execute(
            "tenant-a",
            user(),
            command(
                "ASSIGN",
                9,
                "expired",
                expert_id="evaluator",
                expertise_ref="expertise",
                expires_at=(datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
            ),
        )
    async with database() as session:
        assert (await TenantLexiconService(session, policy).resolve_for_run("tenant-a"))[
            "aliases"
        ] == []
    async with database() as session:
        assert (
            await TenantLexiconService(session, policy).read_profile("tenant-a", user(), version=7)
        )["active_aliases"]
    with pytest.raises(LexiconError) as denied:
        async with database() as session:
            await TenantLexiconService(session, policy, reader).execute(
                "tenant-a",
                user(),
                command("PROMOTE", 10, "expired-promotion", proposal_id=first["proposal_id"]),
            )
    assert denied.value.status == 403

    # Tampered bytes and caller-controlled path references never verify.
    (tmp_path / f"{digest}.json").write_bytes(raw + b" ")
    async with database() as session:
        proposal_record = await session.get(
            AliasProposalORM,
            ("tenant-a", first["proposal_id"]),
        )
        assert reader.resolve("tenant-a", proposal_record, "evaluator", "expert", digest) is None
        assert (
            reader.resolve("tenant-a", proposal_record, "evaluator", "expert", "../private") is None
        )


async def test_database_rejects_history_updates_and_deletes(database):
    await designate(database)
    for sql in (
        "UPDATE tenant_lexicon_version SET digest='rewritten'",
        "DELETE FROM tenant_lexicon_audit",
    ):
        with pytest.raises(DBAPIError):
            async with database() as session, session.begin():
                await session.execute(text(sql))


async def test_downgrade_reupgrade_preserves_history_and_rejects_schema_drift(database):
    await designate(database)
    engine = database.kw["bind"]
    async with engine.begin() as connection:
        await connection.run_sync(lambda conn: migrate(conn, "downgrade"))
        await connection.run_sync(lambda conn: migrate(conn, "upgrade"))
    async with database() as session:
        assert (await TenantLexiconService(session).read_profile("tenant-a", user()))[
            "version"
        ] == 1
    with pytest.raises(DBAPIError):
        async with database() as session, session.begin():
            await session.execute(text("DELETE FROM tenant_lexicon_assignment"))
    with pytest.raises(RuntimeError, match="schema mismatch"):
        async with engine.begin() as connection:
            await connection.execute(
                text("ALTER TABLE tenant_lexicon_head ALTER COLUMN version TYPE TEXT")
            )
            await connection.run_sync(lambda conn: migrate(conn, "upgrade"))


async def test_authenticated_http_tenant_and_role_denials(database, make_keycloak_token):
    from httpx import ASGITransport, AsyncClient

    from contract_intelligence.main import app
    from contract_intelligence.shared.persistence.session import get_async_session

    async def session_dependency():
        async with database() as session:
            yield session

    app.dependency_overrides[get_async_session] = session_dependency
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            path = "/api/v1/tenants/tenant-a/lexicon"
            assert (await client.get(path)).status_code == 401
            token = make_keycloak_token(user_id="operator", tenant_id="tenant-a", role="OPERATOR")
            headers = {"Authorization": f"Bearer {token}"}
            assert (await client.get(path, headers=headers)).status_code == 200
            assert (
                await client.get(path.replace("tenant-a", "tenant-b"), headers=headers)
            ).status_code == 403
            cmd = command(
                "ASSIGN",
                0,
                "http-assign",
                expert_id="expert",
                expertise_ref="attestation",
                expires_at=(datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            )
            assert (
                await client.post(
                    path + "/commands", headers=headers, json=cmd.model_dump(mode="json")
                )
            ).status_code == 403
            headers["Authorization"] = "Bearer " + make_keycloak_token(
                user_id="admin", tenant_id="tenant-a", role="ADMINISTRATOR"
            )
            response = await client.post(
                path + "/commands", headers=headers, json=cmd.model_dump(mode="json")
            )
            assert response.status_code == 200
            assert response.json()["data"]["activation_state"] == "DRAFT_ONLY"
            admin_metadata = (await client.get(path, headers=headers)).json()["metadata"]
            assert admin_metadata["assignment"]["expert_id"] == "expert"
            assert admin_metadata["permissions"]["can_assign"] is True
            assert admin_metadata["permissions"]["can_approve"] is False
            expert_headers = {
                "Authorization": "Bearer "
                + make_keycloak_token(user_id="expert", tenant_id="tenant-a", role="REVIEWER")
            }
            expert_metadata = (await client.get(path, headers=expert_headers)).json()["metadata"]
            assert expert_metadata["permissions"]["can_approve"] is True
            assert expert_metadata["permissions"]["can_propose"] is False
            assert expert_metadata["permissions"]["can_promote"] is False
            assert (
                await client.post(
                    path + "/commands",
                    headers=headers,
                    json={**cmd.model_dump(mode="json"), "activate": True},
                )
            ).status_code == 422
    finally:
        app.dependency_overrides.pop(get_async_session, None)
