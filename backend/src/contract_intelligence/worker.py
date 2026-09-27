"""Kafka orchestrator — dossier.uploaded → AI1 OCR commands; consume OCR results.

Run as a standalone process::

    uv run python -m contract_intelligence.worker

See ``docs/DOC-05d-kafka-ai1-ocr-contract.md``.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from typing import Any

import structlog
from aiokafka import AIOKafkaConsumer
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from contract_intelligence.config.settings import get_settings
from contract_intelligence.contract.domain.entities.job import JobStatus
from contract_intelligence.contract.infrastructure.persistence.orm import (
    DocumentORM,
    DossierORM,
    JobORM,
    ManifestItemORM,
    ManifestORM,
    ManifestRelationORM,
)
from contract_intelligence.extraction.infrastructure.persistence.orm import (
    PipelineRunORM,
    PipelineStepORM,
)
from contract_intelligence.infrastructure import messaging, storage
from contract_intelligence.infrastructure.ai_adapters import (
    AiAdapterError,
    poll_ai2_processing,
    submit_ai2_processing,
)
from contract_intelligence.shared.ai.ai1_adapter import adapt_ai1_snapshot_result
from contract_intelligence.shared.ai.canonical_processing import (
    build_processing_request,
    strip_internal_fields,
)
from contract_intelligence.shared.ai.persistence import (
    persist_ai1_snapshot,
    persist_ai2_processing_result,
    update_pipeline_run_status,
    update_pipeline_step,
)
from contract_intelligence.shared.audit import add_audit_event
from contract_intelligence.shared.base import new_ulid

logger = structlog.get_logger(__name__)

SCHEMA_VERSION = "ci.kafka.v1"
EVENT_OCR_COMMAND = "ai1.ocr.command"
EVENT_OCR_COMPLETED = "ai1.ocr.completed"
EVENT_OCR_FAILED = "ai1.ocr.failed"
# Idempotency for result events (event_id / job_id).
_seen_result_ids: set[str] = set()
_snapshot_cache: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
_submitted_ai2_runs: set[str] = set()


def _utcnow_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _task_id_from(document_id: str) -> int:
    return int(hashlib.sha256(document_id.encode()).hexdigest()[:8], 16) % 10_000_000


def _ai2_query_snapshot_digest(request: dict[str, Any]) -> str:
    """Match AI2's canonical request digest used by its query guard."""

    members = request.get("dossier_members") or []
    manifest = {
        "schema_version": "ai1.dossier-manifest.v1",
        "manifest_id": f"manifest:{request.get('request_id')}",
        "dossier_id": request.get("dossier_id"),
        "documents": [
            {
                "document_id": item.get("document_id"),
                "snapshot_id": item.get("snapshot_id"),
                "role": item.get("role"),
                "source_digest": item.get("source_digest"),
            }
            for item in members
            if isinstance(item, dict)
        ],
    }
    compatibility_payload = {
        "schema_version": "ai2.idp.request.v1",
        "task_id": request.get("task_id"),
        "attempt_id": f"attempt:{request.get('attempt')}",
        "manifest": manifest,
        "snapshots": request.get("snapshots") or [],
    }
    canonical = json.dumps(
        compatibility_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _snapshot_digest(snapshot: dict[str, Any]) -> str:
    canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _durable_snapshots_from_run(run: PipelineRunORM | None) -> dict[str, dict[str, Any]]:
    """Decode AI1 snapshots stored on the durable pipeline run projection."""

    if run is None or not run.config_snapshot:
        return {}
    try:
        payload = (
            json.loads(run.config_snapshot)
            if isinstance(run.config_snapshot, str)
            else run.config_snapshot
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    raw_snapshots = payload.get("ai1_snapshots") if isinstance(payload, dict) else None
    if not isinstance(raw_snapshots, dict):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for document_id, snapshot in raw_snapshots.items():
        if not isinstance(snapshot, dict):
            continue
        resolved_id = str(snapshot.get("document_id") or document_id).strip()
        if resolved_id and snapshot.get("schema_version") == "ai1.snapshot.v1":
            result[resolved_id] = snapshot
    return result


def _merge_snapshot_cache(
    target: dict[str, dict[str, Any]], source: dict[str, dict[str, Any]]
) -> None:
    """Merge only scoped canonical snapshots into a per-run working set."""

    for document_id, snapshot in source.items():
        if (
            isinstance(snapshot, dict)
            and snapshot.get("schema_version") == "ai1.snapshot.v1"
            and str(snapshot.get("document_id") or document_id).strip()
        ):
            target[str(snapshot.get("document_id") or document_id)] = snapshot


async def _record_ai1_document(
    session: AsyncSession,
    *,
    run_id: str,
    document_id: str,
    snapshot: dict[str, Any] | None,
) -> set[str]:
    """Store the canonical snapshot (if any) on the run; return every document extracted in it."""
    run = (
        await session.execute(select(PipelineRunORM).where(PipelineRunORM.id == run_id))
    ).scalar_one_or_none()
    if run is None:
        return {document_id}
    try:
        payload = (
            json.loads(run.config_snapshot)
            if isinstance(run.config_snapshot, str) and run.config_snapshot
            else {}
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    if snapshot is not None:
        payload["ai1_snapshots"] = _durable_snapshots_from_run(run)
        payload["ai1_snapshots"][document_id] = snapshot
        payload["ai1_snapshot_digests"] = {
            key: _snapshot_digest(value) for key, value in payload["ai1_snapshots"].items()
        }
    extracted = {str(value) for value in payload.get("ai1_extracted_documents") or [] if value}
    extracted.add(document_id)
    payload["ai1_extracted_documents"] = sorted(extracted)
    run.config_snapshot = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    await session.flush()
    return extracted


# Pipeline results may only move a job forward along this chain. FAILED and the
# human-owned states (reviewed/approved/cancelled) are final for the worker; a
# fresh run (upload/OCR restart) is the only way out of FAILED.
_FORWARD_RANK = {
    JobStatus.UPLOADED.value: 0,
    JobStatus.PROCESSING.value: 1,
    JobStatus.EXTRACTED.value: 2,
    JobStatus.PENDING_REVIEW.value: 3,
}
_ACTIVE_RUN_STATUSES = frozenset({"queued", "running"})


def _worker_transition_allowed(current: str | None, target: str) -> bool:
    current_rank = _FORWARD_RANK.get(str(current or ""))
    if current_rank is None:
        return False
    if target == JobStatus.FAILED.value:
        return current_rank < _FORWARD_RANK[JobStatus.PENDING_REVIEW.value]
    target_rank = _FORWARD_RANK.get(target)
    return target_rank is not None and target_rank >= current_rank


async def _job_for_run(session: AsyncSession, run_id: str) -> JobORM | None:
    result = await session.execute(select(JobORM).where(JobORM.current_run_id == run_id).limit(1))
    return result.scalar_one_or_none()


def _forget_run(run_id: str | None) -> None:
    if not run_id:
        return
    _submitted_ai2_runs.discard(run_id)
    for key in [key for key in _snapshot_cache if key[1] == run_id]:
        _snapshot_cache.pop(key, None)


async def _resolve_result_job(
    session: AsyncSession,
    message: dict[str, Any],
    *,
    source: str,
    dossier_id: str,
    run_id: str,
    tenant_id: str,
) -> JobORM | None:
    """Bind a result event to the job currently running ``run_id``.

    The envelope's tenant/dossier are claims from another service; the job row
    is the authority. Events for superseded runs, unknown runs or another
    tenant's job are dropped without touching state.
    """
    event_id = str(message.get("event_id") or "")
    if message.get("schema_version") != SCHEMA_VERSION:
        logger.error(
            "worker.result.schema_rejected",
            source=source,
            event_id=event_id,
            schema_version=message.get("schema_version"),
        )
        return None
    if not run_id:
        logger.error("worker.result.missing_run_id", source=source, event_id=event_id)
        return None
    job = await _job_for_run(session, run_id)
    if job is None:
        logger.warning("worker.result.stale_run", source=source, event_id=event_id, run_id=run_id)
        return None
    mismatch = {
        field: claimed
        for field, claimed, actual in (
            ("tenant_id", tenant_id, job.tenant_id),
            ("dossier_id", dossier_id, job.dossier_id),
        )
        if claimed and claimed != actual
    }
    if mismatch:
        logger.error(
            "worker.result.scope_mismatch",
            source=source,
            event_id=event_id,
            run_id=run_id,
            job_id=job.id,
            claimed=mismatch,
        )
        add_audit_event(
            session,
            tenant_id=job.tenant_id,
            action=f"{source}.result_rejected",
            entity_type="job",
            entity_id=job.id,
            dossier_id=job.dossier_id,
            run_id=run_id,
            detail={"event_id": event_id, "reason": "SCOPE_MISMATCH", "claimed": mismatch},
        )
        await session.commit()
        return None
    return job


async def _mark_processing(
    session: AsyncSession, dossier_id: str, *, restart: bool = False
) -> str | None:
    """Start (or resume) the OCR run of the dossier's latest job. Returns its run id.

    A redelivered ``dossier.uploaded`` resumes the active run. ``restart`` (OCR
    re-run) always opens a new run and supersedes the old one, so late results
    of the old run can no longer change the job.
    """
    now = datetime.now(tz=UTC)
    result = await session.execute(
        select(JobORM)
        .where(JobORM.dossier_id == dossier_id)
        .order_by(JobORM.created_at.desc())
        .limit(1)
    )
    job = result.scalar_one_or_none()
    if job is None:
        logger.warning("worker.job_missing", dossier_id=dossier_id)
        return None

    previous_status = job.status
    if restart:
        if previous_status in (JobStatus.APPROVED.value, JobStatus.CANCELLED.value):
            logger.warning(
                "worker.ocr_restart.rejected", dossier_id=dossier_id, status=previous_status
            )
            return None
    elif previous_status not in (JobStatus.UPLOADED.value, JobStatus.PROCESSING.value):
        logger.info(
            "worker.dossier_uploaded.ignored", dossier_id=dossier_id, status=previous_status
        )
        return None

    pipeline_run: PipelineRunORM | None = None
    if job.current_run_id:
        pipeline_run = (
            await session.execute(
                select(PipelineRunORM).where(PipelineRunORM.id == job.current_run_id)
            )
        ).scalar_one_or_none()
    superseded_run_id: str | None = None
    if (
        not restart
        and job.current_run_id
        and (pipeline_run is None or pipeline_run.status in _ACTIVE_RUN_STATUSES)
    ):
        run_id = job.current_run_id
    else:
        superseded_run_id = job.current_run_id
        if pipeline_run is not None and pipeline_run.status in _ACTIVE_RUN_STATUSES:
            pipeline_run.status = "cancelled"
            pipeline_run.error_code = "SUPERSEDED"
            pipeline_run.finished_at = now
        _forget_run(superseded_run_id)
        run_id = new_ulid("run_")
        pipeline_run = None

    if pipeline_run is None:
        pipeline_run = PipelineRunORM(
            id=run_id,
            tenant_id=job.tenant_id,
            job_id=job.id,
            dossier_id=dossier_id,
            status="running",
            pipeline_version="v1.0.0",
            git_sha="",
            trace_id=run_id,
        )
        session.add(pipeline_run)
        await session.flush()
        for step_code in (
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
        ):
            session.add(
                PipelineStepORM(
                    tenant_id=job.tenant_id,
                    run_id=run_id,
                    step=step_code,
                    status=(
                        "succeeded"
                        if step_code in {"S0", "S1"}
                        else "running"
                        if step_code == "S2"
                        else "queued"
                    ),
                )
            )
        await session.flush()
    elif pipeline_run.status == "queued":
        pipeline_run.status = "running"
    await session.execute(
        update(DossierORM)
        .where(DossierORM.id == dossier_id)
        .values(status=JobStatus.PROCESSING.value, updated_at=now)
    )
    job.status = JobStatus.PROCESSING.value
    job.current_run_id = run_id
    job.error_code = None
    job.error_detail = None
    job.updated_at = now
    detail: dict[str, Any] = {"trigger": "ocr.restart" if restart else "dossier.uploaded"}
    if superseded_run_id:
        detail["superseded_run_id"] = superseded_run_id
    add_audit_event(
        session,
        tenant_id=job.tenant_id,
        action="job.status_changed",
        entity_type="job",
        entity_id=job.id,
        dossier_id=dossier_id,
        run_id=run_id,
        from_state=previous_status,
        to_state=JobStatus.PROCESSING.value,
        detail=detail,
    )
    await session.flush()
    return run_id


async def _mark_status(
    session: AsyncSession,
    *,
    status_value: str,
    dossier_id: str | None,
    run_id: str | None,
    error_code: str | None = None,
    error_detail: str | None = None,
    has_conflicts: bool | None = None,
    audit_action: str = "job.status_changed",
    audit_detail: dict[str, Any] | None = None,
) -> bool:
    """Apply a pipeline status to the job running ``run_id``; False when refused.

    With a ``run_id`` only the job whose current run it is may change, so a
    superseded run cannot touch the job. Transitions are forward-only.
    """
    now = datetime.now(tz=UTC)
    job: JobORM | None = None
    if run_id:
        job = await _job_for_run(session, run_id)
    elif dossier_id:
        result = await session.execute(
            select(JobORM)
            .where(JobORM.dossier_id == dossier_id)
            .order_by(JobORM.created_at.desc())
            .limit(1)
        )
        job = result.scalar_one_or_none()
    if job is None:
        logger.warning(
            "worker.status_job_missing",
            dossier_id=dossier_id,
            run_id=run_id,
            status=status_value,
        )
        return False
    previous_status = job.status
    if not _worker_transition_allowed(previous_status, status_value):
        logger.warning(
            "worker.status_transition_refused",
            job_id=job.id,
            run_id=run_id,
            from_state=previous_status,
            to_state=status_value,
            audit_action=audit_action,
        )
        return False
    job.status = status_value
    job.updated_at = now
    if error_code is not None:
        job.error_code = error_code
    if error_detail is not None:
        job.error_detail = error_detail
    resolved = job.dossier_id
    dossier_values: dict[str, Any] = {"status": status_value, "updated_at": now}
    if has_conflicts is not None:
        dossier_values["has_conflicts"] = has_conflicts
    await session.execute(
        update(DossierORM).where(DossierORM.id == resolved).values(**dossier_values)
    )
    detail = dict(audit_detail or {})
    if error_code is not None:
        detail["error_code"] = error_code
    if has_conflicts is not None:
        detail["has_conflicts"] = has_conflicts
    add_audit_event(
        session,
        tenant_id=job.tenant_id,
        action=audit_action,
        entity_type="job",
        entity_id=job.id,
        dossier_id=resolved,
        run_id=run_id or job.current_run_id,
        from_state=previous_status,
        to_state=status_value,
        detail=detail or None,
    )
    await session.flush()
    return True


async def _fail_ai1_run(
    session: AsyncSession,
    *,
    tenant_id: str,
    run_id: str,
    code: str,
    detail: str,
    audit_action: str,
    audit_detail: dict[str, Any],
) -> None:
    """Mark the job, the run and the OCR step FAILED (with audit) and commit.

    Nothing is written when the job may no longer fail (e.g. already in review).
    """
    if not await _mark_status(
        session,
        status_value=JobStatus.FAILED.value,
        dossier_id=None,
        run_id=run_id,
        error_code=code,
        error_detail=detail,
        audit_action=audit_action,
        audit_detail=audit_detail,
    ):
        return
    await update_pipeline_step(
        session,
        tenant_id=tenant_id,
        run_id=run_id,
        step="S2",
        status="failed",
        metrics={"service": "ai1", "error": detail[:500], **audit_detail},
    )
    await update_pipeline_run_status(
        session,
        tenant_id=tenant_id,
        run_id=run_id,
        status="failed",
        error_code=code,
        error_detail=detail,
    )
    await session.commit()


async def _fail_ai2_run(
    session: AsyncSession,
    *,
    tenant_id: str,
    run_id: str,
    code: str,
    detail: str,
    audit_detail: dict[str, Any],
) -> None:
    """Mark the job, the run and the AI2 step FAILED (with audit) and commit."""
    if not await _mark_status(
        session,
        status_value=JobStatus.FAILED.value,
        dossier_id=None,
        run_id=run_id,
        error_code=code,
        error_detail=detail,
        audit_action="ai2.processing_failed",
        audit_detail=audit_detail,
    ):
        return
    await update_pipeline_step(
        session,
        tenant_id=tenant_id,
        run_id=run_id,
        step="S4",
        status="failed",
        metrics={"service": "ai2", "error": detail[:500], **audit_detail},
    )
    await update_pipeline_run_status(
        session,
        tenant_id=tenant_id,
        run_id=run_id,
        status="failed",
        error_code=code,
        error_detail=detail,
    )
    await session.commit()


async def _load_documents(session: AsyncSession, dossier_id: str) -> list[DocumentORM]:
    result = await session.execute(
        select(DocumentORM)
        .where(
            DocumentORM.dossier_id == dossier_id,
        )
        .order_by(DocumentORM.order_index.asc())
    )
    return list(result.scalars().all())


async def _persist_ai2_snapshot_identity(
    session: AsyncSession,
    *,
    dossier_id: str,
    snapshot_digest: str,
    snapshot_id: str = "",
) -> None:
    """Persist the AI2 snapshot identity used to bind later queries.

    ``dossier.checksum`` is the approval checksum and is intentionally empty
    until approval. It must not be reused as the AI2 canonical snapshot digest.
    """

    digest = str(snapshot_digest or "").strip()
    if not digest:
        return

    result = await session.execute(select(DossierORM).where(DossierORM.id == dossier_id))
    dossier = result.scalar_one_or_none()
    if dossier is None:
        return
    metadata = dict(dossier.metadata_json or {})
    metadata["ai2_snapshot_digest"] = digest
    snapshot_id = str(snapshot_id or "").strip()
    if snapshot_id:
        metadata["ai2_snapshot_id"] = snapshot_id
    dossier.metadata_json = metadata
    await session.flush()


async def _build_ocr_command_payload(
    *,
    document: DocumentORM,
    dossier: DossierORM,
    run_id: str,
) -> dict[str, Any]:
    settings = get_settings()
    page_count = int(document.page_count or 0)
    pages = list(range(1, page_count + 1)) if page_count > 0 else [1]

    blob_uri = document.blob_uri
    if not blob_uri:
        raise ValueError(f"Document {document.id} has no blob URI")
    get_url = await storage.generate_presigned_get_url(blob_uri)
    put_urls: dict[str, str] = {}
    for page_no in pages:
        put_key = f"{document.id}/page-{page_no:03d}.png"
        put_urls[str(page_no)] = await storage.generate_presigned_put_url(key=put_key)

    task_id = _task_id_from(document.id)
    engine = (settings.ai1_ocr_engine or "mistral").strip().lower()
    return {
        "schema_version": SCHEMA_VERSION,
        "event_id": new_ulid("evt_"),
        "event_type": EVENT_OCR_COMMAND,
        "occurred_at": _utcnow_iso(),
        "trace_id": run_id,
        "tenant_id": document.tenant_id or dossier.tenant_id,
        "correlation": {
            "dossier_id": dossier.id,
            "document_id": document.id,
            "task_id": task_id,
            "attempt_id": 1,
            "run_id": run_id,
        },
        "payload": {
            "task_id": task_id,
            "attempt_id": 1,
            "tenant_id": document.tenant_id or dossier.tenant_id,
            "document_id": document.id,
            "source_blob_get_url": get_url,
            "source_sha256": document.sha256,
            "pages_to_process": pages,
            "render_target": {
                "dpi": 150,
                "format": "PNG",
                "presigned_put_urls": put_urls,
            },
            "options": {
                "engine": engine,
                "dpi": 150,
                "language": document.lang_detected or "vi",
                "document_role": document.role.lower(),
                "filename": document.filename,
            },
        },
    }


async def handle_dossier_uploaded(session: AsyncSession, event: dict[str, Any]) -> None:
    """Process ``dossier.uploaded``: mark PROCESSING and publish AI1 OCR command."""
    settings = get_settings()
    dossier_id = str(event.get("dossier_id") or "")
    if not dossier_id:
        logger.error("worker.dossier_uploaded.missing_dossier_id", event=event)
        return

    run_id = await _mark_processing(session, dossier_id, restart=bool(event.get("restart")))
    await session.commit()
    if run_id is None:
        return

    documents = await _load_documents(session, dossier_id)
    if not documents:
        logger.error("worker.dossier_uploaded.no_documents", dossier_id=dossier_id)
        return

    dossier = await session.get(DossierORM, dossier_id)
    if dossier is None:
        logger.error("worker.dossier_uploaded.dossier_missing", dossier_id=dossier_id)
        return

    for document in documents:
        envelope = await _build_ocr_command_payload(
            document=document,
            dossier=dossier,
            run_id=run_id,
        )
        await messaging.publish_event(
            settings.kafka_ai1_ocr_commands_topic,
            envelope,
            key=document.id,
        )
        logger.info(
            "worker.dossier_uploaded.ocr_command_published",
            dossier_id=dossier_id,
            document_id=document.id,
            run_id=envelope["correlation"]["run_id"],
            event_id=envelope["event_id"],
        )


async def _run_ai2_if_ready(
    session: AsyncSession,
    *,
    dossier_id: str,
    tenant_id: str,
    run_id: str,
) -> None:
    """Submit/poll AI2 only after manifest confirmation and complete AI1 input."""

    if run_id in _submitted_ai2_runs:
        return
    manifest_result = await session.execute(
        select(ManifestORM).where(ManifestORM.dossier_id == dossier_id)
    )
    manifest = manifest_result.scalar_one_or_none()
    if manifest is None or manifest.status != "confirmed":
        logger.info("worker.ai2.waiting_for_manifest", dossier_id=dossier_id, run_id=run_id)
        return

    durable_run_result = await session.execute(
        select(PipelineRunORM).where(PipelineRunORM.id == run_id)
    )
    durable_run = durable_run_result.scalar_one_or_none()
    if durable_run is not None and durable_run.ai2_result_digest:
        _submitted_ai2_runs.add(run_id)
        logger.info("worker.ai2.already_persisted", dossier_id=dossier_id, run_id=run_id)
        return

    member_result = await session.execute(
        select(ManifestItemORM).where(ManifestItemORM.manifest_id == manifest.id)
    )
    relation_result = await session.execute(
        select(ManifestRelationORM).where(ManifestRelationORM.manifest_id == manifest.id)
    )
    document_result = await session.execute(
        select(DocumentORM).where(DocumentORM.dossier_id == dossier_id)
    )
    snapshots: dict[str, dict[str, Any]] = _durable_snapshots_from_run(durable_run)
    _merge_snapshot_cache(snapshots, _snapshot_cache.get((dossier_id, run_id), {}))
    request = build_processing_request(
        dossier_id=dossier_id,
        run_id=run_id,
        snapshots=snapshots,
        documents=list(document_result.scalars().all()),
        members=list(member_result.scalars().all()),
        relations=list(relation_result.scalars().all()),
    )
    if request is None:
        logger.info(
            "worker.ai2.waiting_for_snapshots",
            dossier_id=dossier_id,
            run_id=run_id,
            snapshot_count=len(snapshots),
        )
        return

    query_snapshot_digest = _ai2_query_snapshot_digest(request)

    await update_pipeline_run_status(
        session,
        tenant_id=tenant_id,
        run_id=run_id,
        status="running",
    )
    await update_pipeline_step(
        session,
        tenant_id=tenant_id,
        run_id=run_id,
        step="S4",
        status="running",
        metrics={"service": "ai2", "contract": "be.ai2.processing.request.v1"},
    )
    await session.commit()

    try:
        submission = await submit_ai2_processing(
            strip_internal_fields(request),
            tenant_id=tenant_id,
            dossier_id=dossier_id,
        )
        ai2_job_id = str(submission.get("job_id") or "")
        if not ai2_job_id:
            raise AiAdapterError("AI2 submission did not return job_id")
        report = await poll_ai2_processing(
            ai2_job_id,
            tenant_id=tenant_id,
            dossier_id=dossier_id,
        )
        if str(report.get("status", "")).upper() != "SUCCEEDED":
            errors = report.get("errors") or [
                {"code": "AI2_FAILED", "message": "AI2 returned FAILED"}
            ]
            raise AiAdapterError(
                str(errors[0].get("message") if isinstance(errors[0], dict) else errors[0])
            )

        await _finalize_ai2_success(
            session,
            tenant_id=tenant_id,
            dossier_id=dossier_id,
            run_id=run_id,
            report=report,
            ai2_job_id=ai2_job_id,
            snapshot_digest=query_snapshot_digest,
            snapshot_id=str((request.get("snapshots") or [{}])[0].get("snapshot_id") or ""),
            source="http_poll",
        )
    except Exception as exc:
        _submitted_ai2_runs.discard(run_id)
        await session.rollback()
        await _fail_ai2_run(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            code="AI2_PROCESSING_FAILED",
            detail=str(exc)[:1000],
            audit_detail={"source": "http_poll"},
        )
        logger.exception("worker.ai2.failed", dossier_id=dossier_id, run_id=run_id)


async def _finalize_ai2_success(
    session: AsyncSession,
    *,
    tenant_id: str,
    dossier_id: str,
    run_id: str,
    report: dict[str, Any],
    ai2_job_id: str,
    snapshot_digest: str = "",
    snapshot_id: str = "",
    source: str,
) -> dict[str, Any] | None:
    """Persist a SUCCEEDED AI2 result and hand the dossier to HITL review.

    Returns None (nothing written) when ``run_id`` is no longer the job's
    current run or the job already left the pipeline (FAILED, reviewed, ...).
    """
    job = await _job_for_run(session, run_id)
    if (
        job is None
        or job.tenant_id != tenant_id
        or job.dossier_id != dossier_id
        or not _worker_transition_allowed(job.status, JobStatus.PENDING_REVIEW.value)
    ):
        logger.warning(
            "worker.ai2.result_refused",
            dossier_id=dossier_id,
            run_id=run_id,
            job_status=job.status if job else None,
            source=source,
        )
        return None
    counts = await persist_ai2_processing_result(
        session,
        tenant_id=tenant_id,
        dossier_id=dossier_id,
        result=report,
        run_id=run_id,
    )
    await _persist_ai2_snapshot_identity(
        session,
        dossier_id=dossier_id,
        snapshot_digest=snapshot_digest,
        snapshot_id=snapshot_id,
    )
    for step in ("S4", "S5", "S6", "S7", "S9", "S10"):
        await update_pipeline_step(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            step=step,
            status="succeeded",
            metrics={
                "service": "ai2",
                "job_id": ai2_job_id,
                "facts": counts["facts"],
                "findings": counts["findings"],
                "review_items": counts.get("review_items", 0),
                "review_state": report.get("review_state"),
            },
        )
    await update_pipeline_run_status(
        session,
        tenant_id=tenant_id,
        run_id=run_id,
        status="succeeded",
    )
    await _mark_status(
        session,
        status_value=JobStatus.PENDING_REVIEW.value,
        dossier_id=dossier_id,
        run_id=run_id,
        has_conflicts=int(counts["findings"]) > 0,
        audit_action="ai2.result_persisted",
        audit_detail={
            "source": source,
            "ai2_job_id": ai2_job_id,
            "facts": counts["facts"],
            "findings": counts["findings"],
            "review_items": counts.get("review_items", 0),
            "review_state": counts.get("review_state"),
            "index_contribution_state": counts.get("index_contribution_state"),
            "idempotent_replay": counts.get("idempotent_replay", False),
        },
    )
    await session.commit()
    _submitted_ai2_runs.add(run_id)
    logger.info(
        "worker.ai2.completed",
        dossier_id=dossier_id,
        run_id=run_id,
        job_id=ai2_job_id,
        source=source,
        facts=counts["facts"],
        findings=counts["findings"],
    )
    return counts


async def handle_ai1_result(session: AsyncSession, message: dict[str, Any]) -> None:
    """Persist AI1 OCR result and update job/dossier status."""
    event_id = str(message.get("event_id") or "")
    raw_payload = message.get("payload")
    payload: dict[str, Any] = raw_payload if isinstance(raw_payload, dict) else {}
    job_id = str(payload.get("job_id") or "")
    dedupe_key = event_id or job_id
    if dedupe_key and dedupe_key in _seen_result_ids:
        logger.info("worker.ai1_result.duplicate", event_id=event_id, job_id=job_id)
        return

    raw_correlation = message.get("correlation")
    correlation: dict[str, Any] = raw_correlation if isinstance(raw_correlation, dict) else {}
    claimed_document_id = str(correlation.get("document_id") or "")
    event_type = message.get("event_type")

    job = await _resolve_result_job(
        session,
        message,
        source="ai1",
        dossier_id=str(correlation.get("dossier_id") or ""),
        run_id=str(correlation.get("run_id") or ""),
        tenant_id=str(message.get("tenant_id") or correlation.get("tenant_id") or ""),
    )
    if job is None:
        if dedupe_key:
            _seen_result_ids.add(dedupe_key)
        return
    # Captured as plain values: a rollback below expires the ORM instance.
    tenant_id = job.tenant_id
    dossier_id = job.dossier_id
    run_id = str(job.current_run_id)
    job_status = job.status
    base_audit = {"event_id": event_id, "ai1_job_id": job_id, "document_id": claimed_document_id}

    if event_type == EVENT_OCR_FAILED or str(payload.get("status")) == "failed":
        raw_error = payload.get("error")
        error: dict[str, Any] = raw_error if isinstance(raw_error, dict) else {}
        await _fail_ai1_run(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            code=str(error.get("code") or "AI1_OCR_FAILED"),
            detail=str(error.get("message") or "OCR failed"),
            audit_action="ai1.ocr_failed",
            audit_detail=base_audit,
        )
        if dedupe_key:
            _seen_result_ids.add(dedupe_key)
        logger.warning(
            "worker.ai1_result.failed",
            dossier_id=dossier_id,
            run_id=run_id,
            error=error,
        )
        return

    if event_type not in (EVENT_OCR_COMPLETED, None) and str(payload.get("status")) != "completed":
        logger.debug("worker.ai1_result.ignored", event_type=event_type)
        return

    if not _worker_transition_allowed(job_status, JobStatus.EXTRACTED.value):
        logger.info(
            "worker.ai1_result.job_not_extracting",
            event_id=event_id,
            run_id=run_id,
            job_status=job_status,
        )
        if dedupe_key:
            _seen_result_ids.add(dedupe_key)
        return

    documents = await _load_documents(session, dossier_id)
    dossier_document_ids = {str(document.id) for document in documents}

    result = payload.get("result")
    rejection: tuple[str, str] | None = None
    snapshot: Any = None
    canonical_snapshot: dict[str, Any] | None = None
    document_id = ""
    if not isinstance(result, dict):
        rejection = ("AI1_RESULT_MISSING", "OCR completed event carries no result")
    else:
        try:
            snapshot = adapt_ai1_snapshot_result(result)
        except (ValueError, KeyError, TypeError) as exc:
            rejection = ("AI1_SNAPSHOT_INVALID", str(exc)[:1000] or type(exc).__name__)
        else:
            raw_canonical = result.get("snapshot")
            canonical_snapshot = raw_canonical if isinstance(raw_canonical, dict) else None
            document_id = str(
                (canonical_snapshot or {}).get("document_id")
                or getattr(snapshot, "document_id", None)
                or claimed_document_id
            )
            if document_id not in dossier_document_ids or (
                claimed_document_id and claimed_document_id != document_id
            ):
                rejection = (
                    "AI1_SNAPSHOT_INVALID",
                    f"Snapshot document {document_id!r} does not belong to this dossier/command",
                )
    if rejection is not None:
        code, detail = rejection
        await _fail_ai1_run(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            code=code,
            detail=detail,
            audit_action="ai1.snapshot_rejected",
            audit_detail=base_audit,
        )
        if dedupe_key:
            _seen_result_ids.add(dedupe_key)
        logger.error("worker.ai1_result.rejected", event_id=event_id, run_id=run_id, code=code)
        return

    try:
        if canonical_snapshot is not None:
            _snapshot_cache.setdefault((dossier_id, run_id), {})[document_id] = canonical_snapshot
        # A new OCR result is authoritative for a retry.  Older databases
        # may already contain immutable evidence rows for this document. In
        # that case the DB append-only trigger rejects the legacy replacement
        # delete, but the canonical snapshot is still available in the
        # in-memory handoff cache and must continue to AI2.
        try:
            await persist_ai1_snapshot(
                session,
                tenant_id=tenant_id,
                snapshot=snapshot,
                run_id=run_id,
            )
        except Exception as exc:
            error_message: Any = str(exc).lower()
            if "append-only" not in error_message and "bất biến" not in error_message:
                raise
            await session.rollback()
            logger.warning(
                "worker.ai1_result.persistence_skipped_immutable",
                dossier_id=dossier_id,
                document_id=document_id,
                run_id=run_id,
                error=str(exc),
            )
        extracted = await _record_ai1_document(
            session, run_id=run_id, document_id=document_id, snapshot=canonical_snapshot
        )
        page_count = len(
            canonical_snapshot.get("pages", [])
            if canonical_snapshot is not None
            else getattr(snapshot, "pages", [])
        )
        all_extracted = dossier_document_ids <= extracted
        steps = ("S2", "S3", "S8") if all_extracted else ("S2",)
        for step in steps:
            await update_pipeline_step(
                session,
                tenant_id=tenant_id,
                run_id=run_id,
                step=step,
                status="succeeded" if all_extracted else "running",
                pages=page_count,
                metrics={
                    "service": "ai1",
                    "document_id": document_id,
                    "extracted_documents": len(extracted & dossier_document_ids),
                    "total_documents": len(dossier_document_ids),
                },
            )
        await _mark_status(
            session,
            status_value=(
                JobStatus.EXTRACTED.value if all_extracted else JobStatus.PROCESSING.value
            ),
            dossier_id=dossier_id,
            run_id=run_id,
            audit_action="ai1.snapshot_persisted",
            audit_detail={
                **base_audit,
                "document_id": document_id,
                "schema_version": canonical_snapshot.get("schema_version")
                if canonical_snapshot is not None
                else "ai1.snapshot.v3",
                "snapshot_digest": _snapshot_digest(canonical_snapshot)
                if canonical_snapshot is not None
                else None,
                "extracted_documents": len(extracted & dossier_document_ids),
                "total_documents": len(dossier_document_ids),
            },
        )
        await session.commit()
        if dedupe_key:
            _seen_result_ids.add(dedupe_key)
        logger.info(
            "worker.ai1_result.persisted",
            dossier_id=dossier_id,
            document_id=document_id,
            run_id=run_id,
            job_id=job_id,
            all_extracted=all_extracted,
        )
        if all_extracted:
            await _run_ai2_if_ready(
                session,
                dossier_id=dossier_id,
                tenant_id=tenant_id,
                run_id=run_id,
            )
    except Exception:
        await session.rollback()
        logger.exception(
            "worker.ai1_result.persist_failed",
            dossier_id=dossier_id,
            run_id=run_id,
        )
        raise


async def handle_dossier_event(session: AsyncSession, message: dict[str, Any]) -> None:
    event_type = message.get("event")
    if event_type == "dossier.uploaded":
        await handle_dossier_uploaded(session, message)
        return
    if event_type == "dossier.manifest.confirmed":
        dossier_id = str(message.get("dossier_id") or "")
        if not dossier_id:
            return
        result = await session.execute(
            select(JobORM)
            .where(JobORM.dossier_id == dossier_id)
            .order_by(JobORM.created_at.desc())
            .limit(1)
        )
        job = result.scalar_one_or_none()
        if job and job.current_run_id:
            await _run_ai2_if_ready(
                session,
                dossier_id=dossier_id,
                tenant_id=job.tenant_id,
                run_id=str(job.current_run_id),
            )
        return
    logger.debug("worker.event.ignored", event_type=event_type)


async def run_dossier_events_consumer(session_factory: async_sessionmaker[AsyncSession]) -> None:
    settings = get_settings()
    consumer = AIOKafkaConsumer(
        settings.kafka_dossier_events_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_orchestrator_group_id,
        enable_auto_commit=True,
        auto_offset_reset="earliest",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )
    await consumer.start()
    logger.info(
        "worker.dossier_events.started",
        topic=settings.kafka_dossier_events_topic,
        group_id=settings.kafka_orchestrator_group_id,
    )
    try:
        async for record in consumer:
            message = record.value
            if not isinstance(message, dict):
                logger.warning("worker.invalid_message", raw=message)
                continue
            try:
                async with session_factory() as session:
                    await handle_dossier_event(session, message)
            except Exception:
                logger.exception(
                    "worker.dossier_event_failed",
                    event_type=message.get("event"),
                    dossier_id=message.get("dossier_id"),
                )
    finally:
        await consumer.stop()


async def run_ai1_results_consumer(session_factory: async_sessionmaker[AsyncSession]) -> None:
    settings = get_settings()
    consumer = AIOKafkaConsumer(
        settings.kafka_ai1_ocr_results_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_backend_ai1_results_group_id,
        enable_auto_commit=True,
        auto_offset_reset="earliest",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        # Match broker message.max.bytes so large OCR snapshots (~1.6MB+) can be fetched.
        max_partition_fetch_bytes=10_485_760,
        fetch_max_bytes=10_485_760,
    )
    await consumer.start()
    logger.info(
        "worker.ai1_results.started",
        topic=settings.kafka_ai1_ocr_results_topic,
        group_id=settings.kafka_backend_ai1_results_group_id,
    )
    try:
        async for record in consumer:
            message = record.value
            if not isinstance(message, dict):
                logger.warning("worker.ai1_results.invalid_message", raw=message)
                continue
            try:
                async with session_factory() as session:
                    await handle_ai1_result(session, message)
            except Exception:
                logger.exception(
                    "worker.ai1_result_failed",
                    event_type=message.get("event_type"),
                    event_id=message.get("event_id"),
                )
    finally:
        await consumer.stop()


async def run_consumer() -> None:
    """Start producer + dossier_events and AI1 results consumers.

    AI2 is not on Kafka: the worker submits/polls it over HTTP once every
    document of the run has an AI1 snapshot (``_run_ai2_if_ready``).
    """
    settings = get_settings()
    engine = create_async_engine(settings.database_url, future=True)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    await messaging.start_producer()
    logger.info(
        "worker.started",
        bootstrap_servers=settings.kafka_bootstrap_servers,
        commands_topic=settings.kafka_ai1_ocr_commands_topic,
        results_topic=settings.kafka_ai1_ocr_results_topic,
    )
    try:
        await asyncio.gather(
            run_dossier_events_consumer(session_factory),
            run_ai1_results_consumer(session_factory),
        )
    finally:
        await messaging.stop_producer()
        await engine.dispose()
        logger.info("worker.stopped")


def main() -> None:
    """CLI entrypoint."""
    asyncio.run(run_consumer())


if __name__ == "__main__":
    main()
