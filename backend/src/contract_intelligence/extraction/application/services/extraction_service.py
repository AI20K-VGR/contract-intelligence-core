"""Extraction application service — pipeline runs, facts, citations, clauses, pages."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
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
from contract_intelligence.extraction.application.dtos.run_dtos import (
    PipelineRunSummaryDTO,
    ReprocessAcceptedDTO,
)
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
from contract_intelligence.shared.base import new_ulid
from contract_intelligence.shared.exceptions import InvalidStateTransition, NotFoundError
from contract_intelligence.shared.storage import FileStorage

logger = structlog.get_logger(__name__)

# Hands a committed, queued run to the Kafka worker (publishes ``dossier.uploaded``).
RunPublisher = Callable[[str], Awaitable[None]]


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
        run_publisher: RunPublisher | None = None,
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
        self._run_publisher = run_publisher
        self._tenant_id = tenant_id

    # ----- Pipeline runs ------------------------------------------------------

    async def trigger_pipeline_run(
        self,
        *,
        dossier_id: str,
        pipeline_version: str = "v1.0.0",
        git_sha: str | None = None,
        trace_id: str | None = None,
        config_override: dict[str, Any] | None = None,
    ) -> PipelineRun:
        """Queue a pipeline run and hand it to the Kafka worker.

        The run is committed as ``queued`` (job back to ``uploaded``), then
        ``dossier.uploaded`` is published; the worker resumes exactly this run
        and sends the AI1 OCR commands. Nothing runs inside the API process.

        Raises:
            InvalidStateTransition: if an active (queued/running) run already exists.
            NotFoundError: if dossier has no documents.
        """
        _ = config_override  # persisted later via config_snapshot when ORM supports it
        await self._ensure_no_active_run(dossier_id)
        await self._ensure_has_documents(dossier_id)

        run_id = new_ulid("run_")
        run = await self._pipeline_run_repo.create(
            run_id=run_id,
            dossier_id=dossier_id,
            pipeline_version=pipeline_version,
            git_sha=git_sha,
            trace_id=trace_id or str(uuid.uuid4()),
        )
        run = cast(PipelineRun, run)

        # Commit before publishing: the worker reads the run through its own session.
        await self._commit()

        if self._run_publisher is None:
            msg = "run_publisher is not wired — ExtractionService cannot dispatch runs"
            raise RuntimeError(msg)
        try:
            await self._run_publisher(dossier_id)
        except Exception:
            # A queued run nobody will pick up would block every later trigger
            # (_ensure_no_active_run), so close it before surfacing the error.
            await self._pipeline_run_repo.update_status(
                run_id, "failed", error_code="DISPATCH_FAILED"
            )
            await self._commit()
            logger.exception("pipeline_run.dispatch_failed", run_id=run_id, dossier_id=dossier_id)
            raise

        logger.info(
            "pipeline_run.dispatched",
            run_id=run_id,
            dossier_id=dossier_id,
            tenant_id=self._tenant_id,
        )
        return run

    async def reprocess_dossier(
        self,
        *,
        dossier_id: str,
        trace_id: str | None = None,
    ) -> ReprocessAcceptedDTO:
        """Create a new immutable pipeline run for an existing dossier (reprocess)."""
        run = await self.trigger_pipeline_run(dossier_id=dossier_id, trace_id=trace_id)
        return ReprocessAcceptedDTO(dossier_id=dossier_id, job_id=run.id)

    async def _commit(self) -> None:
        session = getattr(self._pipeline_run_repo, "_session", None)
        if session is not None:
            await session.commit()

    async def _ensure_no_active_run(self, dossier_id: str) -> None:
        active = await self._pipeline_run_repo.list_pipeline_runs(
            dossier_id=dossier_id,
            status_in=("queued", "running"),
            limit=1,
            offset=0,
        )
        if getattr(active, "total", 0) > 0 or (getattr(active, "items", None) or []):
            raise InvalidStateTransition(
                from_state="active_run",
                to_state="queued",
                entity="PipelineRun",
            )

    @staticmethod
    def to_summary(run: PipelineRun, *, triggered_by: str | None = None) -> PipelineRunSummaryDTO:
        return PipelineRunSummaryDTO.from_domain(run, triggered_by=triggered_by)

    async def _ensure_has_documents(self, dossier_id: str) -> None:
        if self._document_repo is None:
            raise RuntimeError(
                "document_repo is None — wiring thiếu. "
                "ExtractionService cần DocumentRepositoryImpl được inject."
            )
        # Cross-BC read: a run needs at least one document to OCR.
        if not await self._document_repo.list_by_dossier(dossier_id):
            raise NotFoundError(
                entity_type="Document",
                entity_id=f"dossier {dossier_id} has no documents",
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
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PipelineRun], int]:
        from typing import cast

        # OpenAPI ``completed`` ↔ internal ``succeeded``
        status_in: tuple[str, ...] | None = None
        if status:
            db_status = "succeeded" if status == "completed" else status
            status_in = (db_status,)

        page = cast(
            Any,
            await self._pipeline_run_repo.list_pipeline_runs(
                dossier_id=dossier_id,
                status_in=status_in,
                limit=limit,
                offset=offset,
            ),
        )
        return page.items, page.total

    async def get_pipeline_steps(self, run_id: str) -> list[dict[str, Any]]:
        await self.get_pipeline_run(run_id)  # Verify exists + tenant
        from typing import cast

        return cast(list[dict[str, Any]], await self._pipeline_run_repo.list_steps(run_id))

    async def cancel_pipeline_run(self, run_id: str, *, actor_id: str = "system") -> PipelineRun:
        """Cancel a queued/running run; its job fails with ``RUN_CANCELLED``."""
        run = await self.get_pipeline_run(run_id)
        if run.status not in (PipelineRunStatus.RUNNING, PipelineRunStatus.QUEUED):
            raise InvalidStateTransition(
                from_state=run.status.value,
                to_state="cancelled",
                entity="PipelineRun",
            )
        await self._pipeline_run_repo.cancel(run_id, actor_id=actor_id)
        run.status = PipelineRunStatus.CANCELLED
        return run

    # ----- Read endpoints (Phase 2) ------------------------------------------

    async def list_pages(self, document_id: str) -> list[PageDTO]:
        rows = await self._page_repo.list_by_document(document_id)
        return [PageDTO.from_row(r) for r in rows]

    async def list_document_lines(self, document_id: str) -> list[dict[str, Any]]:
        """Pages (size) with their OCR lines: what ``/pages/{id}`` gives, for all pages.

        Two queries instead of one request per page: a 200-page contract made
        the structure view wait for 200 round trips.
        """
        pages = await self._page_repo.list_by_document(document_id)
        by_page: dict[int, list[dict[str, Any]]] = {}
        for line in await self._page_repo.list_lines_by_document(document_id):
            by_page.setdefault(int(line.pop("page_no")), []).append(line)
        return [
            {
                "page_no": page["page_no"],
                "width_pt": page["width_pt"],
                "height_pt": page["height_pt"],
                "ocr_lines": by_page.get(int(page["page_no"]), []),
            }
            for page in pages
        ]

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
