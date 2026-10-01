"""A1: every /jobs/idp result carries the digest that /query binds to."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.transport.kafka_idp_worker as kafka_worker
from app.api import main
from app.contracts.wire import validate_processing_result
from app.pipeline.ai1_snapshot_adapter import adapt_be_ai2_processing_request
from app.security.service_envelope import build_service_envelope

SECRET = "test-secret"
TENANT = "tenant_a"
ACTOR = "backend"
EXAMPLES = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "examples"


def _sha256(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _body_only_request() -> dict:
    body = json.loads((EXAMPLES / "ai1.snapshot.v1.body.example.json").read_text(encoding="utf-8"))
    request_id = f"req-a1-{uuid4().hex[:12]}"
    payload = {
        "schema_version": "be.ai2.processing.request.v1",
        "request_id": request_id,
        "idempotency_key": f"{body['dossier_id']}:{request_id}",
        "attempt": 1,
        "task_id": "process-dossier",
        "dossier_id": body["dossier_id"],
        "snapshots": [body],
        "snapshot_identities": [
            {
                "snapshot_id": body["snapshot_id"],
                "snapshot_version": "ai1.snapshot.v1",
                "source_digest": body["source_digest"],
                "snapshot_digest": _sha256(body),
            }
        ],
        "dossier_members": [
            {
                "member_id": "member-body-001",
                "document_id": body["document_id"],
                "snapshot_id": body["snapshot_id"],
                "role": "body",
                "source_digest": body["source_digest"],
            }
        ],
        "role_relation_map": [],
        "policy_flags": {
            "egress_allowed": False,
            "use_vector": False,
            "budget_limits": {
                "max_processing_seconds": 300,
                "max_llm_calls": 0,
                "max_embedding_tokens": 0,
            },
        },
    }
    payload["service_envelope"] = build_service_envelope(
        payload, secret=SECRET, tenant_id=TENANT, dossier_id=payload["dossier_id"], actor_id=ACTOR
    )
    return payload


def _expected_digest(payload: dict) -> str:
    _request, adapted = adapt_be_ai2_processing_request(payload, tenant_id=TENANT, actor_id=ACTOR)
    return adapted.record.pins.source_snapshot_digest


@pytest.fixture(autouse=True)
def _isolated_api_state(monkeypatch):
    monkeypatch.setenv("AI2_SERVICE_HMAC_SECRET", SECRET)
    main.WIRE_JOBS.clear()
    main.WIRE_IDEMPOTENCY.clear()
    main.STORE._dossiers.clear()
    kafka_worker._processed.clear()
    yield
    kafka_worker._processed.clear()


def _poll(client: TestClient, job_id: str, dossier_id: str) -> dict:
    poll = {"operation": "get_job", "job_id": job_id, "dossier_id": dossier_id}
    envelope = build_service_envelope(
        poll, secret=SECRET, tenant_id=TENANT, dossier_id=dossier_id, actor_id=ACTOR
    )
    response = client.get(f"/jobs/{job_id}", headers={"X-AI2-Service-Envelope": json.dumps(envelope)})
    assert response.status_code == 200, response.text
    return response.json()


def test_queued_result_carries_query_snapshot_digest(monkeypatch):
    monkeypatch.setattr(main, "_run_wire_job", lambda *_args, **_kwargs: None)
    payload = _body_only_request()

    response = TestClient(main.app).post("/jobs/idp", json=payload)

    assert response.status_code == 202, response.text
    wire = response.json()
    assert wire["status"] == "QUEUED"
    assert wire["query_snapshot_digest"] == _expected_digest(payload)
    validate_processing_result(wire)


def test_succeeded_result_digest_is_the_one_query_binds_to():
    payload = _body_only_request()
    client = TestClient(main.app)

    accepted = client.post("/jobs/idp", json=payload)
    assert accepted.status_code == 202, accepted.text
    wire = _poll(client, accepted.json()["job_id"], payload["dossier_id"])

    assert wire["status"] == "SUCCEEDED", wire["errors"]
    digest = wire["query_snapshot_digest"]
    assert digest == _expected_digest(payload)
    validate_processing_result(wire)

    query = {
        "query": "Giá trị hợp đồng là bao nhiêu?",
        "dossier_id": payload["dossier_id"],
        "snapshot_digest": digest,
        "snapshot_version": "ai1.snapshot.v1",
        "query_contract_version": "ai2.query.v1",
    }
    query["service_envelope"] = build_service_envelope(
        query,
        secret=SECRET,
        tenant_id=TENANT,
        dossier_id=payload["dossier_id"],
        actor_id=ACTOR,
        scopes=["ai2.query"],
    )
    answered = client.post("/query", json=query)

    assert answered.status_code == 200, answered.text
    body = answered.json()
    codes = [step.get("code") for step in body["reasoning_trace"] if isinstance(step, dict)]
    assert "AI2_QUERY_EVIDENCE_CONTEXT_REQUIRED" not in codes
    assert body["retrieval_layer"]["snapshot_digest"] == digest


def test_kafka_result_carries_query_snapshot_digest():
    payload = _body_only_request()
    command = {
        "schema_version": kafka_worker.SCHEMA_VERSION,
        "event_id": f"evt-{uuid4().hex}",
        "event_type": kafka_worker.EVENT_COMMAND,
        "trace_id": "trace-a1",
        "tenant_id": TENANT,
        "correlation": {"dossier_id": payload["dossier_id"]},
        "payload": payload,
    }

    envelope = kafka_worker._handle_command(command)

    wire = envelope["payload"]
    assert envelope["event_type"] == kafka_worker.EVENT_COMPLETED, wire["errors"]
    assert wire["query_snapshot_digest"] == _expected_digest(payload)
    validate_processing_result(wire)


def test_result_schema_rejects_malformed_query_snapshot_digest(monkeypatch):
    monkeypatch.setattr(main, "_run_wire_job", lambda *_args, **_kwargs: None)
    wire = TestClient(main.app).post("/jobs/idp", json=_body_only_request()).json()

    wire["query_snapshot_digest"] = "sha256:" + "a" * 64
    with pytest.raises(Exception) as exc_info:
        validate_processing_result(wire)
    assert getattr(exc_info.value, "code", "") == "RESULT_SCHEMA_INVALID"
