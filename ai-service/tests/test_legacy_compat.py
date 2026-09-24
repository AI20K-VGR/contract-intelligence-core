from fastapi.testclient import TestClient

from app.api.main import app


client = TestClient(app)


def test_backend_process_contract_fails_closed_without_snapshot_content() -> None:
    response = client.post(
        "/process",
        json={
            "snapshot_id": "snap-1",
            "snapshot_version": "v1",
            "digest": "sha256:test",
            "dossier_members": [],
            "role_relation_map": {},
            "policy_flags": {"egress_allowed": False, "use_vector": False},
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert body["state"] == "INSUFFICIENT_EVIDENCE"
    assert body["facts"] == []
    assert body["evidence_gaps"][0]["code"] == "AI2_SNAPSHOT_CONTENT_REQUIRED"


def test_backend_query_contract_fails_closed_without_citations() -> None:
    response = client.post(
        "/query",
        json={
            "query": "Mức phí là bao nhiêu?",
            "dossier_id": "dossier-1",
            "snapshot_version": "latest",
            "acl_context": "operator",
            "policy_flags": {"egress_allowed": False},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "INSUFFICIENT_EVIDENCE"
    assert body["citations"] == []


def test_legacy_extract_returns_explicit_evidence_gap() -> None:
    response = client.post("/api/v1/jobs/extract", json={"document_id": "doc-1"})

    assert response.status_code == 202
    job = client.get(f"/api/v1/jobs/{response.json()['job_id']}")
    assert job.status_code == 200
    assert job.json()["result"]["facts"] == []
    assert job.json()["result"]["evidence_gaps"][0]["severity"] == "high"
