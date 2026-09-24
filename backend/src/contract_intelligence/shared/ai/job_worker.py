"""Async Postgres job worker + lease reaper (Control Plane queue).

No Redis / Celery — polls the ``job`` table, claims with
``FOR UPDATE SKIP LOCKED``, runs ``PipelineOrchestrator``, and periodically
requeues stalled leases.
"""

from __future__ import annotations

import asyncio
import socket
import uuid
from typing import Any

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from contract_intelligence.config.settings import Settings, get_settings
from contract_intelligence.shared.base import new_ulid
from contract_intelligence.shared.persistence.job_queue import (
    ClaimedJob,
    claim_next_job,
    complete_job,
    extend_lease,
    fail_job,
    reap_expired_leases,
)
from contract_intelligence.shared.persistence.session import get_engine

logger = structlog.get_logger(__name__)


def _default_worker_id() -> str:
    return f"worker_{socket.gethostname()}_{uuid.uuid4().hex[:8]}"


class JobQueueWorker:
    """Background loops: claim→process jobs + reap expired leases."""

    def __init__(
        self,
        engine: AsyncEngine,
        settings: Settings | None = None,
        *,
        worker_id: str | None = None,
    ) -> None:
        self._engine = engine
        self._settings = settings or get_settings()
        self._worker_id = worker_id or _default_worker_id()
        self._session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        self._tasks: list[asyncio.Task[None]] = []
        self._stopping = asyncio.Event()

    @property
    def worker_id(self) -> str:
        return self._worker_id

    def start(self) -> None:
        if self._tasks:
            return
        self._stopping.clear()
        self._tasks = [
            asyncio.create_task(self._worker_loop(), name="job-queue-worker"),
            asyncio.create_task(self._reaper_loop(), name="job-queue-reaper"),
        ]
        logger.info("job_queue.worker_started", worker_id=self._worker_id)

    async def stop(self) -> None:
        self._stopping.set()
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.info("job_queue.worker_stopped", worker_id=self._worker_id)

    async def _worker_loop(self) -> None:
        poll = self._settings.job_worker_poll_interval_seconds
        lease = self._settings.job_lease_seconds
        while not self._stopping.is_set():
            try:
                claimed = await self._try_claim(lease)
                if claimed is None:
                    await asyncio.sleep(poll)
                    continue
                await self._process_claimed(claimed, lease_seconds=lease)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("job_queue.worker_loop_error")
                await asyncio.sleep(poll)

    async def _reaper_loop(self) -> None:
        interval = self._settings.job_reaper_interval_seconds
        while not self._stopping.is_set():
            try:
                async with self._session_factory() as session:
                    count = await reap_expired_leases(session)
                    await session.commit()
                    if count:
                        logger.info("job_queue.reaper_ok", count=count)
                from contract_intelligence.contract.application.dossier_deletion import (
                    sweep_pending_purges,
                )

                await sweep_pending_purges()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("job_queue.reaper_error")
            await asyncio.sleep(interval)

    async def _try_claim(self, lease_seconds: int) -> ClaimedJob | None:
        async with self._session_factory() as session:
            claimed = await claim_next_job(
                session, worker_id=self._worker_id, lease_seconds=lease_seconds
            )
            await session.commit()
            return claimed

    async def _process_claimed(self, claimed: ClaimedJob, *, lease_seconds: int) -> None:
        from contract_intelligence.shared.ai.pipeline_orchestrator import (
            PipelineContext,
            get_pipeline_orchestrator,
        )

        heartbeat = asyncio.create_task(
            self._heartbeat_loop(claimed.id, lease_seconds),
            name=f"job-heartbeat-{claimed.id}",
        )
        try:
            run_id = claimed.current_run_id or new_ulid("run_")
            if claimed.current_run_id is None:
                await self._ensure_pipeline_run(claimed, run_id)

            documents = await self._load_documents(claimed.tenant_id, claimed.dossier_id)
            if not documents:
                async with self._session_factory() as session:
                    await fail_job(
                        session,
                        job_id=claimed.id,
                        worker_id=self._worker_id,
                        error_code="NO_DOCUMENTS",
                        error_detail="Job has no documents to process",
                    )
                    await session.commit()
                return

            ctx = PipelineContext(
                run_id=run_id,
                dossier_id=claimed.dossier_id,
                tenant_id=claimed.tenant_id,
                documents=documents,
            )
            orchestrator = get_pipeline_orchestrator()
            await orchestrator.run(ctx)

            async with self._session_factory() as session:
                await complete_job(
                    session,
                    job_id=claimed.id,
                    worker_id=self._worker_id,
                    status="pending_review",
                )
                await session.commit()
            logger.info(
                "job_queue.completed",
                job_id=claimed.id,
                run_id=run_id,
                dossier_id=claimed.dossier_id,
            )
        except Exception as exc:
            logger.exception("job_queue.process_failed", job_id=claimed.id)
            try:
                async with self._session_factory() as session:
                    await fail_job(
                        session,
                        job_id=claimed.id,
                        worker_id=self._worker_id,
                        error_code="PIPELINE_FAILED",
                        error_detail=str(exc)[:2000],
                    )
                    await session.commit()
            except Exception:
                logger.exception("job_queue.fail_job_error", job_id=claimed.id)
        finally:
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)

    async def _heartbeat_loop(self, job_id: str, lease_seconds: int) -> None:
        # Renew at half the lease TTL.
        interval = max(5.0, lease_seconds / 2)
        while True:
            await asyncio.sleep(interval)
            try:
                async with self._session_factory() as session:
                    ok = await extend_lease(
                        session,
                        job_id=job_id,
                        worker_id=self._worker_id,
                        lease_seconds=lease_seconds,
                    )
                    await session.commit()
                    if not ok:
                        logger.warning("job_queue.heartbeat_lost", job_id=job_id)
                        return
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("job_queue.heartbeat_error", job_id=job_id)

    async def _ensure_pipeline_run(self, claimed: ClaimedJob, run_id: str) -> None:
        async with self._session_factory() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO pipeline_run (
                        id, tenant_id, job_id, dossier_id, status, pipeline_version
                    ) VALUES (
                        :id, :tenant_id, :job_id, :dossier_id, 'queued', 'v1.0.0'
                    )
                    """
                ),
                {
                    "id": run_id,
                    "tenant_id": claimed.tenant_id,
                    "job_id": claimed.id,
                    "dossier_id": claimed.dossier_id,
                },
            )
            await session.execute(
                text(
                    """
                    UPDATE job SET current_run_id = :run_id, updated_at = CURRENT_TIMESTAMP
                    WHERE id = :job_id
                    """
                ),
                {"run_id": run_id, "job_id": claimed.id},
            )
            await session.commit()

    async def _load_documents(self, tenant_id: str, dossier_id: str) -> list[Any]:
        from contract_intelligence.contract.infrastructure.persistence.orm import DocumentORM
        from contract_intelligence.shared.ai.pipeline_orchestrator import DocumentJob

        async with self._session_factory() as session:
            result = await session.execute(
                select(DocumentORM)
                .where(
                    DocumentORM.tenant_id == tenant_id,
                    DocumentORM.dossier_id == dossier_id,
                )
                .order_by(DocumentORM.order_index)
            )
            docs = result.scalars().all()
            return [
                DocumentJob(
                    document_id=d.id,
                    sha256=d.sha256 or "",
                    blob_uri=d.blob_uri or "",
                    filename=d.filename or "",
                    role=d.role,
                    page_count=int(d.page_count or 0),
                )
                for d in docs
            ]


_worker: JobQueueWorker | None = None


def get_job_queue_worker() -> JobQueueWorker:
    global _worker  # noqa: PLW0603
    if _worker is None:
        _worker = JobQueueWorker(get_engine(), get_settings())
    return _worker


def start_job_queue_worker(engine: AsyncEngine | None = None) -> JobQueueWorker:
    """Bind engine (if provided) and start worker+reaper loops."""
    global _worker  # noqa: PLW0603
    settings = get_settings()
    if not settings.job_queue_enabled:
        logger.info("job_queue.disabled")
        if _worker is None:
            _worker = JobQueueWorker(engine or get_engine(), settings)
        return _worker
    if _worker is None:
        _worker = JobQueueWorker(engine or get_engine(), settings)
    _worker.start()
    return _worker


async def stop_job_queue_worker() -> None:
    global _worker  # noqa: PLW0603
    if _worker is not None:
        await _worker.stop()
        _worker = None


def reset_job_queue_worker() -> None:
    """Test helper — drop singleton without awaiting stop."""
    global _worker  # noqa: PLW0603
    _worker = None


__all__ = [
    "JobQueueWorker",
    "get_job_queue_worker",
    "reset_job_queue_worker",
    "start_job_queue_worker",
    "stop_job_queue_worker",
]
