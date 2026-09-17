import logging
import signal
import threading

from sqlalchemy import select

from app.comparison import compare
from app.config import settings
from app.db import Session
from app.document_processing import process_page
from app.domain import DomainError
from app.evidence import citation, validate_result
from app.facts import extract
from app.models import Job, Snapshot, Task
from app.orchestration import claim, finish, heartbeat
from app.storage import ArtifactStore, canonical, digest
from app.structure import clauses

log = logging.getLogger("worker")


def publish_ready(db):
    jobs = list(
        db.scalars(
            select(Job)
            .where(Job.status.in_(["processing", "uploaded"]))
            .with_for_update(skip_locked=True)
        )
    )
    for job in jobs:
        tasks = list(db.scalars(select(Task).where(Task.job_id == job.id).order_by(Task.task_key)))
        if not tasks or any(t.status in ("queued", "running") for t in tasks):
            continue
        pages = [t.output for t in tasks if t.output]
        pages.sort(key=lambda p: (p["document_id"], p["page_number"]))
        issues = [
            {
                "code": t.error_code or t.output.get("issue"),
                "document_id": t.payload["document_id"],
                "page_number": t.payload["page_number"],
            }
            for t in tasks
            if t.status == "failed" or (t.output and t.output.get("issue"))
        ]
        facts = extract(pages, job.id)
        result = {
            "schema_version": "0.1",
            "run_id": job.id,
            "dossier_id": job.dossier_id,
            "is_partial": bool(issues),
            "review_required": True,
            "coverage": {
                "expected_pages": len(tasks),
                "completed_pages": len(pages),
                "failed_pages": sum(t.status == "failed" for t in tasks),
                "coverage_complete": not issues,
                "processing_complete": True,
            },
            "documents": job.manifest["documents"],
            "pages": pages,
            "clauses": clauses(pages, job.id),
            "tables": [],
            "facts": facts,
            "findings": compare(facts),
            "issues": issues,
            "limitations": [
                "RULE_BASED_CANDIDATES",
                "TABLE_EXTRACTION_NOT_IMPLEMENTED",
                "CONTEXT_REQUIRES_HUMAN_REVIEW",
            ],
            "citations": [],
        }
        try:
            result["citations"] = [citation(p, line, job.id) for p in pages for line in p["lines"]]
            validate_result(result)
        except DomainError as exc:
            job.status, job.failure_code = "failed", exc.code
            continue
        db.add(Snapshot(job_id=job.id, result_hash=digest(canonical(result)), result=result))
        job.status = "failed" if any(t.status == "failed" for t in tasks) else "pending_review"
        job.failure_code = "PAGE_PROCESSING_FAILED" if job.status == "failed" else None


def run_once(factory=Session, config=settings, processor=process_page):
    with factory.begin() as db:
        task = claim(db, config)
        if task:
            task_id, token, payload = task.id, task.lease_token, task.payload
            run_config = db.get(Job, task.job_id).config
    if not task:
        with factory.begin() as db:
            publish_ready(db)
        return False
    stop = threading.Event()

    def keep_alive():
        while not stop.wait(max(1, run_config["lease_seconds"] / 3)):
            try:
                with factory.begin() as db:
                    if not heartbeat(db, task_id, token, run_config["lease_seconds"]):
                        return
            except Exception:
                log.warning("heartbeat_failed")
                return

    thread = threading.Thread(target=keep_alive, daemon=True)
    thread.start()
    output, error = None, None
    try:
        output = processor(payload, run_config, ArtifactStore(config.artifact_root))
    except DomainError as exc:
        error = exc.code
    except Exception:
        # Do not log exception text: OCR/provider errors may contain document content.
        error = "PAGE_PROCESSING_FAILED"
    try:
        with factory.begin() as db:
            finish(db, task_id, token, output, error)
    except DomainError:
        log.warning("lease_lost")
    finally:
        stop.set()
        thread.join(timeout=2)
    with factory.begin() as db:
        publish_ready(db)
    return True


def main():
    logging.basicConfig(level=logging.INFO)
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    while not stop.is_set():
        try:
            busy = run_once()
        except Exception:
            log.error("worker_iteration_failed")
            busy = False
        if not busy:
            stop.wait(settings.poll_seconds)


if __name__ == "__main__":
    main()
