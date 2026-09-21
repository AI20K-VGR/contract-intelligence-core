import time

from sqlalchemy import or_, select, update

from app.domain import require, uid
from app.ingestion import lock_dossier
from app.models import Attempt, Document, Job, Task


def enqueue(db, dossier_id, settings, overrides=None):
    dossier = lock_dossier(db, dossier_id)
    docs = list(db.scalars(select(Document).where(Document.dossier_id == dossier_id)))
    require(sum(d.role == "contract" for d in docs) == 1, "EXACTLY_ONE_CONTRACT", 422)
    if dossier.active_job_id:
        prior = db.get(Job, dossier.active_job_id)
        require(prior.status not in ("uploaded", "processing", "extracted"), "JOB_ACTIVE")
    manifest = [
        {
            "document_id": d.id,
            "sha256": d.sha256,
            "role": d.role,
            "storage_key": d.storage_key,
            "page_count": d.page_count,
        }
        for d in docs
    ]
    config = {
        "profile": "terra_assisted" if settings.ocr_engine == "gpt_vision" else "local_baseline",
        "schema_version": "0.1",
        "rule_version": "local-v1",
        "dpi": settings.dpi,
        "max_pixels": settings.max_pixels,
        "ocr_languages": settings.ocr_languages,
        "ocr_timeout_seconds": settings.ocr_timeout_seconds,
        "ocr_engine": settings.ocr_engine,
        "ocr_vision_model": settings.ocr_vision_model,
        "ocr_vision_max_retries": settings.ocr_vision_max_retries,
        "max_attempts": settings.max_attempts,
        "lease_seconds": settings.lease_seconds,
        # Per-dossier opt-in only (see app/table_continuity.py) -- never a
        # deployment-wide default, since enabling it sends some contract table text
        # to DeepSeek's hosted API.
        "table_continuity_agent": bool((overrides or {}).get("table_continuity_agent")),
    }
    job = Job(
        dossier_id=dossier_id,
        dossier_revision=dossier.revision,
        manifest={"documents": manifest},
        config=config,
    )
    db.add(job)
    db.flush()
    for doc in manifest:
        for page in range(1, doc["page_count"] + 1):
            db.add(
                Task(
                    job_id=job.id,
                    task_key=f"{doc['document_id']}:{page}",
                    payload={**doc, "page_number": page},
                )
            )
    dossier.active_job_id = job.id
    dossier.review_version = 0
    db.flush()
    return {"id": job.id, "status": job.status, "status_url": f"/api/v1/jobs/{job.id}"}


def claim(db, settings):
    now = time.time()
    # PostgreSQL row locking distributes work; SQLite is only for single-worker tests.
    tasks = db.scalars(
        select(Task)
        .where(
            or_(
                (Task.status == "queued") & (Task.retry_at <= now),
                (Task.status == "running") & (Task.lease_until < now),
            )
        )
        .order_by(Task.retry_at, Task.id)
        .with_for_update(skip_locked=True)
        .limit(20)
    )
    for task in tasks:
        job = db.get(Job, task.job_id)
        if task.lease_token:
            old = db.get(Attempt, task.lease_token)
            if old and old.finished_at is None:
                old.finished_at, old.error_code = now, "LEASE_EXPIRED"
        if task.attempts >= job.config["max_attempts"]:
            task.status, task.error_code = "failed", "ATTEMPTS_EXHAUSTED"
            continue
        task.status, task.lease_token = "running", uid()
        task.attempts += 1
        task.lease_until = now + job.config["lease_seconds"]
        db.add(Attempt(id=task.lease_token, task_id=task.id, number=task.attempts, started_at=now))
        job.status = "processing"
        db.flush()
        return task
    return None


def heartbeat(db, task_id, token, seconds):
    now = time.time()
    return (
        db.execute(
            update(Task)
            .where(
                Task.id == task_id,
                Task.status == "running",
                Task.lease_token == token,
                Task.lease_until > now,
            )
            .values(lease_until=now + seconds)
        ).rowcount
        == 1
    )


def finish(db, task_id, token, output=None, error=None):
    task = db.scalar(select(Task).where(Task.id == task_id).with_for_update())
    require(
        task.status == "running" and task.lease_token == token and task.lease_until > time.time(),
        "LEASE_LOST",
    )
    attempt = db.get(Attempt, token)
    attempt.finished_at, attempt.error_code = time.time(), error
    task.error_code = error
    if error:
        maximum = db.get(Job, task.job_id).config["max_attempts"]
        task.status = "queued" if task.attempts < maximum else "failed"
        task.retry_at = time.time() + 2**task.attempts
    else:
        task.status, task.output = "completed", output
    task.lease_until = 0
