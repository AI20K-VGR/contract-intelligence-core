"""API Backend + PostgreSQL thật; nhãn synthetic chỉ kiểm chứng cơ chế."""

from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tests.integration.test_clause_frame_roundtrip import (
    TENANT,
    ai_http as ai_http,
    poll,
    request_fixture,
)

from contract_intelligence.conflict.infrastructure.persistence.orm import FindingORM, FindingSideORM
from contract_intelligence.contract.infrastructure.persistence.orm import (
    DocumentORM,
    DossierORM,
    JobORM,
)
from contract_intelligence.extraction.infrastructure.persistence.orm import (
    OcrLineORM,
    PipelineRunORM,
)
from contract_intelligence.main import app
from contract_intelligence.shared.ai.persistence import persist_ai2_processing_result
from contract_intelligence.shared.auth import AuthenticatedUser, get_current_user
from contract_intelligence.shared.auth.tenant import get_tenant_id
from contract_intelligence.shared.persistence import Base
from contract_intelligence.shared.persistence.orm_registry import import_all_models
from contract_intelligence.shared.persistence.session import get_async_session


def semantic_reviewer(tenant: str = TENANT, role: str = "REVIEWER") -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="semantic-reviewer",
        tenant_id=tenant,
        email="reviewer@example.test",
        display_name="Reviewer synthetic",
        role=role,
    )


async def seed_semantic_run(
    factory: async_sessionmaker[AsyncSession], request: dict[str, Any], result: dict[str, Any]
) -> None:
    """Được P6 dùng lại; pin đúng current run và persisted result, không cache."""
    dossier_id, run_id = request["dossier_id"], request["task_id"]
    async with factory() as session:
        session.add(
            DossierORM(
                id=dossier_id,
                tenant_id=TENANT,
                name="Synthetic semantic review",
                metadata_json={"created_by": "semantic-reviewer"},
            )
        )
        await session.flush()
        session.add(
            JobORM(
                id=f"job-{run_id}", tenant_id=TENANT, dossier_id=dossier_id, current_run_id=run_id
            )
        )
        await session.flush()
        session.add(
            PipelineRunORM(
                id=run_id,
                tenant_id=TENANT,
                dossier_id=dossier_id,
                job_id=f"job-{run_id}",
                status="running",
                pipeline_version="test-v1",
                config_snapshot=json.dumps({"semantic_profile": request["semantic_profile"]}),
            )
        )
        for member in request["dossier_members"]:
            session.add(
                DocumentORM(
                    id=member["document_id"],
                    tenant_id=TENANT,
                    dossier_id=dossier_id,
                    role="CONTRACT" if member["role"] == "body" else "ANNEX",
                    filename="synthetic.pdf",
                    sha256=member["source_digest"],
                )
            )
        for snapshot in request["snapshots"]:
            offset = 0
            for page in snapshot["pages"]:
                for line_no, line in enumerate(page["lines"]):
                    raw = line["raw_text"]
                    session.add(
                        OcrLineORM(
                            id=f"ocr-{snapshot['document_id']}-{line_no}",
                            tenant_id=TENANT,
                            document_id=snapshot["document_id"],
                            page_no=1,
                            line_no=line_no,
                            text=raw,
                            bbox="[]",
                            confidence=None,
                            doc_char_start=offset,
                            doc_char_end=offset + len(raw),
                        )
                    )
                    offset += len(raw) + 1
        await session.commit()
        await persist_ai2_processing_result(
            session, tenant_id=TENANT, dossier_id=dossier_id, result=result, run_id=run_id
        )
        await session.commit()


@asynccontextmanager
async def semantic_route_client(
    factory: async_sessionmaker[AsyncSession], user: AuthenticatedUser | None = None
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async def session_override() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_async_session] = session_override
    app.dependency_overrides[get_tenant_id] = lambda: TENANT
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    else:
        app.dependency_overrides.pop(get_current_user, None)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://backend.test"
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


@pytest_asyncio.fixture
async def semantic_case(
    ai_http: Any,
) -> AsyncGenerator[tuple[async_sessionmaker[AsyncSession], dict[str, Any], dict[str, Any]], None]:
    base, _, raw = ai_http
    request = request_fixture()
    response = httpx.post(base + "/jobs/idp", json=request, timeout=10)
    assert response.status_code == 202, response.text
    result = poll(base, request, response.json()["job_id"])
    assert result["status"] == "SUCCEEDED"
    import_all_models()
    engine = create_async_engine(
        make_url(raw).set(drivername="postgresql+asyncpg"), hide_parameters=True
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    await seed_semantic_run(factory, request, result)
    try:
        yield factory, request, result
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_persisted_semantics_query_review_acl_and_current_run(semantic_case: Any) -> None:
    factory, request, result = semantic_case
    dossier, run = request["dossier_id"], request["task_id"]
    route = f"/api/v1/dossiers/{dossier}/semantic-results"
    async with semantic_route_client(factory, semantic_reviewer()) as client:
        response = await client.get(route)
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["run_id"] == run
        assert data["semantic_extension"] == result["result"]["semantic_extension"]
        assert data["state"] == "NEEDS_REVIEW"
        query = await client.post(
            f"/api/v1/dossiers/{dossier}/query", json={"query": "9007199254740993"}
        )
        assert query.status_code == 200, query.text
        assert query.json()["state"] == "NEEDS_REVIEW"
        assert query.json()["retrieval_layer"]["run_id"] == run
        assert "9007199254740993" in query.json()["answer"]
        conflicts = await client.get(f"/api/v1/dossiers/{dossier}/conflicts")
        assert conflicts.status_code == 200
        semantic = [f for f in conflicts.json()["data"] if f.get("semantic")]
        assert semantic
        finding = semantic[0]
        assert len(finding["sides"]) == 2
        assert finding["semantic"]["review_state"] == "NEEDS_REVIEW"
        item_id = finding["review"]["item_id"]
        version = finding["review"]["current_version"]
        accepted = await client.post(
            f"/api/v1/review-items/{item_id}/actions",
            json={"action": "needs_more_evidence", "base_version": version},
            headers={"Idempotency-Key": "semantic-review-first"},
        )
        assert accepted.status_code == 200, accepted.text
        stale = await client.post(
            f"/api/v1/review-items/{item_id}/actions",
            json={"action": "confirm", "base_version": version},
            headers={"Idempotency-Key": "semantic-review-stale"},
        )
        assert stale.status_code == 409
        assert (await client.get(route)).json()["data"]["semantic_extension"] == data[
            "semantic_extension"
        ]
    async with semantic_route_client(factory, semantic_reviewer("other-tenant")) as client:
        assert (await client.get(route)).status_code == 403
    async with semantic_route_client(factory) as client:
        assert (await client.get(route)).status_code == 401
    async with factory() as session:
        job = await session.scalar(select(JobORM).where(JobORM.dossier_id == dossier))
        pending = run + "-pending"
        session.add(
            PipelineRunORM(
                id=pending,
                tenant_id=TENANT,
                dossier_id=dossier,
                job_id=job.id,
                status="running",
                pipeline_version="test-v1",
            )
        )
        job.current_run_id = pending
        await session.commit()
    async with semantic_route_client(factory, semantic_reviewer()) as client:
        pending_result = (await client.get(route)).json()["data"]
        assert pending_result["run_id"] == pending
        assert pending_result["state"] == "NOT_READY"
        assert pending_result["semantic_extension"] is None
        query = await client.post(
            f"/api/v1/dossiers/{dossier}/query", json={"query": "9007199254740993"}
        )
        assert query.json()["state"] == "BLOCKED"
        assert "9007199254740993" not in query.json()["answer"]


@pytest.mark.asyncio
async def test_semantic_scope_variants_are_reviewable_and_read_only_cannot_correct(
    semantic_case: Any,
) -> None:
    factory, request, _ = semantic_case
    dossier = request["dossier_id"]
    async with factory() as session:
        findings = list(
            (
                await session.scalars(select(FindingORM).where(FindingORM.dossier_id == dossier))
            ).all()
        )
        target = (
            next(f for f in findings if f.key_or_topic.startswith("pair-"))
            if any(f.key_or_topic.startswith("pair-") for f in findings)
            else findings[0]
        )
        sides = list(
            (
                await session.scalars(
                    select(FindingSideORM).where(FindingSideORM.finding_id == target.id)
                )
            ).all()
        )
        pair_sides = [
            s
            for s in sides
            if isinstance(json.loads(s.value_snapshot or "{}"), dict)
            and json.loads(s.value_snapshot or "{}").get("semantic", {}).get("pair")
        ]
        if not pair_sides:
            for finding in findings:
                candidate_sides = list(
                    (
                        await session.scalars(
                            select(FindingSideORM).where(FindingSideORM.finding_id == finding.id)
                        )
                    ).all()
                )
                if any(
                    json.loads(s.value_snapshot or "{}").get("semantic", {}).get("pair")
                    for s in candidate_sides
                ):
                    target, pair_sides = finding, candidate_sides
                    break
        assert pair_sides
        target.disposition = "not_comparable"
        target.confidence = "0.99"
        for side in pair_sides:
            payload = json.loads(side.value_snapshot)
            payload["semantic"]["pair"]["disposition"] = "SCOPE_DIFFERS"
            payload["semantic"]["pair"]["reason"] = "synthetic_scope_difference"
            side.value_snapshot = json.dumps(payload, ensure_ascii=False)
        dossier_row = await session.get(DossierORM, dossier)
        dossier_row.metadata_json = {
            "created_by": "semantic-reviewer",
            "shared_with": [{"id": "read-only-user", "roles": ["REVIEWER"], "permission": "read"}],
        }
        await session.commit()
    async with semantic_route_client(factory, semantic_reviewer()) as client:
        response = await client.get(f"/api/v1/dossiers/{dossier}/conflicts")
        assert response.status_code == 200, response.text
        scope = next(f for f in response.json()["data"] if f["id"] == target.id)
        assert scope["semantic"]["disposition"] == "SCOPE_DIFFERS"
        assert scope["semantic"]["reason"] == "synthetic_scope_difference"
        assert scope["semantic"]["review_state"] == "NEEDS_REVIEW"
        assert len(scope["sides"]) == 2
        assert scope["sides"][0]["semantic"]["frame"]["slots"]
        filtered = await client.get(
            f"/api/v1/dossiers/{dossier}/findings?disposition=SCOPE_DIFFERS"
        )
        assert filtered.status_code == 200
        assert [row["id"] for row in filtered.json()["data"]] == [target.id]
        item_id = scope["review"]["item_id"]
    reader = AuthenticatedUser(
        user_id="read-only-user",
        tenant_id=TENANT,
        role="REVIEWER",
        email="readonly@example.test",
        display_name="Read-only",
    )
    async with semantic_route_client(factory, reader) as client:
        assert (await client.get(f"/api/v1/dossiers/{dossier}/semantic-results")).status_code == 200
        rejected = await client.post(
            f"/api/v1/review-items/{item_id}/actions",
            json={"action": "confirm", "base_version": scope["review"]["current_version"]},
            headers={"Idempotency-Key": "readonly-denied"},
        )
        assert rejected.status_code == 403


@pytest.mark.asyncio
async def test_semantic_read_rejects_tampered_source_and_digest(semantic_case: Any) -> None:
    factory, request, result = semantic_case
    route = f"/api/v1/dossiers/{request['dossier_id']}/semantic-results"
    async with factory() as session:
        run = await session.get(PipelineRunORM, request["task_id"])
        payload = json.loads(run.ai2_result_json)
        payload["result"]["semantic_extension"]["frames"][0]["evidence"][0]["document_id"] = (
            "outside-dossier"
        )
        run.ai2_result_json = json.dumps(payload)
        run.ai2_result_digest = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        await session.commit()
    async with semantic_route_client(factory, semantic_reviewer()) as client:
        invalid = await client.get(route)
        assert invalid.status_code == 409
        assert invalid.json()["detail"]["code"] == "SEMANTIC_RESULT_INVALID"
    async with factory() as session:
        run = await session.get(PipelineRunORM, request["task_id"])
        run.ai2_result_json = json.dumps(result)
        run.ai2_result_digest = "0" * 64
        await session.commit()
    async with semantic_route_client(factory, semantic_reviewer()) as client:
        assert (await client.get(route)).status_code == 409
