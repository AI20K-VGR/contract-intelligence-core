"""Compatibility job store for the Backend's legacy AI-service contract.

This is deliberately not an OCR implementation.  The legacy facade exists so
the current Backend can call AI2 without changing its client contract while
the canonical ``/jobs/idp`` path remains the evidence-complete integration.
Requests that do not carry authoritative source evidence fail closed instead
of fabricating facts, findings, or citations.
"""

from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock
from uuid import uuid4
from typing import Any


_LOCK = Lock()
_JOBS: dict[str, dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _job_report(job_id: str) -> dict[str, Any]:
    with _LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            raise KeyError(job_id)
        return dict(job)


def create_completed_job(*, kind: str, result: dict[str, Any], tenant_id: str = "") -> dict[str, Any]:
    now = _now()
    job_id = f"legacy_{uuid4().hex}"
    report = {
        "job_id": job_id,
        "kind": kind,
        "status": "completed",
        "progress_pct": 100,
        "current_stage": "compatibility_facade",
        "created_at": now,
        "updated_at": now,
        "finished_at": now,
        "result": result,
        "usage": None,
        "error": None,
        "tenant_id": tenant_id,
    }
    with _LOCK:
        _JOBS[job_id] = report
    return {
        "job_id": job_id,
        "kind": kind,
        "status": "queued",
        "created_at": now,
    }


def create_failed_job(*, kind: str, code: str, message: str, tenant_id: str = "") -> dict[str, Any]:
    now = _now()
    job_id = f"legacy_{uuid4().hex}"
    report = {
        "job_id": job_id,
        "kind": kind,
        "status": "failed",
        "progress_pct": 100,
        "current_stage": "compatibility_facade",
        "created_at": now,
        "updated_at": now,
        "finished_at": now,
        "result": None,
        "usage": None,
        "error": {"code": code, "message": message},
        "tenant_id": tenant_id,
    }
    with _LOCK:
        _JOBS[job_id] = report
    return {
        "job_id": job_id,
        "kind": kind,
        "status": "queued",
        "created_at": now,
    }


def get_job(job_id: str) -> dict[str, Any] | None:
    try:
        return _job_report(job_id)
    except KeyError:
        return None


def cancel_job(job_id: str) -> dict[str, Any] | None:
    with _LOCK:
        report = _JOBS.get(job_id)
        if report is None:
            return None
        if report["status"] not in {"completed", "failed", "cancelled"}:
            report["status"] = "cancelled"
            report["current_stage"] = "cancelled"
            report["updated_at"] = _now()
        return dict(report)


def clear_jobs() -> None:
    """Test-only reset; compatibility jobs are process-local by design."""

    with _LOCK:
        _JOBS.clear()


__all__ = [
    "cancel_job",
    "clear_jobs",
    "create_completed_job",
    "create_failed_job",
    "get_job",
]
