import concurrent.futures
import logging
import signal
import threading

from sqlalchemy import select

from app.audit import log_event
from app.comparison import compare
from app.config import settings
from app.db import Session
from app.document_processing import process_page
from app.domain import DomainError
from app.evidence import citation, validate_result
from app.facts import extract
from app.models import Job, Snapshot, Task
from app.orchestration import claim_batch, finish, heartbeat
from app.storage import ArtifactStore, canonical, digest
from app.structure import clauses
from app.tables import link_continuations

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
            "tables": link_continuations([table for p in pages for table in p.get("tables", [])]),
            "facts": facts,
            "findings": compare(facts),
            "issues": issues,
            "limitations": [
                "RULE_BASED_CANDIDATES",
                "TABLE_EXTRACTION_GEOMETRY_HEURISTIC",
                "CONTEXT_REQUIRES_HUMAN_REVIEW",
            ],
            "citations": [],
        }
        try:
            result["citations"] = [citation(p, line, job.id) for p in pages for line in p["lines"]]
            validate_result(result)
        except DomainError as exc:
            job.status, job.failure_code = "failed", exc.code
            log_event(db, job.dossier_id, "system", "job.failed", "job", job.id,
                      result="failure", detail={"failure_code": exc.code})
            continue
        db.add(Snapshot(job_id=job.id, result_hash=digest(canonical(result)), result=result))
        job.status = "failed" if any(t.status == "failed" for t in tasks) else "pending_review"
        job.failure_code = "PAGE_PROCESSING_FAILED" if job.status == "failed" else None
        log_event(db, job.dossier_id, "system", f"job.{job.status}", "job", job.id,
                  result="failure" if job.status == "failed" else "success",
                  detail={"failure_code": job.failure_code, "is_partial": result["is_partial"]})


def run_once(factory=Session, config=settings, processor=process_page):
    with factory.begin() as db:
        tasks = claim_batch(db, config, limit=max(1, config.page_concurrency))
        claims = [
            (task.id, task.lease_token, task.payload, db.get(Job, task.job_id).config)
            for task in tasks
        ]
    if not claims:
        with factory.begin() as db:
            publish_ready(db)
        return False

    stop = threading.Event()
    lock = threading.Lock()
    # Leases still renew one at a time (each is its own claim/finish transaction) --
    # only the OCR work itself (process_page) runs concurrently across threads.
    active = {task_id: (token, run_config["lease_seconds"]) for task_id, token, _, run_config in claims}
    tick = max(1, min(run_config["lease_seconds"] for *_, run_config in claims) / 3)

    def keep_alive():
        while not stop.wait(tick):
            with lock:
                items = list(active.items())
            for task_id, (token, lease_seconds) in items:
                try:
                    with factory.begin() as db:
                        if not heartbeat(db, task_id, token, lease_seconds):
                            with lock:
                                active.pop(task_id, None)
                except Exception:
                    log.warning("heartbeat_failed")
                    with lock:
                        active.pop(task_id, None)

    thread = threading.Thread(target=keep_alive, daemon=True)
    thread.start()

    def process_one(task_id, token, payload, run_config):
        output, error = None, None
        try:
            output = processor(payload, run_config, ArtifactStore(config.artifact_root))
        except DomainError as exc:
            error = exc.code
        except Exception:
            # Do not log exception text: OCR/provider errors may contain document content.
            error = "PAGE_PROCESSING_FAILED"
        with lock:
            active.pop(task_id, None)
        try:
            with factory.begin() as db:
                finish(db, task_id, token, output, error)
        except DomainError:
            log.warning("lease_lost")

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(claims)) as pool:
            futures = [pool.submit(process_one, *claim_args) for claim_args in claims]
            for future in concurrent.futures.as_completed(futures):
                future.result()
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
