"""Unit tests for ExtractionService Phase 4 — runs / reprocess / cancel."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from contract_intelligence.extraction.application.services.extraction_service import (
    ExtractionService,
)
from contract_intelligence.extraction.domain.entities.pipeline_run import (
    PipelineRun,
    PipelineRunStatus,
)
from contract_intelligence.shared.base import Page
from contract_intelligence.shared.exceptions import InvalidStateTransition, NotFoundError

pytestmark = pytest.mark.asyncio


class FakePipelineRunRepo:
    def __init__(self) -> None:
        self.runs: dict[str, PipelineRun] = {}
        self.create_calls = 0

    async def create(self, **kwargs: Any) -> PipelineRun:
        self.create_calls += 1
        run = PipelineRun(
            id=kwargs["run_id"],
            tenant_id="tenant_test",
            dossier_id=kwargs["dossier_id"],
            status=PipelineRunStatus.QUEUED,
            pipeline_version=kwargs.get("pipeline_version", "v1"),
            git_sha=kwargs.get("git_sha") or "",
            trace_id=kwargs.get("trace_id"),
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        self.runs[run.id] = run
        return run

    async def get(self, run_id: str) -> PipelineRun | None:
        return self.runs.get(run_id)

    async def list_pipeline_runs(
        self, *, limit: int = 50, offset: int = 0, **filters: Any
    ) -> Page[str]:
        items = list(self.runs.values())
        if dossier_id := filters.get("dossier_id"):
            items = [r for r in items if r.dossier_id == dossier_id]
        if status_in := filters.get("status_in"):
            allowed = set(status_in)
            items = [r for r in items if r.status.value in allowed]
        return Page(
            items=items[offset : offset + limit],
            total=len(items),
            limit=limit,
            offset=offset,
        )

    async def update_status(
        self, run_id: str, status: str, *, error_code: str | None = None
    ) -> None:
        run = self.runs[run_id]
        run.status = PipelineRunStatus(status)
        _ = error_code

    async def list_steps(self, run_id: str) -> list[dict[str, Any]]:
        return []


class FakeDocRepo:
    def __init__(self, docs: list[Any] | None = None) -> None:
        self.docs = docs or []

    async def list_by_dossier(self, dossier_id: str) -> list[Any]:
        return list(self.docs)


def _doc() -> Any:
    from types import SimpleNamespace

    from contract_intelligence.contract.domain.entities.document import DocumentRole

    return SimpleNamespace(
        id="doc_1",
        sha256="abc",
        blob_uri="s3://x",
        filename="a.pdf",
        role=DocumentRole.CONTRACT,
        page_count=1,
    )


def _svc(repo: FakePipelineRunRepo, docs: list[Any] | None = None) -> ExtractionService:
    return ExtractionService(
        pipeline_run_repo=repo,
        page_repo=AsyncMock(),
        ocr_line_repo=AsyncMock(),
        fact_repo=AsyncMock(),
        citation_repo=AsyncMock(),
        clause_repo=AsyncMock(),
        table_repo=AsyncMock(),
        document_repo=FakeDocRepo(docs if docs is not None else [_doc()]),
        storage=None,
        orchestrator=AsyncMock(run=AsyncMock()),
        tenant_id="tenant_test",
    )


class TestTriggerPipelineRun:
    async def test_creates_queued_run(self) -> None:
        repo = FakePipelineRunRepo()
        svc = _svc(repo)
        run = await svc.trigger_pipeline_run(dossier_id="dos_1", background_tasks=None)
        assert run.status == PipelineRunStatus.QUEUED
        assert repo.create_calls == 1

    async def test_rejects_when_active_run_exists(self) -> None:
        repo = FakePipelineRunRepo()
        active = PipelineRun(
            id="run_active",
            tenant_id="tenant_test",
            dossier_id="dos_1",
            status=PipelineRunStatus.RUNNING,
        )
        repo.runs[active.id] = active
        svc = _svc(repo)
        with pytest.raises(InvalidStateTransition):
            await svc.trigger_pipeline_run(dossier_id="dos_1")

    async def test_raises_when_no_documents(self) -> None:
        repo = FakePipelineRunRepo()
        svc = _svc(repo, docs=[])
        with pytest.raises(NotFoundError):
            await svc.trigger_pipeline_run(dossier_id="dos_empty")


class TestReprocess:
    async def test_returns_accepted_dto(self) -> None:
        repo = FakePipelineRunRepo()
        svc = _svc(repo)
        accepted = await svc.reprocess_dossier(dossier_id="dos_1")
        assert accepted.dossier_id == "dos_1"
        assert accepted.job_id is not None
        assert accepted.job_id.startswith("run_")


class TestCancel:
    async def test_cancels_queued(self) -> None:
        repo = FakePipelineRunRepo()
        run = PipelineRun(
            id="run_1",
            tenant_id="tenant_test",
            dossier_id="dos_1",
            status=PipelineRunStatus.QUEUED,
        )
        repo.runs[run.id] = run
        svc = _svc(repo)
        cancelled = await svc.cancel_pipeline_run("run_1")
        assert cancelled.status == PipelineRunStatus.CANCELLED

    async def test_rejects_terminal_with_409(self) -> None:
        repo = FakePipelineRunRepo()
        run = PipelineRun(
            id="run_1",
            tenant_id="tenant_test",
            dossier_id="dos_1",
            status=PipelineRunStatus.SUCCEEDED,
        )
        repo.runs[run.id] = run
        svc = _svc(repo)
        with pytest.raises(InvalidStateTransition):
            await svc.cancel_pipeline_run("run_1")


class TestListFilter:
    async def test_maps_completed_to_succeeded(self) -> None:
        repo = FakePipelineRunRepo()
        done = PipelineRun(
            id="run_done",
            tenant_id="tenant_test",
            dossier_id="dos_1",
            status=PipelineRunStatus.SUCCEEDED,
        )
        queued = PipelineRun(
            id="run_q",
            tenant_id="tenant_test",
            dossier_id="dos_1",
            status=PipelineRunStatus.QUEUED,
        )
        repo.runs[done.id] = done
        repo.runs[queued.id] = queued
        svc = _svc(repo)
        items, total = await svc.list_pipeline_runs(status="completed")
        assert total == 1
        assert items[0].id == "run_done"

    async def test_to_summary_maps_succeeded_to_completed(self) -> None:
        run = PipelineRun(
            id="run_1",
            tenant_id="tenant_test",
            dossier_id="dos_1",
            status=PipelineRunStatus.SUCCEEDED,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        summary = ExtractionService.to_summary(run)
        assert summary.status == "completed"
        assert summary.run_id == "run_1"
