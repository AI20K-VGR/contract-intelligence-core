from copy import deepcopy

from sqlalchemy import select

from app.comparison import compare
from app.corrections import validate_correction
from app.domain import require
from app.evidence import validate_result
from app.ingestion import lock_dossier
from app.models import AnalysisRevision, Approval, Job, ReviewEvent, Snapshot
from app.storage import canonical, digest


def effective_result(db, job, snapshot):
    revision = db.scalar(select(AnalysisRevision).where(AnalysisRevision.job_id == job.id)
                         .order_by(AnalysisRevision.review_version.desc()).limit(1))
    return (revision.result, revision.result_hash, revision.review_version) if revision else (
        snapshot.result, snapshot.result_hash, 0)


def recompute(db, job, snapshot, event):
    previous, _, _ = effective_result(db, job, snapshot)
    result = deepcopy(previous)
    fact = next(f for f in result["facts"] if f["id"] == event.target_id)
    fact["normalized"] = event.correction
    fact["human_provenance"] = {"event_id": event.id, "actor": event.actor,
                                "review_version": event.version}
    previous_findings = {tuple(f["fact_ids"]): f for f in result["findings"]}
    findings = compare(result["facts"])
    for finding in findings:
        prior = previous_findings.get(tuple(finding["fact_ids"]))
        if prior and event.target_id not in finding["fact_ids"]:
            finding.clear()
            finding.update(prior)
        else:
            finding["id"] = f"{finding['id']}@{event.version}"
            finding["supersedes"] = prior["id"] if prior else None
            finding["analysis_revision"] = event.version
    result["findings"] = findings
    validate_result(result)
    db.add(AnalysisRevision(job_id=job.id, review_version=event.version,
                            result=result, result_hash=digest(canonical(result))))
    db.flush()


def review_state(db, job, snapshot):
    events = list(
        db.scalars(
            select(ReviewEvent).where(ReviewEvent.job_id == job.id).order_by(ReviewEvent.version)
        )
    )
    latest = {event.target_id: event for event in events}
    effective, _, analysis_version = effective_result(db, job, snapshot)
    required = {
        "completeness",
        *[
            f"relation:{d['document_id']}"
            for d in job.manifest["documents"]
            if d["role"] == "appendix"
        ],
        *[f["id"] for f in effective["facts"]],
        *[f["id"] for f in effective["findings"]],
    }
    unresolved = sorted(
        target
        for target in required
        if target not in latest or latest[target].action in ("needs_more_evidence", "reject")
        or (target == "completeness" and latest[target].version < analysis_version)
    )
    stale = any(event.action == "correct" and event.version > analysis_version for event in events)
    blocked = (
        snapshot.result["is_partial"]
        or stale
        or bool(unresolved)
        or any(e.action == "reject" and e.target_id in required for e in latest.values())
    )
    return {
        "unresolved": unresolved,
        "stale": stale,
        "blocked": blocked,
        "analysis_version": analysis_version,
        "targets": sorted(required),
        "history": [
            {
                "id": e.id,
                "target_id": e.target_id,
                "action": e.action,
                "actor": e.actor,
                "reason": e.reason,
                "correction": e.correction,
                "version": e.version,
                "created_at": e.created_at,
            }
            for e in events
        ],
    }


def append_review(db, body, actor):
    job = db.get(Job, body.job_id)
    require(job is not None, "JOB_NOT_FOUND", 404)
    dossier = lock_dossier(db, job.dossier_id)
    require(dossier.active_job_id == job.id, "STALE_RUN")
    require(dossier.review_version == body.expected_revision, "STALE_REVIEW_VERSION")
    require(job.status in ("pending_review", "reviewed"), "JOB_NOT_REVIEWABLE")
    snapshot = db.scalar(select(Snapshot).where(Snapshot.job_id == job.id))
    state = review_state(db, job, snapshot)
    targets = set(state["targets"])
    require(body.target_id in targets, "REVIEW_TARGET_NOT_FOUND", 404)
    require(body.action == "confirm" or bool(body.reason.strip()), "REASON_REQUIRED", 422)
    if body.action == "correct":
        require(
            body.target_id.startswith("fact:") and body.correction is not None,
            "FACT_CORRECTION_REQUIRED",
            422,
        )
        fact = next(f for f in snapshot.result["facts"] if f["id"] == body.target_id)
        validate_correction(fact, body.correction)
    else:
        require(body.correction is None, "UNEXPECTED_CORRECTION", 422)
    dossier.review_version += 1
    event = ReviewEvent(
        job_id=job.id,
        actor=actor.id,
        version=dossier.review_version,
        target_id=body.target_id,
        action=body.action,
        reason=body.reason,
        correction=body.correction,
    )
    db.add(event)
    db.flush()
    if body.action == "correct":
        recompute(db, job, snapshot, event)
    job.status = "pending_review" if review_state(db, job, snapshot)["blocked"] else "reviewed"
    return {"id": event.id, "review_version": dossier.review_version, "status": job.status}


def approve(db, dossier_id, expected_revision, actor):
    dossier = lock_dossier(db, dossier_id)
    require(dossier.review_version == expected_revision, "STALE_REVIEW_VERSION")
    job = db.get(Job, dossier.active_job_id) if dossier.active_job_id else None
    require(job is not None and job.status == "reviewed", "APPROVAL_GATE_BLOCKED")
    snapshot = db.scalar(select(Snapshot).where(Snapshot.job_id == job.id))
    require(not review_state(db, job, snapshot)["blocked"], "APPROVAL_GATE_BLOCKED")
    _, effective_hash, _ = effective_result(db, job, snapshot)
    approval = Approval(
        job_id=job.id,
        dossier_revision=job.dossier_revision,
        review_version=dossier.review_version,
        result_hash=effective_hash,
        actor=actor.id,
    )
    db.add(approval)
    job.status = "approved"
    db.flush()
    return {"id": approval.id, "job_id": job.id, "result_hash": effective_hash,
            "machine_result_hash": snapshot.result_hash}
