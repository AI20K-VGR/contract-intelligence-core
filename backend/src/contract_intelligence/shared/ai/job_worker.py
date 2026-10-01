"""In-process maintenance loop of the API process.

The API process never runs the pipeline: OCR/AI work is orchestrated only by
the Kafka worker (``contract_intelligence.worker``). This loop just sweeps
dossier purges that are due, on ``job_reaper_interval_seconds``.

It used to also claim ``uploaded`` jobs and run the legacy in-process
``PipelineOrchestrator``, which raced the Kafka worker for every new upload.
"""

from __future__ import annotations

import asyncio

import structlog

from contract_intelligence.config.settings import Settings, get_settings

logger = structlog.get_logger(__name__)


class MaintenanceLoop:
    """Background loop: sweep pending dossier purges."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._loop(), name="api-maintenance")
        logger.info("maintenance.started")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        await asyncio.gather(self._task, return_exceptions=True)
        self._task = None
        logger.info("maintenance.stopped")

    async def _loop(self) -> None:
        from contract_intelligence.contract.infrastructure.persistence import (
            dossier_deletion_service,
        )

        interval = self._settings.job_reaper_interval_seconds
        while True:
            try:
                await dossier_deletion_service.sweep_pending_purges()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("maintenance.purge_sweep_error")
            await asyncio.sleep(interval)


_loop: MaintenanceLoop | None = None


def start_maintenance_loop() -> MaintenanceLoop:
    global _loop  # noqa: PLW0603
    if _loop is None:
        _loop = MaintenanceLoop(get_settings())
    _loop.start()
    return _loop


async def stop_maintenance_loop() -> None:
    global _loop  # noqa: PLW0603
    if _loop is not None:
        await _loop.stop()
        _loop = None


__all__ = ["MaintenanceLoop", "start_maintenance_loop", "stop_maintenance_loop"]
