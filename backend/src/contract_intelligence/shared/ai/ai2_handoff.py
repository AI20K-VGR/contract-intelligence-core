"""Backend → AI2 Kafka IDP handoff (DOC-05e).

After AI1 OCR persist, the Kafka worker publishes ``ai2.idp.command`` on
``ci.ai2.idp.commands`` with a body-only ``be.ai2.processing.request.v1``
payload. AI2 consumes, processes, and publishes results; Backend applies
them via ``apply_ai2_wire_result`` (same pending_review path as the webhook).

HTTP ``POST /jobs/idp`` + poll remains lab/demo only — see ``run_ai2_idp_http_handoff``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.config.settings import get_settings
from contract_intelligence.contract.domain.entities.job import JobStatus
from contract_intelligence.contract.infrastructure.persistence.orm import DossierORM, JobORM
from contract_intelligence.infrastructure import messaging
from contract_intelligence.infrastructure.ai_adapters import (
    AiAdapterError,
    build_idp_request,
    poll_idp_job,
    submit_idp_job,
    wire_result_to_findings_payload,
)
from contract_intelligence.shared.ai.persistence import (
    persist_ai2_comparison,
    persist_ai2_extraction,
)
from contract_intelligence.shared.base import new_ulid, utcnow

logger = structlog.get_logger(__name__)

SCHEMA_VERSION = "ci.kafka.v1"
EVENT_AI2_IDP_COMMAND = "ai2.idp.command"
EVENT_AI2_IDP_COMPLETED = "ai2.idp.completed"
EVENT_AI2_IDP_FAILED = "ai2.idp.failed"


def extract_ai1_v1_snapshot(ocr_result: dict[str, Any]) -> dict[str, Any] | None:
    """Pull ``ai1.snapshot.v1`` from an AI1 Kafka ``payload.result`` object."""
    snapshot = ocr_result.get("snapshot")
    if isinstance(snapshot, dict) and snapshot.get("schema_version") == "ai1.snapshot.v1":
        return dict(snapshot)
    if ocr_result.get("schema_version") == "ai1.snapshot.v1" and "pages" in ocr_result:
        return dict(ocr_result)
    # Adapted snapshot from ``adapt_ai1_snapshot_result`` may already be flat.
    if isinstance(ocr_result, dict) and "pages" in ocr_result and ocr_result.get("snapshot_id"):
        return dict(ocr_result)
    return None


def _utcnow_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


async def _mark_pending_review(
    session: AsyncSession,
    *,
    dossier_id: str | None,
    run_id: str | None,
) -> None:
    now = utcnow()
    job: JobORM | None = None
    if run_id:
        from sqlalchemy import select

        result = await session.execute(
            select(JobORM).where(JobORM.current_run_id == run_id).limit(1)
        )
        job = result.scalar_one_or_none()
    if job is None and dossier_id:
        from sqlalchemy import select

        result = await session.execute(
            select(JobORM)
            .where(JobORM.dossier_id == dossier_id)
            .order_by(JobORM.created_at.desc())
            .limit(1)
        )
        job = result.scalar_one_or_none()
    if job is None:
        return
    job.status = JobStatus.PENDING_REVIEW.value
    job.updated_at = now
    await session.execute(
        update(DossierORM)
        .where(DossierORM.id == job.dossier_id)
        .values(status=JobStatus.PENDING_REVIEW.value, updated_at=now)
    )


async def _seed_review_items(
    session: AsyncSession,
    *,
    tenant_id: str,
    dossier_id: str,
    run_id: str,
    findings: list[Any],
) -> int:
    created = 0
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        item_id = new_ulid("ri_")
        finding_id = str(finding.get("finding_id") or finding.get("id") or item_id)
        title = str(
            finding.get("title")
            or finding.get("finding_type")
            or finding.get("kind")
            or "AI2 finding"
        )
        await session.execute(
            text(
                """
                INSERT INTO review_item (
                    id, tenant_id, dossier_id, finding_id, title, status,
                    severity, version, created_at, updated_at
                ) VALUES (
                    :id, :tenant_id, :dossier_id, :finding_id, :title, 'open',
                    :severity, 1, :now, :now
                )
                ON CONFLICT DO NOTHING
                """
            ),
            {
                "id": item_id,
                "tenant_id": tenant_id,
                "dossier_id": dossier_id,
                "finding_id": finding_id,
                "title": title[:500],
                "severity": str(finding.get("severity") or "medium"),
                "now": utcnow(),
            },
        )
        created += 1
    return created


async def apply_ai2_wire_result(
    session: AsyncSession,
    *,
    tenant_id: str,
    dossier_id: str,
    run_id: str,
    wire: dict[str, Any],
) -> dict[str, Any]:
    """Persist wire result → facts/findings/ReviewItems + pending_review."""
    flat = wire_result_to_findings_payload(wire, run_id=run_id)
    status = str(wire.get("status") or "")
    if status.upper() in {"FAILED", "CANCELLED"}:
        await _mark_pending_review(session, dossier_id=dossier_id, run_id=run_id)
        return {"status": status, "persisted_facts": 0, "persisted_findings": 0, "review_items": 0}

    persisted_facts = 0
    persisted_findings = 0
    for block in flat["facts"]:
        if not isinstance(block, dict) or "document_id" not in block:
            continue
        try:
            persisted_facts += await persist_ai2_extraction(
                session,
                tenant_id=tenant_id,
                extraction=block,
                run_id=run_id,
            )
        except Exception:
            logger.exception("ai2_handoff.persist_extraction_failed", run_id=run_id)

    findings = flat["findings"]
    if findings:
        comparison_candidate: dict[str, Any] | None = None
        first = findings[0] if findings else None
        if isinstance(first, dict) and str(first.get("schema_version", "")).startswith(
            "ai2.comparison"
        ):
            comparison_candidate = first
        elif all(isinstance(f, dict) and "finding_type" in f for f in findings):
            comparison_candidate = {
                "schema_version": "ai2.comparison.v2",
                "dossier_id": dossier_id,
                "annex_links": [],
                "findings": findings,
            }
        if comparison_candidate is not None:
            try:
                persisted_findings = await persist_ai2_comparison(
                    session,
                    tenant_id=tenant_id,
                    comparison=comparison_candidate,
                    run_id=run_id,
                )
            except Exception:
                logger.exception("ai2_handoff.persist_comparison_failed", run_id=run_id)

    review_items = 0
    if persisted_findings == 0 and findings:
        review_items = await _seed_review_items(
            session,
            tenant_id=tenant_id,
            dossier_id=dossier_id,
            run_id=run_id,
            findings=findings,
        )

    if findings:
        await session.execute(
            update(DossierORM).where(DossierORM.id == dossier_id).values(has_conflicts=True)
        )

    await _mark_pending_review(session, dossier_id=dossier_id, run_id=run_id)
    await session.flush()
    return {
        "status": status,
        "persisted_facts": persisted_facts,
        "persisted_findings": persisted_findings,
        "review_items": review_items,
        "index_contribution_keys": list(flat["index_contribution"].keys()),
    }


async def publish_ai2_idp_command(
    *,
    tenant_id: str,
    dossier_id: str,
    document_id: str,
    run_id: str | None,
    snapshot: dict[str, Any],
    source_digest: str,
    event_id: str | None = None,
    task_id: int | None = None,
    attempt_id: int = 1,
) -> dict[str, Any]:
    """Publish ``ai2.idp.command`` with full body-only processing request (DOC-05e)."""
    settings = get_settings()
    evt = event_id or new_ulid("evt_")
    snap_id = str(snapshot.get("snapshot_id") or "")
    request = build_idp_request(
        tenant_id=tenant_id,
        dossier_id=dossier_id,
        snapshot=snapshot,
        document_id=document_id,
        source_digest=source_digest,
        request_id=f"req_{evt}",
        idempotency_key=f"idem_{dossier_id}_{snap_id}_{evt}",
        role="body",
    )
    resolved_run = str(run_id or new_ulid("run_"))
    envelope: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "event_id": evt,
        "event_type": EVENT_AI2_IDP_COMMAND,
        "occurred_at": _utcnow_iso(),
        "trace_id": resolved_run,
        "tenant_id": tenant_id,
        "correlation": {
            "dossier_id": dossier_id,
            "document_id": document_id,
            "task_id": task_id if task_id is not None else 0,
            "attempt_id": attempt_id,
            "run_id": resolved_run,
        },
        "payload": request,
    }
    await messaging.publish_event(
        settings.kafka_ai2_idp_commands_topic,
        envelope,
        key=dossier_id,
    )
    logger.info(
        "ai2_handoff.command_published",
        dossier_id=dossier_id,
        document_id=document_id,
        run_id=resolved_run,
        event_id=evt,
        snapshot_id=snap_id,
    )
    return envelope


async def publish_ai2_idp_after_ocr(
    *,
    tenant_id: str,
    dossier_id: str,
    document_id: str,
    run_id: str | None,
    snapshot: dict[str, Any],
    source_digest: str,
    event_id: str | None = None,
    task_id: int | None = None,
) -> dict[str, Any] | None:
    """Gate + publish AI2 Kafka command after successful AI1 OCR persist."""
    settings = get_settings()
    if not settings.ai2_wire_enabled:
        logger.info("ai2_handoff.disabled", dossier_id=dossier_id)
        return None
    return await publish_ai2_idp_command(
        tenant_id=tenant_id,
        dossier_id=dossier_id,
        document_id=document_id,
        run_id=run_id,
        snapshot=snapshot,
        source_digest=source_digest,
        event_id=event_id,
        task_id=task_id,
    )


async def run_ai2_idp_http_handoff(
    session: AsyncSession,
    *,
    tenant_id: str,
    dossier_id: str,
    document_id: str,
    run_id: str | None,
    snapshot: dict[str, Any],
    source_digest: str,
    event_id: str | None = None,
) -> dict[str, Any]:
    """Lab/demo only: HTTP POST /jobs/idp + poll (not the Kafka runtime path)."""
    settings = get_settings()
    if not settings.ai2_wire_enabled:
        logger.info("ai2_handoff.http.disabled", dossier_id=dossier_id)
        return {"status": "skipped", "reason": "ai2_wire_disabled"}

    snap_id = str(snapshot.get("snapshot_id") or "")
    request = build_idp_request(
        tenant_id=tenant_id,
        dossier_id=dossier_id,
        snapshot=snapshot,
        document_id=document_id,
        source_digest=source_digest,
        request_id=f"req_{event_id or new_ulid('req_')}",
        idempotency_key=f"idem_{dossier_id}_{snap_id}_{event_id or '1'}",
    )
    try:
        queued = await submit_idp_job(request)
        job_id = str(queued.get("job_id") or "")
        if not job_id:
            raise AiAdapterError("AI2 /jobs/idp response missing job_id")
        wire = await poll_idp_job(
            job_id,
            dossier_id=dossier_id,
            tenant_id=tenant_id,
        )
    except AiAdapterError as exc:
        logger.error("ai2_handoff.http.failed", dossier_id=dossier_id, error=str(exc))
        await _mark_pending_review(session, dossier_id=dossier_id, run_id=run_id)
        await session.flush()
        return {"status": "failed", "error": str(exc)}

    summary = await apply_ai2_wire_result(
        session,
        tenant_id=tenant_id,
        dossier_id=dossier_id,
        run_id=str(run_id or ""),
        wire=wire,
    )
    logger.info(
        "ai2_handoff.http.completed",
        dossier_id=dossier_id,
        job_id=wire.get("job_id"),
        **summary,
    )
    return summary


# Back-compat alias — prefer publish_ai2_idp_after_ocr / Kafka consumer path.
async def run_ai2_idp_handoff(
    session: AsyncSession,
    *,
    tenant_id: str,
    dossier_id: str,
    document_id: str,
    run_id: str | None,
    snapshot: dict[str, Any],
    source_digest: str,
    event_id: str | None = None,
) -> dict[str, Any]:
    """Deprecated name: publishes Kafka command only (no HTTP poll)."""
    envelope = await publish_ai2_idp_after_ocr(
        tenant_id=tenant_id,
        dossier_id=dossier_id,
        document_id=document_id,
        run_id=run_id,
        snapshot=snapshot,
        source_digest=source_digest,
        event_id=event_id,
    )
    if envelope is None:
        return {"status": "skipped", "reason": "ai2_wire_disabled"}
    return {"status": "command_published", "event_id": envelope.get("event_id")}


__all__ = [
    "EVENT_AI2_IDP_COMMAND",
    "EVENT_AI2_IDP_COMPLETED",
    "EVENT_AI2_IDP_FAILED",
    "SCHEMA_VERSION",
    "apply_ai2_wire_result",
    "extract_ai1_v1_snapshot",
    "publish_ai2_idp_after_ocr",
    "publish_ai2_idp_command",
    "run_ai2_idp_handoff",
    "run_ai2_idp_http_handoff",
]
