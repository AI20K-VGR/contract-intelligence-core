"""Regression coverage for the FE-reported backend gaps (sqlite, offline).

- AI2 result → every finding queued as ReviewItem, job/dossier → pending_review, audit
- AI2 failure → job/dossier/run failed + audit
- dispatcher HTTP poll branch persists + audits instead of only logging
- ``/query`` + ``/ask`` persist QueryTrace in the DB, quota → 429, second ACL pass
"""

from __future__ import annotations

import copy
import json
from collections.abc import AsyncGenerator, Iterator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tests.integration.test_ai2_review_fixes_flow import (
    BODY_DOCUMENT_ID,
    DOSSIER_ID,
    OPERATOR,
    RUN_ID,
    SNAPSHOT_DIGEST,
    TENANT_ID,
    _processing_result,
    _seed_dossier,
)

from contract_intelligence import worker
from contract_intelligence.config.settings import get_settings
from contract_intelligence.contract.infrastructure.persistence.orm import DossierORM, JobORM
from contract_intelligence.extraction.infrastructure.persistence.orm import PipelineRunORM
from contract_intelligence.main import app
from contract_intelligence.review.infrastructure.persistence.orm import ReviewItemORM
from contract_intelligence.shared.ai.dispatcher import DispatchTask, _persist_result
from contract_intelligence.shared.ai.schemas import JobStatus as AiJobStatus, JobStatusReport
from contract_intelligence.shared.audit import AuditEventORM
from contract_intelligence.shared.auth import get_current_user
from contract_intelligence.shared.auth.tenant import get_tenant_id
from contract_intelligence.shared.persistence import Base
from contract_intelligence.shared.persistence.orm_registry import import_all_models
from contract_intelligence.shared.persistence.session import get_async_session
from contract_intelligence.shared.query_policy import QueryTraceORM

_QUERY_AI2 = "contract_intelligence.api.v1.dossiers.query_ai2"


def _result_with_pass_finding() -> dict[str, Any]:
    """One NEEDS_REVIEW finding + one PASS finding that the old code never queued."""
    result = copy.deepcopy(_processing_result())
    result["result"]["findings"].append(
        {
            "finding_id": "finding-term-match",
            "item_key": "contract_value",
            "finding_type": "structured",
            "scope": "contract_annex",
            "disposition": "match",
            "reason": "Body and annex agree.",
            "review_state": "PASS",
            "evidence_left_citation_ids": ["citation-body"],
            "evidence_right_citation_ids": ["citation-annex"],
        }
    )
    return result


@pytest.fixture(autouse=True)
def _reset_worker_ai2_tasks() -> Iterator[None]:
    worker._ai2_tasks.clear()
    yield
    worker._ai2_tasks.clear()


@pytest_asyncio.fixture
async def factory(tmp_path: Any) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    import_all_models()
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'fe-fixes.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await _seed_dossier(session_factory)
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
    app.dependency_overrides[get_current_user] = lambda: OPERATOR
    app.dependency_overrides[get_tenant_id] = lambda: TENANT_ID
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def _job_and_dossier(session: AsyncSession) -> tuple[JobORM, DossierORM]:
    job = (
        await session.execute(select(JobORM).where(JobORM.dossier_id == DOSSIER_ID))
    ).scalar_one()
    dossier = (
        await session.execute(select(DossierORM).where(DossierORM.id == DOSSIER_ID))
    ).scalar_one()
    return job, dossier


async def _audit_rows(session: AsyncSession, action: str) -> list[AuditEventORM]:
    rows = await session.execute(
        select(AuditEventORM).where(AuditEventORM.action == action).order_by(AuditEventORM.id)
    )
    return list(rows.scalars())


# ---------------------------------------------------------------------------
# AI2 result → ReviewItem for every finding, pending_review, audit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ai2_success_queues_every_finding_and_moves_to_pending_review(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    async with factory() as session:
        counts = await worker._finalize_ai2_success(
            session,
            tenant_id=TENANT_ID,
            dossier_id=DOSSIER_ID,
            run_id=RUN_ID,
            report=_result_with_pass_finding(),
            ai2_job_id="ai2-job-http",
            snapshot_digest=SNAPSHOT_DIGEST,
            source="http_poll",
        )

    async with factory() as session:
        job, dossier = await _job_and_dossier(session)
        finding_items = (
            await session.execute(
                select(ReviewItemORM.reason, ReviewItemORM.priority).where(
                    ReviewItemORM.run_id == RUN_ID, ReviewItemORM.target_type == "finding"
                )
            )
        ).all()
        finding_rows = await session.scalar(
            text("SELECT COUNT(*) FROM finding WHERE dossier_id = :d").bindparams(d=DOSSIER_ID)
        )
        audits = await _audit_rows(session, "ai2.result_persisted")
        run = await session.get(PipelineRunORM, RUN_ID)

    assert job.status == "pending_review"
    assert dossier.status == "pending_review"
    assert dossier.has_conflicts is True
    assert run is not None and run.status == "succeeded"
    # Mỗi finding một ReviewItem, kể cả finding PASS/match (trước đây bị bỏ qua).
    assert finding_rows == counts["findings"] == 2
    assert len(finding_items) == finding_rows
    reasons = dict(finding_items)
    assert reasons["finding:contract_value:match"] == "P3"
    assert reasons["finding:payment_term:needs_review"] == "P1"
    assert counts["review_items"] >= finding_rows
    assert counts["index_contribution_state"] == "propose"
    assert len(audits) == 1
    audit = audits[0]
    assert (audit.from_state, audit.to_state) == ("uploaded", "pending_review")
    assert audit.run_id == RUN_ID
    detail = json.loads(audit.detail or "{}")
    assert detail["source"] == "http_poll"
    assert detail["findings"] == 2
    assert detail["has_conflicts"] is True


@pytest.mark.asyncio
async def test_ai2_failure_marks_job_failed_with_audit(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    async with factory() as session:
        await worker._fail_ai2_run(
            session,
            tenant_id=TENANT_ID,
            run_id=RUN_ID,
            code="AI2_SCHEMA_INVALID",
            detail="snapshot rejected",
            audit_detail={"source": "http_poll"},
        )

    async with factory() as session:
        job, dossier = await _job_and_dossier(session)
        audits = await _audit_rows(session, "ai2.processing_failed")
        run = await session.get(PipelineRunORM, RUN_ID)

    assert job.status == "failed"
    assert job.error_code == "AI2_SCHEMA_INVALID"
    assert dossier.status == "failed"
    assert run is not None and run.status == "failed"
    assert len(audits) == 1
    assert audits[0].to_state == "failed"


# ---------------------------------------------------------------------------
# Dispatcher HTTP poll branch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatcher_persists_terminal_report_and_audits(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    task = DispatchTask(
        task_id=7,
        kind="extract",
        submit_coroutine=None,
        request_payload=None,
        tenant_id=TENANT_ID,
        run_id=RUN_ID,
        dossier_id=DOSSIER_ID,
    )
    written = await _persist_result(
        task,
        JobStatusReport(
            job_id="ai-job-timeout",
            kind="extract",
            status=AiJobStatus.FAILED,
            error={"code": "POLL_TIMEOUT", "message": "AI service did not complete in time"},
        ),
        session_factory=factory,
    )

    async with factory() as session:
        audits = await _audit_rows(session, "ai.extract.failed")

    assert written == 0
    assert len(audits) == 1
    assert audits[0].entity_id == "ai-job-timeout"
    assert audits[0].actor_id == "system:dispatcher"
    assert json.loads(audits[0].detail or "{}")["error"]["code"] == "POLL_TIMEOUT"


@pytest.mark.asyncio
async def test_dispatcher_rejects_unknown_kind_and_rolls_back(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    task = DispatchTask(
        task_id=8,
        kind="bogus",
        submit_coroutine=None,
        request_payload=None,
        tenant_id=TENANT_ID,
    )
    report = JobStatusReport(
        job_id="ai-job-bogus", kind="extract", status=AiJobStatus.COMPLETED, result={}
    )
    with pytest.raises(ValueError, match="Unknown dispatch kind"):
        await _persist_result(task, report, session_factory=factory)

    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(AuditEventORM)) == 0


# ---------------------------------------------------------------------------
# /query + /ask: QueryTrace in DB, quota, second ACL pass
# ---------------------------------------------------------------------------


def _ai2_answer(*source_file_ids: str) -> dict[str, Any]:
    return {
        "state": "PASS",
        "answer": "Thanh toán trong 30 ngày.",
        "citations": [
            {"source_file_id": doc_id, "line_id": f"line-{doc_id}", "text_span": "30 ngày"}
            for doc_id in source_file_ids
        ],
        "retrieval_layer": {"selected": "LEXICAL"},
        "reasoning_trace": [],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["query", "ask"])
async def test_query_and_ask_persist_query_trace_in_db(
    factory: async_sessionmaker[AsyncSession], client: AsyncClient, endpoint: str
) -> None:
    with patch(_QUERY_AI2, new=AsyncMock(return_value=_ai2_answer(BODY_DOCUMENT_ID))) as ai2:
        response = await client.post(
            f"/api/v1/dossiers/{DOSSIER_ID}/{endpoint}",
            json={"query": "Thời hạn thanh toán?"},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["acl_decision"] == "passed"
    assert body["answer"] == "Thanh toán trong 30 ngày."
    assert ai2.await_args.args[0]["actor_id"] == OPERATOR.user_id

    async with factory() as session:
        trace = await session.get(QueryTraceORM, body["trace_id"])

    assert trace is not None
    assert trace.endpoint == endpoint
    assert trace.actor_id == OPERATOR.user_id
    assert trace.tenant_id == TENANT_ID
    assert trace.snapshot_digest == SNAPSHOT_DIGEST
    assert trace.query_contract_version
    assert trace.acl_decision == "passed"
    assert json.loads(trace.citations)[0]["source_file_id"] == BODY_DOCUMENT_ID


@pytest.mark.asyncio
async def test_query_second_acl_pass_drops_citation_outside_dossier(
    factory: async_sessionmaker[AsyncSession], client: AsyncClient
) -> None:
    answer = _ai2_answer(BODY_DOCUMENT_ID, "document-from-another-dossier")
    with patch(_QUERY_AI2, new=AsyncMock(return_value=answer)):
        response = await client.post(
            f"/api/v1/dossiers/{DOSSIER_ID}/query", json={"query": "Thời hạn?"}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["acl_decision"] == "filtered"
    assert body["state"] == "BLOCKED"
    assert body["answer"] == ""
    assert [c["source_file_id"] for c in body["citations"]] == [BODY_DOCUMENT_ID]

    async with factory() as session:
        trace = await session.get(QueryTraceORM, body["trace_id"])
    assert trace is not None
    assert trace.dropped_citations == 1
    assert trace.acl_decision == "filtered"


@pytest.mark.asyncio
async def test_tenant_daily_quota_returns_429_before_ai2(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "query_daily_quota_per_tenant", 1)
    with patch(_QUERY_AI2, new=AsyncMock(return_value=_ai2_answer(BODY_DOCUMENT_ID))) as ai2:
        first = await client.post(f"/api/v1/dossiers/{DOSSIER_ID}/ask", json={"query": "a"})
        second = await client.post(f"/api/v1/dossiers/{DOSSIER_ID}/query", json={"query": "b"})

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["Retry-After"] == "3600"
    assert "QUOTA_EXCEEDED" in second.text
    assert ai2.await_count == 1


@pytest.mark.asyncio
async def test_ai2_failure_still_writes_query_trace(
    factory: async_sessionmaker[AsyncSession], client: AsyncClient
) -> None:
    from contract_intelligence.infrastructure.ai_adapters import AiAdapterError

    with patch(_QUERY_AI2, new=AsyncMock(side_effect=AiAdapterError("down"))):
        response = await client.post(
            f"/api/v1/dossiers/{DOSSIER_ID}/ask", json={"query": "Điều 1?"}
        )

    assert response.status_code == 502
    async with factory() as session:
        traces = list((await session.execute(select(QueryTraceORM))).scalars())
    assert len(traces) == 1
    assert traces[0].error_code == "AI2_QUERY_FAILED"
    assert traces[0].endpoint == "ask"


@pytest.mark.asyncio
async def test_query_policy_flags_come_from_server_not_client(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "ai2_query_egress_allowed", False)
    with patch(_QUERY_AI2, new=AsyncMock(return_value=_ai2_answer(BODY_DOCUMENT_ID))) as ai2:
        rejected = await client.post(
            f"/api/v1/dossiers/{DOSSIER_ID}/query",
            json={"query": "a", "policy_flags": {"egress_allowed": True}},
        )
        accepted = await client.post(f"/api/v1/dossiers/{DOSSIER_ID}/query", json={"query": "a"})

    assert rejected.status_code == 422
    assert accepted.status_code == 200
    assert ai2.await_count == 1
    assert ai2.await_args.args[0]["policy_flags"]["egress_allowed"] is False


@pytest.mark.asyncio
async def test_query_rejects_tombstoned_dossier(
    factory: async_sessionmaker[AsyncSession], client: AsyncClient
) -> None:
    async with factory() as session:
        dossier = await session.get(DossierORM, DOSSIER_ID)
        assert dossier is not None
        dossier.deleted_at = dossier.created_at
        await session.commit()

    with patch(_QUERY_AI2, new=AsyncMock(return_value=_ai2_answer(BODY_DOCUMENT_ID))) as ai2:
        response = await client.post(f"/api/v1/dossiers/{DOSSIER_ID}/ask", json={"query": "a"})

    assert response.status_code == 404
    assert ai2.await_count == 0


@pytest.mark.asyncio
async def test_query_requires_tenant_header(client: AsyncClient) -> None:
    app.dependency_overrides.pop(get_tenant_id, None)
    with patch(_QUERY_AI2, new=AsyncMock(return_value=_ai2_answer(BODY_DOCUMENT_ID))) as ai2:
        missing = await client.post(f"/api/v1/dossiers/{DOSSIER_ID}/query", json={"query": "a"})
        mismatched = await client.post(
            f"/api/v1/dossiers/{DOSSIER_ID}/query",
            json={"query": "a"},
            headers={"X-Tenant-Id": "tenant-other"},
        )
        ok = await client.post(
            f"/api/v1/dossiers/{DOSSIER_ID}/query",
            json={"query": "a"},
            headers={"X-Tenant-Id": TENANT_ID},
        )

    assert missing.status_code == 400
    assert mismatched.status_code == 403
    assert ok.status_code == 200
    assert ai2.await_count == 1
