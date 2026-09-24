"""Small compatibility job store for the legacy Backend AI2 client."""

from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4


_LOCK = Lock()
_JOBS: dict[str, dict] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_completed_job(*, kind: str, result: dict, tenant_id: str) -> dict:
    job_id = str(uuid4())
    report = {
        "job_id": job_id,
        "kind": kind,
        "status": "completed",
        "created_at": _now(),
        "updated_at": _now(),
        "result": result,
        "tenant_id": tenant_id,
    }
    with _LOCK:
        _JOBS[job_id] = report
    return {"job_id": job_id, "status": "completed"}


def create_failed_job(*, kind: str, code: str, message: str, tenant_id: str) -> dict:
    job_id = str(uuid4())
    report = {
        "job_id": job_id,
        "kind": kind,
        "status": "failed",
        "created_at": _now(),
        "updated_at": _now(),
        "error": {"code": code, "message": message},
        "tenant_id": tenant_id,
    }
    with _LOCK:
        _JOBS[job_id] = report
    return {"job_id": job_id, "status": "failed"}


def get_job(job_id: str) -> dict | None:
    with _LOCK:
        report = _JOBS.get(job_id)
        return dict(report) if report else None


def cancel_job(job_id: str) -> dict | None:
    with _LOCK:
        report = _JOBS.get(job_id)
        if report is None:
            return None
        if report["status"] in {"completed", "failed"}:
            return dict(report)
        report["status"] = "cancelled"
        report["updated_at"] = _now()
        return dict(report)


def clear_jobs() -> None:
    with _LOCK:
        _JOBS.clear()
