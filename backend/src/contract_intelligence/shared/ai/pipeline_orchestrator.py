"""Pipeline orchestrator — drive AI service OCR → Extract → Compare chain.

Module này là **Async Pipeline Driver** triển khai mô hình Push Job & Polling
Status (DOC-05c §2). Được gọi bởi ``BackgroundDispatcher`` mỗi khi có pipeline
run mới được trigger.

Flow (theo tài liệu):
    1. Pipeline run được tạo từ POST /dossiers/{id}/runs (POST 202 ngay)
    2. Orchestrator chạy nền (FastAPI BackgroundTasks):
        a. Pre-flight: tạo tasks DB + presigned URLs (Sprint 4 — MinIO)
        b. Submit OCR job cho từng document → poll tới COMPLETED
        c. Submit Extract job cho từng document → poll → persist facts/citations
        d. Submit Compare job cho dossier (nếu có annex) → poll
        e. Mark run = SUCCEEDED
    3. Frontend polling GET /runs/{id} thấy status chuyển running → succeeded

Mỗi step được update vào ``pipeline_step`` table (S0..S10) cho dashboard.
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from contract_intelligence.config.settings import Settings, get_settings
from contract_intelligence.shared.ai.client import (
    AiServiceClient,
    get_ai_service_client,
)
from contract_intelligence.shared.ai.persistence import (
    persist_ai1_snapshot,
    persist_ai2_comparison,
    persist_ai2_extraction,
    persist_usage_ledger,
    update_pipeline_run_status,
    update_pipeline_step,
)
from contract_intelligence.shared.ai.schemas import (
    Ai1SnapshotPayload,
    Ai2ComparisonPayload,
    Ai2ExtractionPayload,
    CompareJobRequest,
    ExtractJobRequest,
    JobStatus,
    JobStatusReport,
    OcrJobRequest,
)
from contract_intelligence.shared.base import new_ulid

logger = structlog.get_logger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Raw SQL constants — dùng text() để tránh cross-BC ORM import (import-linter).
# Tránh import DossierORM từ contract.infrastructure.persistence.orm
# ──────────────────────────────────────────────────────────────────────────────

_DOSSIER_STATUS_UPDATE = text(
    "UPDATE dossier SET status = :status, updated_at = CURRENT_TIMESTAMP "
    "WHERE id = :dossier_id AND tenant_id = :tenant_id"
)

_DOSSIER_CONFLICTS_UPDATE = text(
    "UPDATE dossier SET has_conflicts = :has_conflicts, updated_at = CURRENT_TIMESTAMP "
    "WHERE id = :dossier_id AND tenant_id = :tenant_id"
)


# ──────────────────────────────────────────────────────────────────────────────
# Context
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class DocumentJob:
    """1 document cần xử lý — packed để orchestrator chạy vòng lặp."""

    document_id: str
    sha256: str
    blob_uri: str
    filename: str
    role: str  # "CONTRACT" | "ANNEX"
    page_count: int = 0


@dataclass(slots=True)
class PipelineContext:
    """Tất cả tham chiếu orchestrator cần — không giữ DB session cross-await."""

    run_id: str
    dossier_id: str
    tenant_id: str
    documents: list[DocumentJob]
    trace_id: str | None = None
    llm_config: dict[str, Any] | None = None
    snapshot_digest: str = ""
    full_text_nfc: str = ""


# ──────────────────────────────────────────────────────────────────────────────
# Orchestrator
# ──────────────────────────────────────────────────────────────────────────────


class PipelineOrchestrator:
    """Drive OCR → Extract → Compare chain — bound to AI client + DB engine.

    Pattern:
        orchestrator = PipelineOrchestrator(client, engine, settings)
        await orchestrator.run(ctx)  # blocks until pipeline done OR timeout
    """

    def __init__(
        self,
        *,
        client: AiServiceClient,
        engine: AsyncEngine,
        settings: Settings,
    ) -> None:
        self._client = client
        self._engine = engine
        self._settings = settings
        self._session_factory = async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )

    async def run_with_documents(
        self,
        *,
        run_id: str,
        dossier_id: str,
        tenant_id: str,
        documents: list[DocumentJob],
        trace_id: str | None = None,
    ) -> None:
        """Entry point cho cả upload router lẫn run trigger router.

        Documents đã được load sẵn bởi caller — không truy vấn DB ở đây.
        Tránh cross-BC dependency từ upload router vào ExtractionService.
        """
        ctx = PipelineContext(
            run_id=run_id,
            dossier_id=dossier_id,
            tenant_id=tenant_id,
            documents=documents,
            trace_id=trace_id,
        )
        await self.run(ctx)

    async def run(self, ctx: PipelineContext) -> None:
        """Chạy toàn bộ pipeline — gọi từ BackgroundDispatcher."""
        try:
            await self._mark_step(ctx, "S0", "running")
            await update_pipeline_run_status_via_engine(
                self._engine,
                tenant_id=ctx.tenant_id,
                run_id=ctx.run_id,
                status="running",
            )
            await self._mark_step(ctx, "S0", "succeeded")

            snapshot_digests: dict[str, str] = {}
            full_text_per_doc: dict[str, str] = {}
            all_facts: dict[str, list[dict[str, Any]]] = {}

            # ── Phase 1: OCR cho mỗi document ──────────────────────────────
            for idx, doc in enumerate(ctx.documents):
                await self._mark_step(ctx, "S2", "running")
                try:
                    snapshot = await self._run_ocr(ctx, doc)
                    snapshot_digests[doc.document_id] = self._compute_digest(snapshot)
                    full_text_per_doc[doc.document_id] = snapshot.full_text_nfc
                    await self._mark_step(ctx, "S8", "running")
                    snap_dump = snapshot.model_dump(mode="json")
                    run_id = ctx.run_id
                    await self._with_session(
                        lambda s, _sd=snap_dump, _rid=run_id: persist_ai1_snapshot(
                            s,
                            tenant_id=ctx.tenant_id,
                            snapshot=_sd,
                            run_id=_rid,
                        )
                    )
                    await self._mark_step(ctx, "S8", "succeeded")
                    await self._mark_step(ctx, "S3", "succeeded")
                except Exception as exc:
                    logger.exception(
                        "pipeline.ocr_failed",
                        document_id=doc.document_id,
                        run_id=ctx.run_id,
                        error=str(exc),
                    )
                    await self._mark_step(ctx, "S2", "failed")
                    await self._fail_pipeline(ctx, "OCR_FAILED", str(exc))
                    return
                # Yield để scheduler không block
                if idx < len(ctx.documents) - 1:
                    await asyncio.sleep(0)

            # ── Phase 2: Extract cho mỗi document ──────────────────────────
            for doc in ctx.documents:
                await self._mark_step(ctx, "S4", "running")
                try:
                    extraction = await self._run_extract(ctx, doc)
                    all_facts[doc.document_id] = [
                        f.model_dump(mode="json") for f in extraction.facts
                    ]
                    await self._mark_step(ctx, "S9", "running")
                    ext_dump = extraction.model_dump(mode="json")
                    run_id = ctx.run_id
                    await self._with_session(
                        lambda s, _ed=ext_dump, _rid=run_id: persist_ai2_extraction(
                            s,
                            tenant_id=ctx.tenant_id,
                            extraction=_ed,
                            run_id=_rid,
                        )
                    )
                    await self._mark_step(ctx, "S9", "succeeded")
                    await self._mark_step(ctx, "S5", "succeeded")
                except Exception as exc:
                    logger.exception(
                        "pipeline.extract_failed",
                        document_id=doc.document_id,
                        run_id=ctx.run_id,
                        error=str(exc),
                    )
                    await self._mark_step(ctx, "S4", "failed")
                    await self._fail_pipeline(ctx, "EXTRACT_FAILED", str(exc))
                    return

            # ── Phase 3: Compare (nếu có annex + contract) ─────────────────
            has_contract = any(d.role == "CONTRACT" for d in ctx.documents)
            has_annex = any(d.role == "ANNEX" for d in ctx.documents)

            if has_contract and has_annex:
                await self._mark_step(ctx, "S6", "running")
                try:
                    comparison = await self._run_compare(ctx, all_facts)
                    await self._mark_step(ctx, "S10", "running")
                    cmp_dump = comparison.model_dump(mode="json")
                    run_id = ctx.run_id
                    await self._with_session(
                        lambda s, _cd=cmp_dump, _rid=run_id: persist_ai2_comparison(
                            s,
                            tenant_id=ctx.tenant_id,
                            comparison=_cd,
                            run_id=_rid,
                        )
                    )
                    # Update dossier.has_conflicts based on findings
                    await self._mark_dossier_has_conflicts(ctx, len(comparison.findings) > 0)
                    await self._mark_step(ctx, "S10", "succeeded")
                    await self._mark_step(ctx, "S7", "succeeded")
                except Exception as exc:
                    logger.exception(
                        "pipeline.compare_failed",
                        dossier_id=ctx.dossier_id,
                        run_id=ctx.run_id,
                        error=str(exc),
                    )
                    await self._mark_step(ctx, "S6", "failed")
                    await self._fail_pipeline(ctx, "COMPARE_FAILED", str(exc))
                    return

            # ── Finalize ────────────────────────────────────────────────────
            await update_pipeline_run_status_via_engine(
                self._engine,
                tenant_id=ctx.tenant_id,
                run_id=ctx.run_id,
                status="succeeded",
            )
            await self._mark_dossier_status(ctx, "extracted")
            logger.info("pipeline.succeeded", run_id=ctx.run_id, dossier_id=ctx.dossier_id)

        except Exception as exc:
            logger.exception("pipeline.unhandled_error", run_id=ctx.run_id, error=str(exc))
            await self._fail_pipeline(ctx, "INTERNAL_CRASH", str(exc))

    # ─── Phase implementations ─────────────────────────────────────────────

    async def _run_ocr(
        self,
        ctx: PipelineContext,
        doc: DocumentJob,
    ) -> Ai1SnapshotPayload:
        """Submit OCR + poll + return canonical payload.

        Headers tuân thủ DOC-05c §3:
            X-Tenant-Id, X-Task-Id, X-Attempt-Id, X-Internal-Service-Key
        """
        task_id = self._next_task_id()
        req = OcrJobRequest(
            task_id=task_id,
            attempt_id=1,
            tenant_id=ctx.tenant_id,
            document_id=doc.document_id,
            source_blob_get_url=f"http://minio.internal/{doc.blob_uri}",  # Sprint 4: presigned
            source_sha256=doc.sha256,
            pages_to_process=list(range(1, max(1, doc.page_count) + 1)),
            render_target={
                "dpi": 150,
                "format": "PNG",
                "presigned_put_urls": {
                    str(i): f"http://minio.internal/renders/{doc.document_id}_{i}.png?token=stub"
                    for i in range(1, max(1, doc.page_count) + 1)
                },
            },
            options={"language": "vi", "detect_tables": True, "extract_clauses": True},
        )

        submission = await self._client.submit_ocr(req)
        report = await self._poll_to_completion(submission.job_id, ctx=ctx)

        if report.status is JobStatus.FAILED:
            code = (report.error or {}).get("code", "OCR_FAILED")
            raise RuntimeError(f"OCR job failed: {code}")

        result = report.result or {}
        snapshot = Ai1SnapshotPayload.model_validate(result)

        # Persist usage ledger
        if report.usage:
            await self._with_session(
                lambda s: persist_usage_ledger(
                    s,
                    tenant_id=ctx.tenant_id,
                    usage=report.usage,
                    task_id=task_id,
                    job_kind="ocr",
                )
            )
        return snapshot

    async def _run_extract(
        self,
        ctx: PipelineContext,
        doc: DocumentJob,
    ) -> Ai2ExtractionPayload:
        """Submit extract job for a document (after its OCR completed)."""
        task_id = self._next_task_id()
        req = ExtractJobRequest(
            task_id=task_id,
            attempt_id=1,
            tenant_id=ctx.tenant_id,
            document_id=doc.document_id,
            snapshot_digest=ctx.snapshot_digest or self._compute_digest_for_doc(doc),
            document_text_nfc=ctx.full_text_nfc,
            clause_tree=[],
            requested_schema_keys=[
                "price.total",
                "date.signing",
                "date.effective",
                "party.buyer.name",
                "party.seller.name",
                "term.delivery",
                "penalty.breach",
            ],
            llm_config=ctx.llm_config
            or {
                "model": "gpt-5.6-terra",
                "temperature": 0.0,
                "prompt_version": "extract.v2.1",
            },
        )

        submission = await self._client.submit_extract(req)
        report = await self._poll_to_completion(submission.job_id, ctx=ctx)

        if report.status is JobStatus.FAILED:
            code = (report.error or {}).get("code", "EXTRACT_FAILED")
            raise RuntimeError(f"Extract job failed: {code}")

        result = report.result or {}
        extraction = Ai2ExtractionPayload.model_validate(result)

        if report.usage:
            await self._with_session(
                lambda s: persist_usage_ledger(
                    s,
                    tenant_id=ctx.tenant_id,
                    usage=report.usage,
                    task_id=task_id,
                    job_kind="extract",
                )
            )
        return extraction

    async def _run_compare(
        self,
        ctx: PipelineContext,
        facts_per_doc: dict[str, list[dict[str, Any]]],
    ) -> Ai2ComparisonPayload:
        """Submit compare job for dossier (contract vs annex)."""
        task_id = self._next_task_id()
        contract_doc = next((d for d in ctx.documents if d.role == "CONTRACT"), None)
        annex_docs = [d for d in ctx.documents if d.role == "ANNEX"]

        if contract_doc is None or not annex_docs:
            raise RuntimeError("Compare requires 1 CONTRACT + ≥1 ANNEX")

        req = CompareJobRequest(
            task_id=task_id,
            attempt_id=1,
            tenant_id=ctx.tenant_id,
            dossier_id=ctx.dossier_id,
            contract_document={
                "document_id": contract_doc.document_id,
                "facts": facts_per_doc.get(contract_doc.document_id, []),
                "clauses": [],
            },
            annex_documents=[
                {
                    "document_id": d.document_id,
                    "facts": facts_per_doc.get(d.document_id, []),
                    "clauses": [],
                }
                for d in annex_docs
            ],
            comparison_keys=[
                "price.total",
                "term.delivery",
                "penalty.breach",
                "date.effective",
                "date.expiration",
            ],
        )

        submission = await self._client.submit_compare(req)
        report = await self._poll_to_completion(submission.job_id, ctx=ctx)

        if report.status is JobStatus.FAILED:
            code = (report.error or {}).get("code", "COMPARE_FAILED")
            raise RuntimeError(f"Compare job failed: {code}")

        result = report.result or {}
        comparison = Ai2ComparisonPayload.model_validate(result)

        if report.usage:
            await self._with_session(
                lambda s: persist_usage_ledger(
                    s,
                    tenant_id=ctx.tenant_id,
                    usage=report.usage,
                    task_id=task_id,
                    job_kind="compare",
                )
            )
        return comparison

    # ─── Polling helper ────────────────────────────────────────────────────

    async def _poll_to_completion(
        self,
        job_id: str,
        *,
        ctx: PipelineContext,
    ) -> JobStatusReport:
        """Poll AI service tới khi COMPLETED/FAILED/CANCELLED.

        Implements Exponential Backoff theo DOC-05b §7:
            1s → 1s → 2s → 3s → 5s (cap)
        """
        max_polls = self._settings.ai_dispatcher_max_polls
        interval = self._settings.ai_dispatcher_poll_interval_seconds
        # Compute backoff intervals
        backoff = [interval, interval, interval * 2, interval * 2, interval * 3, interval * 5]

        for i in range(max_polls):
            await asyncio.sleep(backoff[min(i, len(backoff) - 1)])
            report = await self._client.get_job_status(job_id)
            if report.status in (
                JobStatus.COMPLETED,
                JobStatus.FAILED,
                JobStatus.CANCELLED,
            ):
                return report
        # Timeout — cancel + return failure
        logger.warning(
            "pipeline.poll_timeout",
            job_id=job_id,
            run_id=ctx.run_id,
            max_polls=max_polls,
        )
        await self._client.cancel_job(job_id)
        return JobStatusReport(
            job_id=job_id,
            kind="unknown",
            status=JobStatus.FAILED,
            error={"code": "POLL_TIMEOUT", "message": "AI service did not complete in time"},
        )

    # ─── Helpers ────────────────────────────────────────────────────────────

    async def _mark_step(self, ctx: PipelineContext, step: str, status: str) -> None:
        try:
            await self._with_session(
                lambda s: update_pipeline_step(
                    s,
                    tenant_id=ctx.tenant_id,
                    run_id=ctx.run_id,
                    step=step,
                    status=status,
                )
            )
        except Exception as exc:
            logger.warning(
                "pipeline.mark_step_failed",
                step=step,
                status=status,
                error=str(exc),
            )

    async def _fail_pipeline(self, ctx: PipelineContext, code: str, detail: str) -> None:
        try:
            await update_pipeline_run_status_via_engine(
                self._engine,
                tenant_id=ctx.tenant_id,
                run_id=ctx.run_id,
                status="failed",
                error_code=code,
                error_detail=detail[:1000],
            )
        except Exception as exc:
            logger.warning("pipeline.mark_failed_error", error=str(exc))

    async def _mark_dossier_status(self, ctx: PipelineContext, status: str) -> None:
        """Update dossier.status — dùng raw SQL để tránh cross-BC ORM import."""
        try:
            async with self._session_factory() as session:
                await session.execute(
                    _DOSSIER_STATUS_UPDATE,
                    {
                        "status": status,
                        "dossier_id": ctx.dossier_id,
                        "tenant_id": ctx.tenant_id,
                    },
                )
                await session.commit()
        except Exception as exc:
            logger.warning(
                "pipeline.mark_dossier_failed",
                dossier_id=ctx.dossier_id,
                error=str(exc),
            )

    async def _mark_dossier_has_conflicts(self, ctx: PipelineContext, has_conflicts: bool) -> None:
        """Update dossier.has_conflicts — dùng raw SQL để tránh cross-BC ORM import."""
        try:
            async with self._session_factory() as session:
                await session.execute(
                    _DOSSIER_CONFLICTS_UPDATE,
                    {
                        "has_conflicts": has_conflicts,
                        "dossier_id": ctx.dossier_id,
                        "tenant_id": ctx.tenant_id,
                    },
                )
                await session.commit()
        except Exception as exc:
            logger.warning(
                "pipeline.mark_conflicts_failed",
                dossier_id=ctx.dossier_id,
                error=str(exc),
            )

    async def _with_session(self, coro_factory: Any) -> None:
        """Helper: mở AsyncSession mới cho mỗi DB write (cross-await safe)."""
        async with self._session_factory() as session:
            try:
                await coro_factory(session)
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    def _next_task_id(self) -> int:
        """Stub — Sprint 4 sẽ thay bằng DB sequence. Hiện tại dùng ULID hash."""
        return int(hashlib.sha256(new_ulid("tsk_").encode()).hexdigest()[:8], 16) % 10_000_000

    def _compute_digest(self, snapshot: Ai1SnapshotPayload) -> str:
        """SHA-256 digest của full_text_nfc + page count — semantic gate check."""
        h = hashlib.sha256()
        h.update(snapshot.full_text_nfc.encode("utf-8"))
        h.update(str(snapshot.total_pages).encode())
        return h.hexdigest()

    def _compute_digest_for_doc(self, doc: DocumentJob) -> str:
        """Fallback digest từ sha256 + page count — dùng khi chưa có OCR result."""
        h = hashlib.sha256()
        h.update(doc.sha256.encode())
        h.update(str(doc.page_count).encode())
        return h.hexdigest()


# ──────────────────────────────────────────────────────────────────────────────
# Module-level helpers (DB writes bypassing session_factory)
# ──────────────────────────────────────────────────────────────────────────────


async def update_pipeline_run_status_via_engine(
    engine: AsyncEngine,
    *,
    tenant_id: str,
    run_id: str,
    status: str,
    error_code: str | None = None,
    error_detail: str | None = None,
) -> None:
    """Update pipeline_run status — mở session mới để tránh cross-await session reuse."""
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        try:
            await update_pipeline_run_status(
                session,
                tenant_id=tenant_id,
                run_id=run_id,
                status=status,
                error_code=error_code,
                error_detail=error_detail,
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ──────────────────────────────────────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────────────────────────────────────

_orchestrator: PipelineOrchestrator | None = None


def get_pipeline_orchestrator() -> PipelineOrchestrator:
    """Singleton — bound to AI service client + DB engine."""
    global _orchestrator  # noqa: PLW0603
    if _orchestrator is None:
        from contract_intelligence.shared.persistence import get_engine

        engine = get_engine()
        _orchestrator = PipelineOrchestrator(
            client=get_ai_service_client(),
            engine=engine,
            settings=get_settings(),
        )
    return _orchestrator


def reset_pipeline_orchestrator() -> None:
    """Test helper."""
    global _orchestrator  # noqa: PLW0603
    _orchestrator = None


__all__ = [
    "DocumentJob",
    "PipelineContext",
    "PipelineOrchestrator",
    "get_pipeline_orchestrator",
    "reset_pipeline_orchestrator",
]
