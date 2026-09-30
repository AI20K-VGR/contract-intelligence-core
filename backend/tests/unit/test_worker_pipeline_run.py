"""Kafka worker state machine (sqlite, offline).

- ``dossier.uploaded`` opens/resumes a run; OCR restart supersedes it
- AI1 results bind to the job's current run and the tenant/dossier in the DB
- EXTRACTED only once every document of the dossier has a snapshot
- invalid/missing snapshot → FAILED + audit; nothing moves a job backwards
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Iterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import contract_intelligence.worker as worker
from contract_intelligence.contract.infrastructure.persistence.orm import (
    DocumentORM,
    DossierORM,
    JobORM,
)
from contract_intelligence.extraction.infrastructure.persistence.orm import (
    PipelineRunORM,
    PipelineStepORM,
)
from contract_intelligence.shared.audit import AuditEventORM
from contract_intelligence.shared.persistence import Base
from contract_intelligence.shared.persistence.orm_registry import import_all_models

TENANT = "tenant_test"
DOSSIER = "dos_test"
JOB = "job_test"
DOC_A = "doc_a"
DOC_B = "doc_b"


@pytest.fixture(autouse=True)
def _reset_worker_state() -> Iterator[None]:
    worker._ai2_tasks.clear()
    yield
    worker._ai2_tasks.clear()


@pytest_asyncio.fixture
async def factory(tmp_path: Any) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    import_all_models()
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'worker.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        session.add_all(
            [
                DossierORM(id=DOSSIER, tenant_id=TENANT, name="Worker fixture"),
                JobORM(id=JOB, tenant_id=TENANT, dossier_id=DOSSIER),
                *(
                    DocumentORM(
                        id=doc_id,
                        tenant_id=TENANT,
                        dossier_id=DOSSIER,
                        role="CONTRACT" if index == 0 else "ANNEX",
                        order_index=index,
                        filename=f"{doc_id}.pdf",
                        sha256=str(index) * 64,
                    )
                    for index, doc_id in enumerate((DOC_A, DOC_B))
                ),
            ]
        )
        await session.commit()
    yield session_factory
    await engine.dispose()


@pytest.fixture
def ai2_ready(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Stub the AI1 snapshot adapter/persistence and the AI2 hand-off."""
    monkeypatch.setattr(
        worker,
        "adapt_ai1_snapshot_result",
        lambda result: SimpleNamespace(document_id=result["snapshot"]["document_id"], pages=[]),
    )
    monkeypatch.setattr(worker, "persist_ai1_snapshot", AsyncMock())
    schedule_ai2 = MagicMock()
    monkeypatch.setattr(worker, "_schedule_ai2", schedule_ai2)
    return schedule_ai2


async def _start(factory: async_sessionmaker[AsyncSession], *, restart: bool = False) -> str:
    async with factory() as session:
        run_id = await worker._mark_processing(session, DOSSIER, restart=restart)
        await session.commit()
    assert run_id is not None
    return run_id


async def _job(factory: async_sessionmaker[AsyncSession]) -> JobORM:
    async with factory() as session:
        job = await session.get(JobORM, JOB)
    assert job is not None
    return job


async def _audits(factory: async_sessionmaker[AsyncSession], action: str) -> list[AuditEventORM]:
    async with factory() as session:
        rows = await session.execute(select(AuditEventORM).where(AuditEventORM.action == action))
        return list(rows.scalars())


def _ocr_completed(run_id: str, document_id: str, **overrides: Any) -> dict[str, Any]:
    message: dict[str, Any] = {
        "schema_version": worker.SCHEMA_VERSION,
        "event_id": f"evt_{run_id}_{document_id}",
        "event_type": worker.EVENT_OCR_COMPLETED,
        "tenant_id": TENANT,
        "correlation": {"dossier_id": DOSSIER, "document_id": document_id, "run_id": run_id},
        "payload": {
            "job_id": f"ai1_{document_id}",
            "status": "completed",
            "result": {
                "snapshot": {
                    "schema_version": "ai1.snapshot.v1",
                    "document_id": document_id,
                    "pages": [],
                }
            },
        },
    }
    message.update(overrides)
    return message


async def _deliver(factory: async_sessionmaker[AsyncSession], message: dict[str, Any]) -> None:
    async with factory() as session:
        await worker.handle_ai1_result(session, message)


# ---------------------------------------------------------------------------
# dossier.uploaded / OCR restart
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_opens_run_with_all_steps(factory: async_sessionmaker[AsyncSession]) -> None:
    run_id = await _start(factory)

    async with factory() as session:
        run = await session.get(PipelineRunORM, run_id)
        steps = (
            await session.execute(
                select(PipelineStepORM.step).where(PipelineStepORM.run_id == run_id)
            )
        ).scalars()
        dossier = await session.get(DossierORM, DOSSIER)
    job = await _job(factory)

    assert run is not None and run.job_id == JOB and run.status == "running"
    assert sorted(steps, key=lambda s: int(s[1:])) == [f"S{n}" for n in range(11)]
    assert job.status == "processing" and job.current_run_id == run_id
    assert dossier is not None and dossier.status == "processing"
    assert len(await _audits(factory, "job.status_changed")) == 1


@pytest.mark.asyncio
async def test_redelivered_upload_resumes_active_run(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    first = await _start(factory)
    second = await _start(factory)
    assert first == second


@pytest.mark.asyncio
async def test_ocr_command_asks_for_every_page_with_one_render_url_each(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_url = AsyncMock(return_value="http://get")
    monkeypatch.setattr(worker.storage, "generate_presigned_get_url", get_url)
    put_url = AsyncMock(side_effect=lambda *, key, expires_in, **_: f"http://put/{key}")
    monkeypatch.setattr(worker.storage, "generate_presigned_put_url", put_url)
    document = DocumentORM(
        id=DOC_A,
        tenant_id=TENANT,
        dossier_id=DOSSIER,
        role="CONTRACT",
        order_index=0,
        filename="a.pdf",
        sha256="0" * 64,
        blob_uri="s3://dossiers/a.pdf",
        page_count=200,
    )
    dossier = DossierORM(id=DOSSIER, tenant_id=TENANT, name="x")

    envelope = await worker._build_ocr_command_payload(
        document=document, dossier=dossier, run_id="run_x"
    )

    payload = envelope["payload"]
    assert payload["pages_to_process"] == list(range(1, 201))
    urls = payload["render_target"]["presigned_put_urls"]
    assert len(urls) == 200 and urls["200"].endswith("/page-200.png")
    # URLs outlive the run's AI1 deadline (default 600s + 30s x 200 pages) by 10 min.
    expected_ttl = worker.ai1_deadline_seconds(200) + 600
    assert expected_ttl == 7200
    assert get_url.await_args.kwargs["expires_in"] == expected_ttl
    assert {call.kwargs["expires_in"] for call in put_url.await_args_list} == {expected_ttl}
    # One more PUT URL: where AI1 may upload the snapshot JSON (DOC-11 §2).
    target = payload["options"]["result_target"]
    assert target["uri"] == f"s3://ci-render/{DOC_A}/ai1-result/run_x.json"
    assert target["put_url"] == f"http://put/{DOC_A}/ai1-result/run_x.json"
    assert target["content_type"] == "application/json"
    assert put_url.await_count == 201


def test_presign_ttl_never_exceeds_the_s3_limit() -> None:
    assert worker._presign_ttl_seconds(1_000_000) == 7 * 24 * 3600


# ---------------------------------------------------------------------------
# AI1 watchdog
# ---------------------------------------------------------------------------


async def _age_run(factory: async_sessionmaker[AsyncSession], run_id: str, seconds: int) -> None:
    async with factory() as session:
        run = await session.get(PipelineRunORM, run_id)
        assert run is not None
        run.created_at = datetime.now(tz=UTC) - timedelta(seconds=seconds)
        await session.commit()


@pytest.mark.asyncio
async def test_watchdog_fails_run_past_its_ai1_deadline(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    run_id = await _start(factory)
    # Fixture documents have no page count: deadline = 600 + 30 x 1 page.
    await _age_run(factory, run_id, worker.ai1_deadline_seconds(0) + 5)

    async with factory() as session:
        assert await worker.fail_overdue_ai1_runs(session) == [run_id]

    job = await _job(factory)
    async with factory() as session:
        run = await session.get(PipelineRunORM, run_id)
    assert job.status == "failed" and job.error_code == "AI1_TIMEOUT"
    assert run is not None and run.status == "failed"
    (audit,) = await _audits(factory, "ai1.timeout")
    assert audit.run_id == run_id


@pytest.mark.asyncio
async def test_watchdog_leaves_runs_within_deadline_and_finished_jobs(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    run_id = await _start(factory)
    await _age_run(factory, run_id, worker.ai1_deadline_seconds(0) - 60)
    async with factory() as session:
        assert await worker.fail_overdue_ai1_runs(session) == []

    # A job that already left PROCESSING is never touched, however old its run.
    async with factory() as session:
        job = await session.get(JobORM, JOB)
        assert job is not None
        job.status = "pending_review"
        await session.commit()
    await _age_run(factory, run_id, 10 * worker.ai1_deadline_seconds(0))
    async with factory() as session:
        assert await worker.fail_overdue_ai1_runs(session) == []
    assert (await _job(factory)).status == "pending_review"


@pytest.mark.asyncio
async def test_watchdog_deadline_grows_with_page_count(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    async with factory() as session:
        for doc_id in (DOC_A, DOC_B):
            document = await session.get(DocumentORM, doc_id)
            assert document is not None
            document.page_count = 100
        await session.commit()
    run_id = await _start(factory)
    # Old enough for a 1-page dossier, well inside the 200-page deadline (6600s).
    await _age_run(factory, run_id, 3600)
    async with factory() as session:
        assert await worker.fail_overdue_ai1_runs(session) == []
    await _age_run(factory, run_id, worker.ai1_deadline_seconds(200) + 5)
    async with factory() as session:
        assert await worker.fail_overdue_ai1_runs(session) == [run_id]


@pytest.mark.asyncio
async def test_ocr_result_after_timeout_does_not_revive_the_job(
    factory: async_sessionmaker[AsyncSession], ai2_ready: MagicMock
) -> None:
    run_id = await _start(factory)
    await _age_run(factory, run_id, worker.ai1_deadline_seconds(0) + 5)
    async with factory() as session:
        await worker.fail_overdue_ai1_runs(session)

    await _deliver(factory, _ocr_completed(run_id, DOC_A))
    await _deliver(factory, _ocr_completed(run_id, DOC_B))

    job = await _job(factory)
    assert job.status == "failed" and job.error_code == "AI1_TIMEOUT"
    assert ai2_ready.call_count == 0
    late = await _audits(factory, "ai1.late_result")
    assert [a.run_id for a in late] == [run_id, run_id]
    assert all('"job_error_code": "AI1_TIMEOUT"' in (a.detail or "") for a in late)


@pytest.mark.asyncio
async def test_upload_event_starts_run_queued_by_api(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    """POST /runs commits a queued run; the worker must run that one, not a new one."""
    async with factory() as session:
        session.add(
            PipelineRunORM(
                id="run_api",
                tenant_id=TENANT,
                job_id=JOB,
                dossier_id=DOSSIER,
                status="queued",
                pipeline_version="v1.0.0",
            )
        )
        session.add_all(
            PipelineStepORM(tenant_id=TENANT, run_id="run_api", step=f"S{n}", status="queued")
            for n in range(11)
        )
        job = await session.get(JobORM, JOB)
        assert job is not None
        job.status = "uploaded"
        job.current_run_id = "run_api"
        await session.commit()

    assert await _start(factory) == "run_api"

    async with factory() as session:
        run = await session.get(PipelineRunORM, "run_api")
        steps = dict(
            (
                await session.execute(
                    select(PipelineStepORM.step, PipelineStepORM.status).where(
                        PipelineStepORM.run_id == "run_api"
                    )
                )
            ).all()
        )
    assert run is not None and run.status == "running"
    assert (steps["S0"], steps["S1"], steps["S2"], steps["S3"]) == (
        "succeeded",
        "succeeded",
        "running",
        "queued",
    )
    assert (await _job(factory)).status == "processing"


@pytest.mark.asyncio
async def test_ocr_restart_supersedes_run_and_ignores_its_late_results(
    factory: async_sessionmaker[AsyncSession], ai2_ready: MagicMock
) -> None:
    old_run = await _start(factory)
    new_run = await _start(factory, restart=True)

    async with factory() as session:
        superseded = await session.get(PipelineRunORM, old_run)
    assert new_run != old_run
    assert superseded is not None and superseded.status == "cancelled"
    assert superseded.error_code == "SUPERSEDED"

    await _deliver(factory, _ocr_completed(old_run, DOC_A))
    await _deliver(factory, _ocr_completed(old_run, DOC_B))

    job = await _job(factory)
    assert job.status == "processing" and job.current_run_id == new_run
    assert ai2_ready.call_count == 0


@pytest.mark.asyncio
async def test_upload_event_does_not_reopen_a_job_in_review(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    run_id = await _start(factory)
    async with factory() as session:
        job = await session.get(JobORM, JOB)
        assert job is not None
        job.status = "pending_review"
        await session.commit()

    async with factory() as session:
        assert await worker._mark_processing(session, DOSSIER) is None
    job = await _job(factory)
    assert job.status == "pending_review" and job.current_run_id == run_id


@pytest.mark.asyncio
async def test_ocr_restart_refused_for_approved_job(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    await _start(factory)
    async with factory() as session:
        job = await session.get(JobORM, JOB)
        assert job is not None
        job.status = "approved"
        await session.commit()

    async with factory() as session:
        assert await worker._mark_processing(session, DOSSIER, restart=True) is None
    assert (await _job(factory)).status == "approved"


@pytest.mark.asyncio
async def test_ocr_restart_recovers_failed_job_with_new_run(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    old_run = await _start(factory)
    await _deliver(factory, _ocr_completed(old_run, DOC_A, payload={"job_id": "x"}))
    assert (await _job(factory)).status == "failed"

    new_run = await _start(factory, restart=True)
    job = await _job(factory)
    assert new_run != old_run
    assert job.status == "processing" and job.error_code is None


# ---------------------------------------------------------------------------
# AI1 results
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extracted_only_after_every_document_has_a_snapshot(
    factory: async_sessionmaker[AsyncSession], ai2_ready: MagicMock
) -> None:
    run_id = await _start(factory)

    await _deliver(factory, _ocr_completed(run_id, DOC_A))
    assert (await _job(factory)).status == "processing"
    assert ai2_ready.call_count == 0

    await _deliver(factory, _ocr_completed(run_id, DOC_B))
    assert (await _job(factory)).status == "extracted"
    ai2_ready.assert_called_once()

    async with factory() as session:
        run = await session.get(PipelineRunORM, run_id)
    assert run is not None
    assert '"ai1_extracted_documents": ["doc_a", "doc_b"]' in str(run.config_snapshot)
    audits = await _audits(factory, "ai1.snapshot_persisted")
    assert [(a.from_state, a.to_state) for a in audits] == [
        ("processing", "processing"),
        ("processing", "extracted"),
    ]


@pytest.mark.asyncio
async def test_redelivered_result_is_ignored_without_memory_state(
    factory: async_sessionmaker[AsyncSession], ai2_ready: MagicMock
) -> None:
    """Dedupe lives in the run row, so it survives a worker restart."""
    run_id = await _start(factory)
    await _deliver(factory, _ocr_completed(run_id, DOC_A))
    await _deliver(factory, _ocr_completed(run_id, DOC_B))
    assert ai2_ready.call_count == 1

    # Worker restarts (no in-memory state) and Kafka redelivers DOC_A.
    worker._ai2_tasks.clear()
    await _deliver(factory, _ocr_completed(run_id, DOC_A))

    assert (await _job(factory)).status == "extracted"
    assert len(await _audits(factory, "ai1.snapshot_persisted")) == 2
    # The redelivery re-kicks AI2 (idempotent per run) instead of stranding the job.
    assert ai2_ready.call_count == 2


@pytest.mark.asyncio
async def test_invalid_snapshot_marks_job_failed_with_audit(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    run_id = await _start(factory)
    message = _ocr_completed(run_id, DOC_A)
    message["payload"]["result"] = {"snapshot": {"schema_version": "bogus"}}

    await _deliver(factory, message)

    job = await _job(factory)
    async with factory() as session:
        run = await session.get(PipelineRunORM, run_id)
    audits = await _audits(factory, "ai1.snapshot_rejected")
    assert job.status == "failed" and job.error_code == "AI1_SNAPSHOT_INVALID"
    assert run is not None and run.status == "failed"
    assert len(audits) == 1 and audits[0].to_state == "failed"


@pytest.mark.asyncio
async def test_completed_event_without_result_marks_job_failed(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    run_id = await _start(factory)
    message = _ocr_completed(run_id, DOC_A)
    message["payload"].pop("result")

    await _deliver(factory, message)

    job = await _job(factory)
    assert job.status == "failed" and job.error_code == "AI1_RESULT_MISSING"


@pytest.mark.asyncio
async def test_snapshot_for_foreign_document_marks_job_failed(
    factory: async_sessionmaker[AsyncSession], ai2_ready: MagicMock
) -> None:
    run_id = await _start(factory)
    message = _ocr_completed(run_id, DOC_A)
    message["payload"]["result"]["snapshot"]["document_id"] = "doc_other_dossier"

    await _deliver(factory, message)

    assert (await _job(factory)).status == "failed"
    assert ai2_ready.call_count == 0


@pytest.mark.asyncio
async def test_late_success_does_not_override_failed(
    factory: async_sessionmaker[AsyncSession], ai2_ready: MagicMock
) -> None:
    run_id = await _start(factory)
    failed = _ocr_completed(run_id, DOC_A, event_type=worker.EVENT_OCR_FAILED)
    failed["payload"] = {"job_id": "ai1_a", "status": "failed", "error": {"code": "OCR_X"}}
    await _deliver(factory, failed)

    await _deliver(factory, _ocr_completed(run_id, DOC_B))

    job = await _job(factory)
    assert job.status == "failed" and job.error_code == "OCR_X"
    assert len(await _audits(factory, "ai1.snapshot_persisted")) == 0


@pytest.mark.asyncio
async def test_envelope_with_wrong_schema_version_is_dropped(
    factory: async_sessionmaker[AsyncSession], ai2_ready: MagicMock
) -> None:
    run_id = await _start(factory)
    await _deliver(factory, _ocr_completed(run_id, DOC_A, schema_version="ci.kafka.v0"))

    assert (await _job(factory)).status == "processing"
    assert len(await _audits(factory, "ai1.snapshot_persisted")) == 0


@pytest.mark.asyncio
async def test_result_claiming_another_tenant_is_rejected(
    factory: async_sessionmaker[AsyncSession], ai2_ready: MagicMock
) -> None:
    run_id = await _start(factory)
    await _deliver(factory, _ocr_completed(run_id, DOC_A, tenant_id="tenant_attacker"))

    assert (await _job(factory)).status == "processing"
    rejected = await _audits(factory, "ai1.result_rejected")
    assert len(rejected) == 1 and rejected[0].tenant_id == TENANT


@pytest.mark.asyncio
async def test_ai2_success_refused_after_job_failed(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    run_id = await _start(factory)
    async with factory() as session:
        job = await session.get(JobORM, JOB)
        assert job is not None
        job.status = "failed"
        await session.commit()

    async with factory() as session:
        counts = await worker._finalize_ai2_success(
            session,
            tenant_id=TENANT,
            dossier_id=DOSSIER,
            run_id=run_id,
            report={"status": "SUCCEEDED"},
            ai2_job_id="ai2_late",
            source="kafka",
        )

    assert counts is None
    assert (await _job(factory)).status == "failed"


# ---------------------------------------------------------------------------
# AI2 HTTP submit retry guard
# ---------------------------------------------------------------------------


class _ScalarResult:
    def __init__(self, value: object) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object:
        return self._value


class _RowsResult:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def scalars(self) -> _RowsResult:
        return self

    def all(self) -> list[object]:
        return self._rows


@pytest.mark.asyncio
async def test_ai2_transient_failure_can_be_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = "run_ai2_retry"
    manifest = SimpleNamespace(id="manifest_test", status="confirmed")
    durable_run = SimpleNamespace(ai2_result_digest=None, config_snapshot={})

    def result_sequence() -> list[object]:
        return [
            _ScalarResult(SimpleNamespace(status="extracted")),
            _ScalarResult(manifest),
            _ScalarResult(durable_run),
            _RowsResult([]),
            _RowsResult([]),
            _RowsResult([]),
        ]

    session = SimpleNamespace(
        execute=AsyncMock(side_effect=result_sequence()),
        commit=AsyncMock(),
        rollback=AsyncMock(),
    )
    monkeypatch.setattr(
        worker,
        "build_processing_request",
        lambda **_kwargs: {"snapshots": [{"snapshot_id": "snap_test"}]},
    )
    monkeypatch.setattr(worker, "update_pipeline_run_status", AsyncMock())
    monkeypatch.setattr(worker, "update_pipeline_step", AsyncMock())
    monkeypatch.setattr(worker, "_mark_status", AsyncMock())
    submit = AsyncMock(side_effect=RuntimeError("temporary AI2 outage"))
    monkeypatch.setattr(worker, "submit_ai2_processing", submit)

    await worker._run_ai2_if_ready(
        session, dossier_id="dos_test", tenant_id="tenant_test", run_id=run_id
    )

    assert session.rollback.await_count == 1

    session.execute = AsyncMock(side_effect=result_sequence())
    await worker._run_ai2_if_ready(
        session, dossier_id="dos_test", tenant_id="tenant_test", run_id=run_id
    )

    assert submit.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("job_status", ["processing", "pending_review", "failed"])
async def test_ai2_not_submitted_unless_job_is_extracted(
    factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    job_status: str,
) -> None:
    """Durable guard: a manifest.confirmed replay after AI2 finished must not resubmit."""
    run_id = await _start(factory)
    async with factory() as session:
        job = await session.get(JobORM, JOB)
        assert job is not None
        job.status = job_status
        await session.commit()
    submit = AsyncMock()
    monkeypatch.setattr(worker, "submit_ai2_processing", submit)

    async with factory() as session:
        await worker._run_ai2_if_ready(session, dossier_id=DOSSIER, tenant_id=TENANT, run_id=run_id)

    submit.assert_not_awaited()


@pytest.mark.asyncio
async def test_ai2_deadline_miss_fails_run_as_ai2_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = SimpleNamespace(id="manifest_test", status="confirmed")
    durable_run = SimpleNamespace(ai2_result_digest=None, config_snapshot='{"ai2_attempt": 2}')
    documents = [SimpleNamespace(page_count=150), SimpleNamespace(page_count=50)]
    session = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _ScalarResult(SimpleNamespace(status="extracted")),
                _ScalarResult(manifest),
                _ScalarResult(durable_run),
                _RowsResult([]),
                _RowsResult([]),
                _RowsResult(documents),
            ]
        ),
        commit=AsyncMock(),
        rollback=AsyncMock(),
    )
    build = MagicMock(return_value={"snapshots": [{"snapshot_id": "snap_test"}]})
    monkeypatch.setattr(worker, "build_processing_request", build)
    monkeypatch.setattr(worker, "update_pipeline_run_status", AsyncMock())
    monkeypatch.setattr(worker, "update_pipeline_step", AsyncMock())
    monkeypatch.setattr(worker, "submit_ai2_processing", AsyncMock(return_value={"job_id": "j9"}))
    poll = AsyncMock(side_effect=worker.AiAdapterDeadlineExceeded("still running"))
    monkeypatch.setattr(worker, "poll_ai2_processing", poll)
    fail = AsyncMock()
    monkeypatch.setattr(worker, "_fail_ai2_run", fail)

    await worker._run_ai2_if_ready(
        session, dossier_id="dos_test", tenant_id="tenant_test", run_id="run_x"
    )

    budget = worker.ai2_deadline_seconds(200)
    assert budget == 700  # 300s + 2s x 200 pages
    assert build.call_args.kwargs["attempt"] == 2
    assert build.call_args.kwargs["max_processing_seconds"] == budget
    assert poll.await_args.kwargs["timeout_seconds"] == budget + 60
    assert fail.await_args.kwargs["code"] == "AI2_TIMEOUT"
    assert fail.await_args.kwargs["audit_detail"]["ai2_job_id"] == "j9"


# ---------------------------------------------------------------------------
# AI2 retry without re-OCR
# ---------------------------------------------------------------------------


async def _fail_at_ai2(
    factory: async_sessionmaker[AsyncSession], ai2_ready: MagicMock, code: str
) -> str:
    """Both documents OCR'd (EXTRACTED), then the AI2 step failed with ``code``."""
    run_id = await _start(factory)
    await _deliver(factory, _ocr_completed(run_id, DOC_A))
    await _deliver(factory, _ocr_completed(run_id, DOC_B))
    assert (await _job(factory)).status == "extracted"
    async with factory() as session:
        await worker._fail_ai2_run(
            session, tenant_id=TENANT, run_id=run_id, code=code, detail="x", audit_detail={}
        )
    ai2_ready.reset_mock()
    return run_id


def _retry_event(run_id: str) -> dict[str, Any]:
    return {"event": "dossier.ai2.retry", "dossier_id": DOSSIER, "run_id": run_id}


@pytest.mark.asyncio
@pytest.mark.parametrize("code", ["AI2_TIMEOUT", "AI2_PROCESSING_FAILED"])
async def test_ai2_retry_reopens_run_with_next_attempt(
    factory: async_sessionmaker[AsyncSession], ai2_ready: MagicMock, code: str
) -> None:
    run_id = await _fail_at_ai2(factory, ai2_ready, code)

    async with factory() as session:
        await worker.handle_dossier_event(session, _retry_event(run_id))

    job = await _job(factory)
    async with factory() as session:
        run = await session.get(PipelineRunORM, run_id)
    assert job.status == "extracted" and job.error_code is None
    assert job.current_run_id == run_id  # same run: no new OCR
    assert run is not None and run.status == "running"
    assert worker._ai2_attempt(run) == 2
    ai2_ready.assert_called_once_with(dossier_id=DOSSIER, tenant_id=TENANT, run_id=run_id)
    (audit,) = await _audits(factory, "ai2.retry_requested")
    assert audit.detail is not None and '"attempt": 2' in str(audit.detail).replace("'", '"')


@pytest.mark.asyncio
async def test_ai2_retry_refused_when_ocr_failed(
    factory: async_sessionmaker[AsyncSession], ai2_ready: MagicMock
) -> None:
    run_id = await _start(factory)
    await _deliver(factory, _ocr_completed(run_id, DOC_A, event_type=worker.EVENT_OCR_FAILED))
    assert (await _job(factory)).status == "failed"

    async with factory() as session:
        await worker.handle_dossier_event(session, _retry_event(run_id))

    assert (await _job(factory)).status == "failed"
    ai2_ready.assert_not_called()


@pytest.mark.asyncio
async def test_ai2_retry_is_a_no_op_once_the_run_is_back_in_flight(
    factory: async_sessionmaker[AsyncSession], ai2_ready: MagicMock
) -> None:
    """A redelivered retry event must not bump the attempt a second time."""
    run_id = await _fail_at_ai2(factory, ai2_ready, "AI2_TIMEOUT")

    async with factory() as session:
        await worker.handle_dossier_event(session, _retry_event(run_id))
    async with factory() as session:
        await worker.handle_dossier_event(session, _retry_event(run_id))

    async with factory() as session:
        run = await session.get(PipelineRunORM, run_id)
    assert worker._ai2_attempt(run) == 2
    assert ai2_ready.call_count == 1


# ---------------------------------------------------------------------------
# AI1 result uploaded to MinIO (payload.result_ref) instead of inlined
# ---------------------------------------------------------------------------


def _by_reference(
    message: dict[str, Any], *, uri: str | None = None, sha: str | None = None
) -> tuple[dict[str, Any], bytes]:
    """Move the inline result to a result_ref, as AI1 does for large dossiers."""
    import hashlib
    import json as _json

    payload = message["payload"]
    body = _json.dumps(payload.pop("result"), ensure_ascii=False).encode()
    document_id = message["correlation"]["document_id"]
    run_id = message["correlation"]["run_id"]
    payload["result"] = None
    payload["result_ref"] = {
        "uri": uri or f"s3://ci-render/{document_id}/ai1-result/{run_id}.json",
        "sha256": sha or hashlib.sha256(body).hexdigest(),
        "bytes": len(body),
    }
    return message, body


@pytest.mark.asyncio
async def test_result_by_reference_is_downloaded_and_persisted(
    factory: async_sessionmaker[AsyncSession],
    ai2_ready: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = await _start(factory)
    objects: dict[str, bytes] = {}
    for document_id in (DOC_A, DOC_B):
        message, body = _by_reference(_ocr_completed(run_id, document_id))
        objects[message["payload"]["result_ref"]["uri"]] = body
        monkeypatch.setattr(worker.storage, "download_object", AsyncMock(side_effect=objects.get))
        await _deliver(factory, message)

    job = await _job(factory)
    assert job.status == "extracted"
    assert ai2_ready.call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"uri": "s3://dossiers/someone-else/contract.pdf"}, "not the issued target"),
        ({"sha": "0" * 64}, "sha256 does not match"),
        ({"missing": True}, "does not exist"),
    ],
)
async def test_bad_result_reference_fails_the_run(
    factory: async_sessionmaker[AsyncSession],
    ai2_ready: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    change: dict[str, Any],
    reason: str,
) -> None:
    run_id = await _start(factory)
    message, body = _by_reference(
        _ocr_completed(run_id, DOC_A), uri=change.get("uri"), sha=change.get("sha")
    )
    download = AsyncMock(
        side_effect=FileNotFoundError("gone") if change.get("missing") else None,
        return_value=body,
    )
    monkeypatch.setattr(worker.storage, "download_object", download)

    await _deliver(factory, message)

    job = await _job(factory)
    assert job.status == "failed" and job.error_code == "AI1_RESULT_UNREADABLE"
    assert reason in (job.error_detail or "")
    if "uri" in change:
        download.assert_not_awaited()  # never reads an object it did not issue
    assert ai2_ready.call_count == 0


@pytest.mark.asyncio
async def test_transient_storage_error_is_retried_not_failed(
    factory: async_sessionmaker[AsyncSession],
    ai2_ready: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = await _start(factory)
    message, _ = _by_reference(_ocr_completed(run_id, DOC_A))
    monkeypatch.setattr(
        worker.storage, "download_object", AsyncMock(side_effect=ConnectionError("minio down"))
    )

    with pytest.raises(ConnectionError):
        await _deliver(factory, message)

    assert (await _job(factory)).status == "processing"


# ---------------------------------------------------------------------------
# Keep what finished, retry only what failed (Sprint 3 task 2)
# ---------------------------------------------------------------------------


def _failed(run_id: str, document_id: str) -> dict[str, Any]:
    message = _ocr_completed(run_id, document_id, event_type=worker.EVENT_OCR_FAILED)
    message["payload"] = {
        "job_id": f"ai1_{document_id}",
        "status": "failed",
        "error": {"code": "AI1_OCR_FAILED", "message": "page 7 unreadable"},
    }
    return message


@pytest.fixture
def ocr_commands(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """OCR commands the worker publishes; documents get a blob to presign."""
    published: list[dict[str, Any]] = []

    async def publish(topic: str, message: dict[str, Any], **_: Any) -> None:
        if topic == worker.get_settings().kafka_ai1_ocr_commands_topic:
            published.append(message)

    monkeypatch.setattr(worker.messaging, "publish_event", publish)
    monkeypatch.setattr(worker.storage, "generate_presigned_get_url", AsyncMock(return_value="g"))
    monkeypatch.setattr(worker.storage, "generate_presigned_put_url", AsyncMock(return_value="p"))
    return published


async def _give_blobs(factory: async_sessionmaker[AsyncSession]) -> None:
    async with factory() as session:
        for doc_id in (DOC_A, DOC_B):
            document = await session.get(DocumentORM, doc_id)
            assert document is not None
            document.blob_uri = f"s3://dossiers/{doc_id}.pdf"
            document.page_count = 3
        await session.commit()


async def _run_payload(factory: async_sessionmaker[AsyncSession], run_id: str) -> dict[str, Any]:
    async with factory() as session:
        run = await session.get(PipelineRunORM, run_id)
    assert run is not None
    return worker._run_payload(run)


@pytest.mark.asyncio
async def test_result_after_the_run_failed_is_kept_on_the_run(
    factory: async_sessionmaker[AsyncSession], ai2_ready: MagicMock
) -> None:
    run_id = await _start(factory)
    await _deliver(factory, _failed(run_id, DOC_A))
    await _deliver(factory, _ocr_completed(run_id, DOC_B))

    job = await _job(factory)
    assert job.status == "failed" and job.error_code == "AI1_OCR_FAILED"
    assert (await _run_payload(factory, run_id))["ai1_extracted_documents"] == [DOC_B]
    (late,) = await _audits(factory, "ai1.late_result")
    assert '"kept": true' in (late.detail or "")
    assert ai2_ready.call_count == 0


@pytest.mark.asyncio
async def test_retry_failed_re_ocrs_only_the_missing_document(
    factory: async_sessionmaker[AsyncSession],
    ai2_ready: MagicMock,
    ocr_commands: list[dict[str, Any]],
) -> None:
    await _give_blobs(factory)
    first_run = await _start(factory)
    await _deliver(factory, _failed(first_run, DOC_A))
    await _deliver(factory, _ocr_completed(first_run, DOC_B))

    async with factory() as session:
        await worker.handle_dossier_uploaded(
            session,
            {
                "event": "dossier.uploaded",
                "dossier_id": DOSSIER,
                "restart": True,
                "retry_failed": True,
            },
        )
    job = await _job(factory)
    retry_run = str(job.current_run_id)
    assert retry_run != first_run and job.status == "processing"
    # Only A goes back to AI1; B's result is carried over, not re-OCR'd.
    assert [c["correlation"]["document_id"] for c in ocr_commands] == [DOC_A]
    assert (await _run_payload(factory, retry_run))["ai1_extracted_documents"] == [DOC_B]

    await _deliver(factory, _ocr_completed(retry_run, DOC_A))
    job = await _job(factory)
    assert job.status == "extracted"
    assert ai2_ready.call_count == 1
    assert sorted((await _run_payload(factory, retry_run))["ai1_extracted_documents"]) == [
        DOC_A,
        DOC_B,
    ]


@pytest.mark.asyncio
async def test_retry_failed_with_everything_kept_goes_straight_to_ai2(
    factory: async_sessionmaker[AsyncSession],
    ai2_ready: MagicMock,
    ocr_commands: list[dict[str, Any]],
) -> None:
    await _give_blobs(factory)
    run_id = await _start(factory)
    # The watchdog gave up, then both results still arrived.
    await _age_run(factory, run_id, worker.ai1_deadline_seconds(6) + 5)
    async with factory() as session:
        assert await worker.fail_overdue_ai1_runs(session) == [run_id]
    await _deliver(factory, _ocr_completed(run_id, DOC_A))
    await _deliver(factory, _ocr_completed(run_id, DOC_B))

    async with factory() as session:
        await worker.handle_dossier_uploaded(
            session, {"event": "dossier.uploaded", "dossier_id": DOSSIER, "retry_failed": True}
        )

    assert ocr_commands == []
    job = await _job(factory)
    assert job.status == "extracted" and job.current_run_id != run_id
    assert ai2_ready.call_count == 1
    assert len(await _audits(factory, "ai1.snapshots_carried")) == 1


@pytest.mark.asyncio
async def test_plain_restart_still_re_ocrs_everything(
    factory: async_sessionmaker[AsyncSession],
    ai2_ready: MagicMock,
    ocr_commands: list[dict[str, Any]],
) -> None:
    await _give_blobs(factory)
    run_id = await _start(factory)
    await _deliver(factory, _failed(run_id, DOC_A))
    await _deliver(factory, _ocr_completed(run_id, DOC_B))

    async with factory() as session:
        await worker.handle_dossier_uploaded(
            session, {"event": "dossier.uploaded", "dossier_id": DOSSIER, "restart": True}
        )

    assert sorted(c["correlation"]["document_id"] for c in ocr_commands) == [DOC_A, DOC_B]


# ---------------------------------------------------------------------------
# DEC-BE-AI2-01 B1: the AI2 payload does not read the clock
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_snapshot_time_is_stamped_once_and_survives_redelivery(
    factory: async_sessionmaker[AsyncSession], ai2_ready: MagicMock
) -> None:
    run_id = await _start(factory)
    await _deliver(factory, _ocr_completed(run_id, DOC_A))
    await _deliver(factory, _ocr_completed(run_id, DOC_B))
    stamped = (await _run_payload(factory, run_id))["ai1_snapshot_recorded_at"]
    assert sorted(stamped) == [DOC_A, DOC_B]

    # Worker restarts and Kafka redelivers DOC_A with the same snapshot.
    worker._ai2_tasks.clear()
    await _deliver(factory, _ocr_completed(run_id, DOC_A))

    assert (await _run_payload(factory, run_id))["ai1_snapshot_recorded_at"] == stamped
    async with factory() as session:
        run = await session.get(PipelineRunORM, run_id)
    assert run is not None
    assert worker._snapshot_created_at(run) == stamped


@pytest.mark.asyncio
async def test_carried_snapshot_keeps_its_stored_time(
    factory: async_sessionmaker[AsyncSession],
    ai2_ready: MagicMock,
    ocr_commands: list[dict[str, Any]],
) -> None:
    await _give_blobs(factory)
    first_run = await _start(factory)
    await _deliver(factory, _failed(first_run, DOC_A))
    await _deliver(factory, _ocr_completed(first_run, DOC_B))
    first_stamp = (await _run_payload(factory, first_run))["ai1_snapshot_recorded_at"][DOC_B]

    async with factory() as session:
        await worker.handle_dossier_uploaded(
            session,
            {"event": "dossier.uploaded", "dossier_id": DOSSIER, "retry_failed": True},
        )
    retry_run = str((await _job(factory)).current_run_id)

    carried = (await _run_payload(factory, retry_run))["ai1_snapshot_recorded_at"]
    assert retry_run != first_run
    assert carried[DOC_B] == first_stamp


def test_run_stored_before_the_stamp_falls_back_to_the_run_time() -> None:
    created = datetime(2026, 9, 30, 8, 0)  # SQLite hands back a naive UTC value
    run = SimpleNamespace(
        created_at=created,
        config_snapshot='{"ai1_snapshots": {"doc_a": {"schema_version": "ai1.snapshot.v1"}}}',
    )

    assert worker._snapshot_created_at(run) == {  # type: ignore[arg-type]
        DOC_A: created.replace(tzinfo=UTC).isoformat()
    }
