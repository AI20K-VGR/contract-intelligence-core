import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.pipeline.runtime import ProcessingRuntime
from fixtures import envelope as fixture_envelope, mock_record


def test_hydrate_store_restores_successful_job_after_restart(monkeypatch):
    from app.api import main

    record = mock_record()
    record.dossier_id = "dossier-hydration-test"

    class SuccessfulJobs:
        def list_succeeded(self):
            return [
                {
                    "job_id": "job-hydration-test",
                    "tenant_id": record.tenant_id,
                    "dossier_id": record.dossier_id,
                    "request": {"dossier_id": record.dossier_id},
                }
            ]

    monkeypatch.setattr(main, "JOB_STORE", SuccessfulJobs())
    monkeypatch.setattr(
        main,
        "adapt_be_ai2_processing_request",
        lambda *_args, **_kwargs: (None, SimpleNamespace(record=record)),
    )

    main.STORE._dossiers.pop((record.tenant_id, record.dossier_id), None)
    assert main._hydrate_store_from_jobs() == 1
    assert main.STORE.get(record.tenant_id, record.dossier_id) is record


def _ai1_snapshot():
    root = Path(__file__).resolve().parents[2]
    return json.loads(
        (root / "docs" / "contracts" / "examples" / "ai1.snapshot.v1.body.example.json")
        .read_text(encoding="utf-8")
    )


def test_case_query_route_uses_existing_query_contract():
    client = TestClient(app)
    response = client.post(
        "/api/cases/HD-TONG-HOP/query",
        json={"query": "Điều 9 nói gì?", "use_llm": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["case_id"] == "HD-TONG-HOP"
    assert body["review_state"] in {"ANSWERED", "NEEDS_REVIEW", "INSUFFICIENT_EVIDENCE"}


def test_review_rejects_unknown_candidate_and_publish_stays_proposal():
    client = TestClient(app)
    session = client.post("/api/workspace/sample-compare")
    assert session.status_code == 200
    payload = session.json()
    sid = payload["session_id"]

    review = client.post(
        f"/api/workspace/{sid}/review",
        json={"candidate_id": "does-not-exist", "action": "confirm"},
    )
    assert review.status_code == 404

    published = client.post(f"/api/workspace/{sid}/publish", json={"confirm": True})
    assert published.status_code == 200
    assert published.json()["contribution"]["publish"] == "propose"


def test_review_stales_only_after_processing_basis_changes(monkeypatch):
    from app.api import main

    main.SESSIONS.clear()
    view = main.workspace_sample_compare()
    sid = view["session_id"]
    candidate = main.SESSIONS[sid]["job"].contribution.candidates[0]

    main.workspace_review(
        sid,
        main.ReviewBody(candidate_id=candidate.candidate_id, action="confirm"),
    )
    main.workspace_extract(sid, main.RunBody(use_llm=False))
    assert main.SESSIONS[sid]["reviews_stale"] is False

    record = main.SESSIONS[sid]["record"]
    record.pins.extraction_version += 1
    main.SESSIONS[sid]["envelope"].pins.extraction_version = record.pins.extraction_version
    main.workspace_extract(sid, main.RunBody(use_llm=False))
    assert main.SESSIONS[sid]["reviews_stale"] is True
    with pytest.raises(Exception, match="stale"):
        main.workspace_publish(sid, main.PublishBody(confirm=True))


def test_api_vector_path_honors_request_embedding_budget_before_provider(monkeypatch):
    from app.api import main

    class NoCallEmbeddingClient:
        def __init__(self):
            self.calls = 0

        def discover(self, *, egress_approved=True, force=False):
            return type("Capability", (), {
                "status": "READY",
                "selected_model": "embedding-test",
                "dimensions": 2,
            })()

        def embed(self, *args, **kwargs):
            self.calls += 1
            raise AssertionError("embedding provider must not be called after budget denial")

    record = mock_record()
    envelope = fixture_envelope()
    client = NoCallEmbeddingClient()
    monkeypatch.setattr(main, "EMBEDDING_CLIENT", client)
    monkeypatch.setattr(main.VECTOR_RECALL, "enabled", True)
    main.STORE.put(record)

    runtime = ProcessingRuntime(egress_allowed=True, max_embedding_tokens=1)
    result = main._reason_output(
        record,
        envelope,
        {"type": "lookup_term", "query": "zzzzzz-not-in-source"},
        use_llm=False,
        use_vector=True,
        runtime=runtime,
    )

    assert result["retrieval_trace"]["vector_status"] == "BUDGET_EXCEEDED"
    assert client.calls == 0


def test_ai1_snapshot_endpoint_uses_official_handoff_adapter():
    client = TestClient(app)
    response = client.post("/api/workspace/ai1-snapshot", json=_ai1_snapshot())
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "ai1_snapshot"
    assert body["ai1"]["source"] == "ai1.snapshot.v1"
    assert body["n_tables"] == 0
    assert body["pages"][0]["quality"] == "EMPTY"


def test_ai1_snapshot_endpoint_rejects_edge_case_catalog():
    client = TestClient(app)
    response = client.post(
        "/api/workspace/ai1-snapshot",
        json={"schema_version": "ai2.ocr_edge_cases.v1", "cases": []},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "UNSUPPORTED_ARTIFACT_KIND"


def test_ai1_snapshot_endpoint_accepts_legacy_text_only_as_degraded():
    client = TestClient(app)
    response = client.post(
        "/api/workspace/ai1-snapshot",
        json={
            "document_id": "legacy-api-doc",
            "filename": "contract.pdf",
            "page_count": 1,
            "full_text": "Dieu 1\nNoi dung",
            "pages": [
                {
                    "page_number": 1,
                    "status": "SUCCESS",
                    "input_type": "TEXT_LAYER",
                    "text": "Dieu 1\nNoi dung",
                    "geometry_available": True,
                }
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "ai1_snapshot"
    assert body["ai1"]["source"] == "legacy_ocr_json"
    assert body["pages"][0]["quality"] == "LOW"
    assert body["pages"][0]["table_coverage"] == "UNKNOWN"
