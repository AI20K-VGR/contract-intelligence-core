from collections import Counter

from app.domain import require
from app.models import Job

CATEGORIES = {
    "uploaded": "Queued",
    "processing": "In Progress",
    "extracted": "In Progress",
    "pending_review": "Needs Review",
    "reviewed": "Done",
    "approved": "Done",
    "failed": "Failed",
}


def batch_summary(db, batch):
    require(batch is not None, "BATCH_NOT_FOUND", 404)
    jobs = [db.get(Job, job_id) for job_id in batch.job_ids]
    counts = Counter(CATEGORIES[job.status] for job in jobs)
    return {
        "id": batch.id,
        "total": len(jobs),
        "categories": {key: counts[key] for key in sorted(set(CATEGORIES.values()))},
        "jobs": [{"id": job.id, "status": job.status} for job in jobs],
    }
