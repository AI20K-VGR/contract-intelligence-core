import time

from conftest import create_job, pdf_bytes
from sqlalchemy import select

from app.models import Attempt, Snapshot
from app.orchestration import claim, finish
from app.storage import ArtifactStore
from app.worker import run_once


def drain(factory, config):
    for _ in range(10):
        if not run_once(factory, config):
            return
    raise AssertionError("worker did not drain")


def test_native_end_to_end_review_approval_and_citation(system):
    client, factory, config = system
    dossier, job_id = create_job(client)
    drain(factory, config)
    result = client.get(f"/api/v1/dossiers/{dossier}/results").json()
    assert result["status"] == "pending_review"
    assert result["machine"]["coverage"]["expected_pages"] == 1
    assert len(result["machine"]["facts"]) == 3
    citation = result["machine"]["facts"][0]["citation_ids"][0]
    response = client.get(f"/api/v1/citations/{citation}/resolve")
    assert response.status_code == 200
    assert client.get(response.json()["page_url"]).headers["content-type"] == "image/png"
    blocked = client.post(
        f"/api/v1/dossiers/{dossier}/approve",
        json={"expected_revision": 0},
        headers={"Idempotency-Key": "blocked"},
    )
    assert blocked.status_code == 409
    original = result["result_hash"]
    for revision, target in enumerate(result["review"]["unresolved"]):
        response = client.post(
            "/api/v1/review-events",
            json={
                "job_id": job_id,
                "target_id": target,
                "action": "confirm",
                "expected_revision": revision,
            },
            headers={"Idempotency-Key": f"review-{revision}"},
        )
        assert response.status_code == 201, response.text
    response = client.post(
        f"/api/v1/dossiers/{dossier}/approve",
        json={"expected_revision": len(result["review"]["unresolved"])},
        headers={"Idempotency-Key": "approve"},
    )
    assert response.status_code == 201
    assert response.json()["result_hash"] == original
    assert client.get(f"/api/v1/jobs/{job_id}").json()["status"] == "approved"
    audit = client.get(f"/api/v1/dossiers/{dossier}/audit").json()["items"]
    actions = [e["action"] for e in audit]
    assert actions[0] == "dossier.created"
    assert "document.uploaded" in actions
    assert "job.enqueued" in actions
    assert "job.pending_review" in actions
    assert actions.count("review.confirm") == len(result["review"]["unresolved"])
    assert actions[-1] == "dossier.approved"
    assert all(e["created_at"] <= audit[i + 1]["created_at"] for i, e in enumerate(audit[:-1]))
    assert all(e["actor"] for e in audit)
    uploaded = next(e for e in audit if e["action"] == "document.uploaded")
    assert uploaded["object_type"] == "document" and uploaded["result"] == "success"


def test_document_list_file_and_page_text(system):
    client, factory, config = system
    dossier, job_id = create_job(client)
    drain(factory, config)
    docs = client.get(f"/api/v1/dossiers/{dossier}/documents").json()["items"]
    assert [d["role"] for d in docs] == ["contract"]
    document_id = docs[0]["id"]
    assert docs[0]["page_count"] == 1
    file_response = client.get(f"/api/v1/documents/{document_id}/file")
    assert file_response.status_code == 200
    assert file_response.content.startswith(b"%PDF-")
    text_response = client.get(
        f"/api/v1/documents/{document_id}/pages/1/text", params={"run_id": job_id}
    )
    assert text_response.status_code == 200
    body = text_response.json()
    assert body["engine"] == "pymupdf"
    assert any("Payment" in line["text"] for line in body["lines"])
    assert client.get(f"/api/v1/documents/{document_id}/pages/2/text", params={"run_id": job_id}).status_code == 404
    assert client.get("/api/v1/documents/missing/file").status_code == 404


def test_idempotency(system):
    client, _, _ = system
    body = {"title": "Demo"}
    headers = {"Idempotency-Key": "same"}
    first = client.post("/api/v1/dossiers", json=body, headers=headers)
    assert client.post("/api/v1/dossiers", json=body, headers=headers).json() == first.json()
    assert (
        client.post("/api/v1/dossiers", json={"title": "Changed"}, headers=headers).status_code
        == 409
    )


def test_manifest_freeze_and_contract_required(system):
    client, _, _ = system
    response = client.post(
        "/api/v1/dossiers", json={"title": "Empty"}, headers={"Idempotency-Key": "empty"}
    )
    empty = response.json()["id"]
    assert (
        client.post(
            f"/api/v1/dossiers/{empty}/jobs", headers={"Idempotency-Key": "start-empty"}
        ).status_code
        == 422
    )
    dossier, _ = create_job(client)
    response = client.post(
        f"/api/v1/dossiers/{dossier}/documents",
        files={"file": ("annex.pdf", pdf_bytes(), "application/pdf")},
        data={"role": "appendix"},
        headers={"Idempotency-Key": "late-upload"},
    )
    assert response.status_code == 409


def test_stale_review_and_correction_keep_machine(system):
    client, factory, config = system
    dossier, job_id = create_job(client)
    drain(factory, config)
    before = client.get(f"/api/v1/dossiers/{dossier}/results").json()
    target = before["machine"]["facts"][0]["id"]
    body = {
        "job_id": job_id,
        "target_id": target,
        "action": "correct",
        "expected_revision": 0,
        "reason": "Manual check",
        "correction": {"name": "Corrected"},
    }
    response = client.post(
        "/api/v1/review-events", json=body, headers={"Idempotency-Key": "correct"}
    )
    assert response.status_code == 201
    assert (
        client.post(
            "/api/v1/review-events", json=body, headers={"Idempotency-Key": "stale"}
        ).status_code
        == 409
    )
    after = client.get(f"/api/v1/dossiers/{dossier}/results").json()
    assert before["machine"] == after["machine"]
    assert not after["review"]["stale"] and after["review"]["blocked"]
    assert after["effective"]["facts"][0]["normalized"] == {"name": "Corrected"}


def test_lease_fencing_and_attempt_history(system):
    client, factory, config = system
    config.max_attempts = 3
    _, _ = create_job(client)
    with factory.begin() as db:
        task = claim(db, config)
        task_id, old_token = task.id, task.lease_token
        task.lease_until = time.time() - 1
    with factory.begin() as db:
        newer = claim(db, config)
        assert newer.lease_token != old_token
        assert db.get(Attempt, old_token).error_code == "LEASE_EXPIRED"
    import pytest

    from app.domain import DomainError

    with pytest.raises(DomainError, match="LEASE_LOST"), factory.begin() as db:
        finish(db, task_id, old_token, {"bad": "stale output"})


def test_failed_page_retry_reuses_checkpoint(system):
    client, factory, config = system
    dossier, original = create_job(client, pages=2)
    from app.document_processing import process_page

    def fail_second(payload, cfg, store):
        if payload["page_number"] == 2:
            raise RuntimeError("sensitive raw document text")
        return process_page(payload, cfg, store)

    while run_once(factory, config, fail_second):
        pass
    result = client.get(f"/api/v1/dossiers/{dossier}/results").json()
    assert result["machine"]["is_partial"]
    assert "sensitive" not in str(result)
    response = client.post(f"/api/v1/jobs/{original}/retry", headers={"Idempotency-Key": "retry"})
    assert response.status_code == 202, response.text
    assert response.json()["reused_pages"] == 1
    new_id = response.json()["id"]
    drain(factory, config)
    assert client.get(f"/api/v1/jobs/{new_id}").json()["attempts"] == 1
    assert (
        client.get(f"/api/v1/dossiers/{dossier}/results").json()["machine"]["is_partial"] is False
    )
    with factory() as db:
        assert db.scalar(select(Snapshot).where(Snapshot.job_id == original)).result["is_partial"]


def test_structured_comparison_match_difference_and_amendment(system):
    client, factory, config = system
    dossier = client.post(
        "/api/v1/dossiers", json={"title": "Structured comparison"},
        headers={"Idempotency-Key": "sc-create"},
    ).json()["id"]
    contract_text = (
        "Article 1. Term\nwithin 30 days\n"
        "Article 2. Effective Date\n01/01/2025\n"
        "Article 3. Penalty\n10.000.000 VND"
    )
    annex_text = (
        "Article 1. Term\nwithin 30 days\n"
        "Article 2. Effective Date\n01/02/2025\n"
        "Article 3 (amended). Penalty\n15.000.000 VND"
    )
    for text, role, key in ((contract_text, "contract", "sc-contract"), (annex_text, "appendix", "sc-annex")):
        response = client.post(
            f"/api/v1/dossiers/{dossier}/documents",
            files={"file": ("doc.pdf", pdf_bytes(text), "application/pdf")},
            data={"role": role},
            headers={"Idempotency-Key": key},
        )
        assert response.status_code == 201, response.text
    assert client.post(
        f"/api/v1/dossiers/{dossier}/jobs", headers={"Idempotency-Key": "sc-start"}
    ).status_code == 202
    drain(factory, config)
    findings = client.get(f"/api/v1/dossiers/{dossier}/results").json()["machine"]["findings"]
    assert len(findings) == 3
    by_topic = {f["topic"]: f for f in findings}
    assert by_topic["duration_days"]["disposition"] == "comparable_match"
    assert by_topic["duration_days"]["values_equal"] is True
    assert by_topic["date"]["disposition"] == "comparable_difference"
    assert by_topic["date"]["values_equal"] is False
    assert by_topic["amount"]["disposition"] == "candidate_amendment"
    assert by_topic["amount"]["values_equal"] is False
    assert all(f["rule_version"] == "local-v2" for f in findings)


def test_annex_findings_have_two_sources_and_abstain(system):
    client, factory, config = system
    dossier, _ = create_job(client, annex=True)
    drain(factory, config)
    result = client.get(f"/api/v1/dossiers/{dossier}/results").json()
    finding = result["machine"]["findings"][0]
    assert finding["disposition"] == "insufficient_evidence"
    assert finding["citations_a"] and finding["citations_b"]
    assert any(t.startswith("relation:") for t in result["review"]["unresolved"])


def test_artifact_paths_are_server_owned(tmp_path):
    import pytest

    store = ArtifactStore(tmp_path)
    with pytest.raises(ValueError):
        store.path("../../secret.pdf")
    assert store.put(b"synthetic", "json") == store.put(b"synthetic", "json")


def test_batch_totals(system):
    client, factory, _ = system
    ids = []
    for i in range(2):
        dossier = client.post(
            "/api/v1/dossiers",
            json={"title": f"Batch {i}"},
            headers={"Idempotency-Key": f"create-{i}"},
        ).json()["id"]
        client.post(
            f"/api/v1/dossiers/{dossier}/documents",
            files={"file": ("synthetic.pdf", pdf_bytes(), "application/pdf")},
            data={"role": "contract"},
            headers={"Idempotency-Key": f"upload-{i}"},
        )
        ids.append(dossier)
    response = client.post(
        "/api/v1/batches", json={"dossier_ids": ids}, headers={"Idempotency-Key": "batch"}
    )
    assert response.status_code == 202
    summary = client.get(f"/api/v1/batches/{response.json()['id']}").json()
    assert summary["total"] == sum(summary["categories"].values()) == 2
    assert summary["categories"]["Queued"] == 2
