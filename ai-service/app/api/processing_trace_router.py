"""Signed internal read API for the bounded HTTP-worker processing trace."""

from __future__ import annotations

import json

from fastapi import APIRouter, Header, HTTPException

from app.security.service_envelope import ServiceEnvelopeError, verify_service_envelope
from app.tools.jobs import job_store_from_env
from app.tools.processing_trace_store import ProcessingTraceStore, project_processing_trace

router = APIRouter()


@router.get("/internal/processing-trace/{job_id}")
def read_processing_trace(
    job_id: str,
    dossier_id: str,
    snapshot_digest: str,
    x_ai2_service_envelope: str | None = Header(default=None),
) -> dict:
    if not x_ai2_service_envelope:
        raise HTTPException(401, detail={"code": "SERVICE_ENVELOPE_MISSING"})
    try:
        raw_envelope = json.loads(x_ai2_service_envelope)
        envelope = verify_service_envelope(
            {"job_id": job_id, "dossier_id": dossier_id, "snapshot_digest": snapshot_digest,
             "service_envelope": raw_envelope},
            required_scope="ai2.trace.read",
        )
    except (json.JSONDecodeError, ServiceEnvelopeError) as exc:
        raise HTTPException(401, detail={"code": getattr(exc, "code", "SERVICE_ENVELOPE_INVALID")}) from exc

    if envelope.dossier_id != dossier_id:
        raise HTTPException(403, detail={"code": "TRACE_SCOPE_MISMATCH"})
    try:
        job_store = job_store_from_env()
        job = job_store.get(job_id, tenant_id=envelope.tenant_id, dossier_id=dossier_id)
        if job is None:
            raise HTTPException(404, detail={"code": "TRACE_JOB_NOT_FOUND"})
        if job.get("trace_status") == "UNAVAILABLE":
            return {
                "schema_version": "ai2.processing-trace.v1",
                "trace_status": "UNAVAILABLE",
                "status": "TRACE_UNAVAILABLE",
                "snapshot_digest": snapshot_digest,
                "stages": [],
            }
        trace_store = ProcessingTraceStore(job_store)
        events = trace_store.read_latest_execution(
            tenant_id=envelope.tenant_id, dossier_id=dossier_id, job_id=job_id,
            snapshot_digest=snapshot_digest,
        )
        projection = project_processing_trace(events, terminal_job=job["status"] in {
            "SUCCEEDED", "FAILED", "CANCELLED",
        })
        return {
            "schema_version": "ai2.processing-trace.v1",
            "trace_status": "AVAILABLE" if events else "UNAVAILABLE",
            "job_status": job["status"],
            "snapshot_digest": snapshot_digest,
            **projection,
        }
    except HTTPException:
        raise
    except Exception:
        return {
            "schema_version": "ai2.processing-trace.v1",
            "trace_status": "UNAVAILABLE",
            "status": "TRACE_UNAVAILABLE",
            "reason_code": "TRACE_STORE_UNAVAILABLE",
            "snapshot_digest": snapshot_digest,
            "stages": [],
        }
