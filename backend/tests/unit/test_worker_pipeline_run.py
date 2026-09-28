"""Kafka worker state machine (sqlite, offline).

- ``dossier.uploaded`` opens/resumes a run; OCR restart supersedes it
- AI1 results bind to the job's current run and the tenant/dossier in the DB
- EXTRACTED only once every document of the dossier has a snapshot
- invalid/missing snapshot → FAILED + audit; nothing moves a job backwards
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Iterator
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
    monkeypatch.setattr(
        worker.storage, "generate_presigned_get_url", AsyncMock(return_value="http://get")
    )
    put_url = AsyncMock(side_effect=lambda *, key: f"http://put/{key}")
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
