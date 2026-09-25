from fastapi.testclient import TestClient

from app.api import main
from app.api.main import app
from app.security.service_envelope import build_service_envelope
from fixtures import mock_record


def test_legacy_extract_returns_explicit_evidence_gap_without_fabricating_fact() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/jobs/extract",
        headers={"X-Tenant-Id": "tenant-a"},
        json={
            "task_id": 1,
            "attempt_id": 1,
            "tenant_id": "tenant-a",
            "document_id": "doc-a",
            "snapshot_digest": "digest",
            "document_text_nfc": "Giá trị hợp đồng 100 triệu",
        },
    )
    assert response.status_code == 202
    job_id = response.json()["job_id"]

    report = client.get(f"/api/v1/jobs/{job_id}")
    assert report.status_code == 200
    body = report.json()
    assert body["status"] == "completed"
    assert body["result"]["facts"] == []
    assert body["result"]["evidence_gaps"][0]["suggested_profile"] == "ai1.snapshot.v1"


def test_legacy_compare_fails_closed_without_citations() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/jobs/compare",
        json={
            "task_id": 2,
            "attempt_id": 1,
            "tenant_id": "tenant-a",
            "dossier_id": "dossier-a",
            "contract_document": {"document_id": "doc-a", "facts": []},
            "annex_documents": [],
        },
    )
    assert response.status_code == 202
    report = client.get(f"/api/v1/jobs/{response.json()['job_id']}")
    assert report.json()["status"] == "failed"
    assert report.json()["error"]["code"] == "INSUFFICIENT_EVIDENCE"


def test_legacy_ocr_is_not_implemented_by_ai2() -> None:
    client = TestClient(app)
    response = client.post("/api/v1/jobs/ocr", json={})
    assert response.status_code == 501
    assert response.json()["detail"]["code"] == "AI2_OCR_NOT_SUPPORTED"


def test_backend_process_routes_accept_current_handoff_contract() -> None:
    client = TestClient(app)
    payload = {
        "snapshot_id": "snapshot-1",
        "snapshot_version": "ai1.snapshot.v1",
        "digest": "sha256:abc",
        "dossier_members": [],
        "role_relation_map": {},
        "policy_flags": {"egress_allowed": False},
    }

    for path in ("/process", "/api/v1/process"):
        response = client.post(path, json=payload)
        assert response.status_code == 202
        body = response.json()
        assert body["state"] == "INSUFFICIENT_EVIDENCE"
        assert body["snapshot_id"] == "snapshot-1"
        assert body["evidence_gaps"][0]["code"] == "AI2_SNAPSHOT_CONTENT_REQUIRED"


def test_backend_query_routes_fail_closed_without_snapshot_evidence() -> None:
    client = TestClient(app)
    payload = {
        "query": "Giá trị hợp đồng là bao nhiêu?",
        "dossier_id": "dossier-1",
        "snapshot_version": "ai1.snapshot.v1",
        "acl_context": "reviewer",
        "policy_flags": {"egress_allowed": False},
    }

    for path in ("/query", "/api/v1/query"):
        response = client.post(path, json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body["state"] == "INSUFFICIENT_EVIDENCE"
        assert body["citations"] == []


def test_backend_query_reads_authoritative_canonical_record(monkeypatch) -> None:
    monkeypatch.setenv("AI2_SERVICE_HMAC_SECRET", "test-secret")
    main.STORE._dossiers.clear()
    main.STORE.put(mock_record())

    query = {
        "query": "contract value",
        "dossier_id": "dossier_001",
        "snapshot_version": "ai1.snapshot.v1",
        "acl_context": "reviewer",
        "policy_flags": {"egress_allowed": False, "use_vector": False},
    }
    query["service_envelope"] = build_service_envelope(
        query,
        secret="test-secret",
        tenant_id="tenant_a",
        dossier_id="dossier_001",
        actor_id="user_001",
        scopes=["ai2.query"],
    )

    response = TestClient(app).post("/api/v1/query", json=query)

    assert response.status_code == 200
    body = response.json()
    assert body["state"] != "INSUFFICIENT_EVIDENCE"
    assert body["citations"]
