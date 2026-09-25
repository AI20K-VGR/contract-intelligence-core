from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import main
from app.api.main import app
from app.security.service_envelope import build_service_envelope
from fixtures import mock_record


def _signed_query(payload: dict) -> dict:
    wire = dict(payload)
    wire["service_envelope"] = build_service_envelope(
        wire,
        secret="test-secret",
        tenant_id="tenant_a",
        dossier_id="dossier_001",
        actor_id="user_001",
        scopes=["ai2.query"],
    )
    return wire


def test_metadata_only_query_fails_closed_before_retrieval(monkeypatch) -> None:
    monkeypatch.setenv("AI2_SERVICE_HMAC_SECRET", "test-secret")
    main.STORE._dossiers.clear()
    main.STORE.put(mock_record())

    response = TestClient(app).post(
        "/api/v1/query",
        json=_signed_query(
            {
                "query": "contract value",
                "dossier_id": "dossier_001",
                "snapshot_version": "ai1.snapshot.v1",
                "query_contract_version": "ai2.query.v1",
                "acl_context": "reviewer",
                "policy_flags": {"egress_allowed": False},
            }
        ),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "INSUFFICIENT_EVIDENCE"
    assert body["citations"] == []
    assert body["reasoning_trace"][0]["code"] == "AI2_QUERY_EVIDENCE_CONTEXT_REQUIRED"


def test_query_rejects_stale_snapshot_digest_before_reasoning(monkeypatch) -> None:
    monkeypatch.setenv("AI2_SERVICE_HMAC_SECRET", "test-secret")
    main.STORE._dossiers.clear()
    main.STORE.put(mock_record())

    response = TestClient(app).post(
        "/api/v1/query",
        json=_signed_query(
            {
                "query": "contract value",
                "dossier_id": "dossier_001",
                "snapshot_version": "ai1.snapshot.v1",
                "snapshot_digest": "sha256:stale",
                "query_contract_version": "ai2.query.v1",
                "acl_context": "reviewer",
                "policy_flags": {"egress_allowed": False},
            }
        ),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "INSUFFICIENT_EVIDENCE"
    assert body["citations"] == []
    assert body["reasoning_trace"][0]["code"] == "AI2_QUERY_EVIDENCE_CONTEXT_REQUIRED"
