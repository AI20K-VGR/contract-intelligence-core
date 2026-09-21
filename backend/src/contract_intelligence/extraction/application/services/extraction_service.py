"""Extraction application service — pipeline runs, facts, citations, clauses, pages."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, cast

import structlog

from contract_intelligence.contract.domain.repositories.document_repository import (
    DocumentRepository,
)
from contract_intelligence.extraction.application.dtos.clause_dtos import (
    ClauseNodeDTO,
    build_clause_tree,
)
from contract_intelligence.extraction.application.dtos.fact_effective_dtos import (
    FactEffectiveDTO,
)
from contract_intelligence.extraction.application.dtos.page_dtos import PageDTO
from contract_intelligence.extraction.application.dtos.table_dtos import DocTableDTO
from contract_intelligence.extraction.domain.entities.pipeline_run import (
    PipelineRun,
    PipelineRunStatus,
)
from contract_intelligence.extraction.domain.repositories.citation_repository import (
    CitationRepository,
)
from contract_intelligence.extraction.domain.repositories.fact_repository import (
    FactRepository,
)
from contract_intelligence.extraction.domain.repositories.page_repository import (
    PageRepository,
)

# Import trực tiếp từ sub-module để tránh chain qua shared.ai.__init__
# (eagerly imports persistence → ORM).
from contract_intelligence.shared.ai.pipeline_orchestrator import (
    DocumentJob,
    PipelineContext,
    PipelineOrchestrator,
    get_pipeline_orchestrator,
)
from contract_intelligence.shared.base import new_ulid
from contract_intelligence.shared.exceptions import NotFoundError
from contract_intelligence.shared.storage import FileStorage

logger = structlog.get_logger(__name__)


class ExtractionService:
    """Use-case orchestration cho Extraction BC.

    Tất cả repo params giờ là Protocol từ domain — application không leak ORM/infrastructure.
    """

    def __init__(
        self,
        *,
        pipeline_run_repo: Any,  # PipelineRunRepository — domain Protocol
        page_repo: PageRepository,
        ocr_line_repo: Any,  # OcrLineRepository — domain Protocol (chưa extract)
        fact_repo: FactRepository,
        citation_repo: CitationRepository,
        clause_repo: Any,  # ClauseNodeRepository — chưa extract Protocol
        table_repo: Any,  # DocTableRepository — chưa extract Protocol
        document_repo: DocumentRepository | None = None,
        storage: FileStorage | None = None,
        orchestrator: PipelineOrchestrator | None = None,
        tenant_id: str,
    ) -> None:
        self._pipeline_run_repo = pipeline_run_repo
        self._page_repo = page_repo
        self._ocr_line_repo = ocr_line_repo
        self._fact_repo = fact_repo
        self._citation_repo = citation_repo
        self._clause_repo = clause_repo
        self._table_repo = table_repo
        self._document_repo = document_repo
        self._storage = storage
        self._orchestrator = orchestrator or get_pipeline_orchestrator()
        self._tenant_id = tenant_id

    # ----- Pipeline runs ------------------------------------------------------

    async def trigger_pipeline_run(
        self,
        *,
        dossier_id: str,
        pipeline_version: str = "v1.0.0",
        git_sha: str | None = None,
        trace_id: str | None = None,
        background_tasks: Any | None = None,
    ) -> PipelineRun:
        """Tạo pipeline_run + dispatch orchestrator chạy nền.

        Args:
            dossier_id: ID của dossier cần xử lý.
            pipeline_version: SemVer của pipeline (default: v1.0.0).
            git_sha: Optional git SHA để truy vết.
            trace_id: W3C TraceContext cho OpenTelemetry.
            background_tasks: FastAPI BackgroundTasks instance — nếu None,
                orchestrator chạy inline (dùng cho test).

        Returns:
            PipelineRun vừa tạo — status=queued.
        """
        run_id = new_ulid("run_")
        run = await self._pipeline_run_repo.create(
            run_id=run_id,
            dossier_id=dossier_id,
            pipeline_version=pipeline_version,
            git_sha=git_sha,
            trace_id=trace_id or str(uuid.uuid4()),
        )

        run = cast(PipelineRun, run)

        # Build context — gather documents
        ctx = await self._build_context(run_id=run_id, dossier_id=dossier_id, trace_id=trace_id)

        if background_tasks is not None:
            # Production path — chạy nền qua FastAPI BackgroundTasks
            background_tasks.add_task(self._run_orchestrator_safely, ctx)
            logger.info(
                "pipeline_run.scheduled",
                run_id=run_id,
                dossier_id=dossier_id,
                tenant_id=self._tenant_id,
                mode="background",
            )
        else:
            # Test/sync path — chạy inline
            asyncio.create_task(self._run_orchestrator_safely(ctx))
            logger.info(
                "pipeline_run.scheduled",
                run_id=run_id,
                dossier_id=dossier_id,
                tenant_id=self._tenant_id,
                mode="inline",
            )

        return run

    async def _run_orchestrator_safely(self, ctx: PipelineContext) -> None:
        """Run orchestrator với error handling — không để crash background task."""
        try:
            await self._orchestrator.run(ctx)
        except Exception as exc:
            logger.exception(
                "pipeline_run.orchestrator_error",
                run_id=ctx.run_id,
                dossier_id=ctx.dossier_id,
                error=str(exc),
            )

    async def _build_context(
        self,
        *,
        run_id: str,
        dossier_id: str,
        trace_id: str | None,
    ) -> PipelineContext:
        """Load documents từ DB → build DocumentJob list cho orchestrator."""
        if self._document_repo is None:
            # Defensive — nếu DI thiếu, thử lấy từ engine
            raise RuntimeError(
                "document_repo is None — wiring thiếu. "
                "ExtractionService cần DocumentRepositoryImpl được inject."
            )

        # Load documents cho dossier (cross-BC read)
        documents = await self._document_repo.list_by_dossier(dossier_id)
        if not documents:
            raise NotFoundError(
                entity_type="Document",
                entity_id=f"dossier {dossier_id} has no documents",
            )

        doc_jobs = [
            DocumentJob(
                document_id=d.id,
                sha256=d.sha256,
                blob_uri=d.blob_uri,
                filename=d.filename,
                role=d.role.value,
                page_count=d.page_count,
            )
            for d in documents
        ]

        return PipelineContext(
            run_id=run_id,
            dossier_id=dossier_id,
            tenant_id=self._tenant_id,
            documents=doc_jobs,
            trace_id=trace_id,
        )

    async def get_pipeline_run(self, run_id: str) -> PipelineRun:
        run = await self._pipeline_run_repo.get(run_id)
        if run is None:
            raise NotFoundError(entity_type="PipelineRun", entity_id=run_id)
        from typing import cast

        return cast(PipelineRun, run)

    async def list_pipeline_runs(
        self,
        *,
        dossier_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PipelineRun], int]:
        from typing import cast

        page = cast(
            Any,
            await self._pipeline_run_repo.list_pipeline_runs(
                dossier_id=dossier_id, limit=limit, offset=offset
            ),
        )
        return page.items, page.total

    async def get_pipeline_steps(self, run_id: str) -> list[dict[str, Any]]:
        await self.get_pipeline_run(run_id)  # Verify exists + tenant
        from typing import cast

        return cast(list[dict[str, Any]], await self._pipeline_run_repo.list_steps(run_id))

    async def cancel_pipeline_run(self, run_id: str) -> PipelineRun:
        run = await self.get_pipeline_run(run_id)
        if run.status not in (PipelineRunStatus.RUNNING, PipelineRunStatus.QUEUED):
            raise NotFoundError(
                entity_type="PipelineRun", entity_id=f"{run_id} not cancellable ({run.status})"
            )
        await self._pipeline_run_repo.update_status(run_id, "cancelled")
        run.status = PipelineRunStatus.CANCELLED
        return run

    # ----- Read endpoints (Phase 2) ------------------------------------------

    async def list_pages(self, document_id: str) -> list[PageDTO]:
        rows = await self._page_repo.list_by_document(document_id)
        return [PageDTO.from_row(r) for r in rows]

    async def get_page(self, page_id: str) -> dict[str, Any]:
        data = await self._page_repo.get(page_id)
        if data is None:
            raise NotFoundError(entity_type="Page", entity_id=page_id)
        return data

    async def get_page_image(
        self,
        document_id: str,
        page_no: int,
        *,
        variant: str = "preview",
    ) -> tuple[bytes, str]:
        """Stream page image bytes from storage.

        Returns:
            (image_bytes, media_type) — media_type is image/png or image/webp.
        """
        if self._storage is None:
            raise RuntimeError("storage is None — ExtractionService needs FileStorage injected")

        page = await self._page_repo.get_by_document_and_page_no(document_id, page_no)
        if page is None:
            raise NotFoundError(
                entity_type="Page",
                entity_id=f"{document_id}#{page_no}",
            )

        uri = page.get("preview_uri") if variant == "preview" else page.get("render_uri")
        if not uri:
            # Fall back to the other variant if requested one is missing
            uri = page.get("render_uri") or page.get("preview_uri")
        if not uri:
            raise NotFoundError(
                entity_type="PageImage",
                entity_id=f"{document_id}#{page_no}/{variant}",
            )

        try:
            data = await self._storage.get(uri)
        except FileNotFoundError as exc:
            raise NotFoundError(
                entity_type="PageImage",
                entity_id=f"{document_id}#{page_no}/{variant}",
            ) from exc

        media_type = "image/webp" if str(uri).lower().endswith(".webp") else "image/png"
        return data, media_type

    async def list_facts(self, document_id: str) -> list[dict[str, Any]]:
        return await self._fact_repo.list_by_document(document_id)

    async def list_dossier_facts(
        self,
        dossier_id: str,
        *,
        key: str | None = None,
        effective: bool = True,
    ) -> list[FactEffectiveDTO]:
        """List FactEffective for a dossier — includes current_version for concurrency."""
        rows = await self._fact_repo.list_effective_by_dossier(
            dossier_id, key=key, effective=effective
        )
        return [FactEffectiveDTO.from_row(r, effective=effective) for r in rows]

    async def get_fact(self, fact_id: str) -> dict[str, Any]:
        data = await self._fact_repo.get(fact_id)
        if data is None:
            raise NotFoundError(entity_type="Fact", entity_id=fact_id)
        return data

    async def get_citation(self, citation_id: str) -> dict[str, Any]:
        data = await self._citation_repo.get(citation_id)
        if data is None:
            raise NotFoundError(entity_type="Citation", entity_id=citation_id)
        return data

    async def list_clauses(
        self, document_id: str, *, run_id: str | None = None
    ) -> list[ClauseNodeDTO]:
        flat = cast(list[dict[str, Any]], await self._clause_repo.list_by_document(document_id))
        # run_id reserved for future pipeline-scoped filtering
        _ = run_id
        return build_clause_tree(flat)

    async def list_tables(
        self, document_id: str, *, run_id: str | None = None
    ) -> list[DocTableDTO]:
        rows = cast(list[dict[str, Any]], await self._table_repo.list_by_document(document_id))
        _ = run_id
        return [DocTableDTO.from_row(r) for r in rows]


__all__ = ["ExtractionService"]
