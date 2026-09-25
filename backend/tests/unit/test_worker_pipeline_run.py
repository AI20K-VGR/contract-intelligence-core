"""Regression tests for the Kafka worker's canonical upload path."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import contract_intelligence.worker as worker
from contract_intelligence.extraction.infrastructure.persistence.orm import (
    PipelineRunORM,
    PipelineStepORM,
)
from contract_intelligence.worker import _mark_processing


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
async def test_mark_processing_creates_pipeline_run_and_all_steps_for_canonical_upload() -> None:
    job = SimpleNamespace(
        id="job_test",
        tenant_id="tenant_test",
        dossier_id="dos_test",
        current_run_id="run_test",
        status="uploaded",
        updated_at=None,
    )
    session = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                None,  # dossier status update
                _ScalarResult(job),  # latest job lookup
                _ScalarResult(None),  # missing pipeline_run lookup
            ]
        ),
        add=MagicMock(),
        flush=AsyncMock(),
    )

    run_id = await _mark_processing(session, "dos_test")

    assert run_id == "run_test"
    added = [call.args[0] for call in session.add.call_args_list]
    runs = [item for item in added if isinstance(item, PipelineRunORM)]
    steps = [item for item in added if isinstance(item, PipelineStepORM)]
    assert len(runs) == 1
    assert runs[0].id == "run_test"
    assert runs[0].job_id == "job_test"
    assert runs[0].dossier_id == "dos_test"
    assert [step.step for step in steps] == [
        "S0",
        "S1",
        "S2",
        "S3",
        "S4",
        "S5",
        "S6",
        "S7",
        "S8",
        "S9",
        "S10",
    ]


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_ai1_retry_replaces_existing_snapshot_instead_of_skipping_persist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = SimpleNamespace(
        execute=AsyncMock(),
        commit=AsyncMock(),
    )
    persist = AsyncMock()
    monkeypatch.setattr(
        worker,
        "adapt_ai1_snapshot_result",
        lambda _result: SimpleNamespace(document_id="doc_test", pages=[object()]),
    )
    monkeypatch.setattr(worker, "persist_ai1_snapshot", persist)
    monkeypatch.setattr(worker, "_mark_status", AsyncMock())
    monkeypatch.setattr(worker, "update_pipeline_step", AsyncMock())
    monkeypatch.setattr(worker, "_run_ai2_if_ready", AsyncMock())

    await worker.handle_ai1_result(
        session,
        {
            "event_id": "event_retry",
            "event_type": "ai1.ocr.completed",
            "tenant_id": "tenant_test",
            "correlation": {
                "dossier_id": "dos_test",
                "document_id": "doc_test",
                "run_id": "run_retry",
            },
            "payload": {
                "job_id": "job_retry",
                "result": {
                    "snapshot": {
                        "schema_version": "ai1.snapshot.v1",
                        "document_id": "doc_test",
                        "pages": [],
                    }
                },
            },
        },
    )

    persist.assert_awaited_once()


@pytest.mark.asyncio
async def test_ai2_transient_failure_releases_submission_guard_for_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = "run_ai2_retry"
    worker._submitted_ai2_runs.discard(run_id)
    manifest = SimpleNamespace(id="manifest_test", status="confirmed")
    durable_run = SimpleNamespace(ai2_result_digest=None, config_snapshot={})

    def result_sequence() -> list[object]:
        return [
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
        session,
        dossier_id="dos_test",
        tenant_id="tenant_test",
        run_id=run_id,
    )

    assert run_id not in worker._submitted_ai2_runs
    assert session.rollback.await_count == 1

    session.execute = AsyncMock(side_effect=result_sequence())
    await worker._run_ai2_if_ready(
        session,
        dossier_id="dos_test",
        tenant_id="tenant_test",
        run_id=run_id,
    )

    assert submit.await_count == 2
