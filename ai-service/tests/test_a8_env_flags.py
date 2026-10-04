"""A8: server-side env flags decide egress/LLM/vector; /query LLM is capped."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.transport.kafka_idp_worker as kafka_worker
from app.api import main
from app.contracts.schema_validation import validate_contract
from app.llm.client import query_llm_timeout_seconds
from app.pipeline.ai1_snapshot_adapter import adapt_be_ai2_processing_request
from app.reasoning.l2_plan import L2Planner
from app.security.service_envelope import build_service_envelope
from fixtures import envelope as fixture_envelope
from fixtures import mock_record

SECRET = "test-secret"
TENANT = "tenant_a"
EXAMPLES = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "examples"
ENV_FLAGS = (
    "AI2_PROCESSING_EGRESS_ALLOWED",
    "AI2_QUERY_EGRESS_ALLOWED",
    "AI2_QUERY_USE_LLM",
    "AI2_QUERY_USE_VECTOR",
    "AI2_QUERY_LLM_TIMEOUT_SECONDS",
)


class FakeLLM:
    """Configured provider double; ``block`` makes every call hang."""

    instances: list["FakeLLM"] = []
    release = threading.Event()
    block = False

    def __init__(self, *_args: Any, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.calls = 0
        self.traces: list[dict[str, Any]] = []
        self.model = "fake"
        FakeLLM.instances.append(self)

    def configured(self) -> bool:
        return True

    def complete_json(self, system: str, user: str, **_kwargs: Any) -> dict[str, Any]:
        self.calls += 1
        if FakeLLM.block:
            FakeLLM.release.wait(20)
        return {
            "answer": "model answer",
            "citations": [{"node_id": "clause_5_3", "text_span": "payment"}],
            "sufficient": False,
        }


def _llm_calls() -> int:
    return sum(item.calls for item in FakeLLM.instances)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in ENV_FLAGS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AI2_SERVICE_HMAC_SECRET", SECRET)
    FakeLLM.instances = []
    FakeLLM.block = False
    FakeLLM.release = threading.Event()
    main.WIRE_JOBS.clear()
    main.WIRE_IDEMPOTENCY.clear()
    main.STORE._dossiers.clear()
    kafka_worker._processed.clear()
    yield
    FakeLLM.release.set()
    kafka_worker._processed.clear()
    main.STORE._dossiers.clear()


def _sha256(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _processing_request(policy_flags: dict[str, Any]) -> dict:
    body = json.loads((EXAMPLES / "ai1.snapshot.v1.body.example.json").read_text(encoding="utf-8"))
    request_id = f"req-a8-{uuid4().hex[:12]}"
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
            **policy_flags,
            "budget_limits": {
                "max_processing_seconds": 300,
                "max_llm_calls": 5,
                "max_embedding_tokens": 0,
            },
        },
    }
    payload["service_envelope"] = build_service_envelope(
        payload, secret=SECRET, tenant_id=TENANT, dossier_id=payload["dossier_id"], actor_id="backend"
    )
    return payload


def _poll(client: TestClient, job_id: str, dossier_id: str) -> dict:
    poll = {"operation": "get_job", "job_id": job_id, "dossier_id": dossier_id}
    envelope = build_service_envelope(
        poll, secret=SECRET, tenant_id=TENANT, dossier_id=dossier_id, actor_id="backend"
    )
    response = client.get(f"/jobs/{job_id}", headers={"X-AI2-Service-Envelope": json.dumps(envelope)})
    assert response.status_code == 200, response.text
    return response.json()


def _spy_run_idp(monkeypatch, module: Any) -> dict[str, Any]:
    captured: dict[str, Any] = {}
    real = module.run_idp

    def spy(record: Any, envelope: Any, **kwargs: Any) -> Any:
        captured.update(kwargs, egress_approved=record.egress_approved)
        return real(record, envelope, **kwargs)

    monkeypatch.setattr(module, "run_idp", spy)
    monkeypatch.setattr(module, "NineRouterClient", FakeLLM)
    return captured


# --- processing: AI2_PROCESSING_EGRESS_ALLOWED ------------------------------


@pytest.mark.parametrize(
    ("env_value", "request_egress", "expected"),
    [(None, True, False), ("false", True, False), ("true", False, True)],
)
def test_processing_egress_comes_from_env_not_request(
    monkeypatch, env_value: str | None, request_egress: bool, expected: bool
):
    if env_value is not None:
        monkeypatch.setenv("AI2_PROCESSING_EGRESS_ALLOWED", env_value)
    captured = _spy_run_idp(monkeypatch, main)
    payload = _processing_request({"egress_allowed": request_egress, "use_vector": False})
    client = TestClient(main.app)

    accepted = client.post("/jobs/idp", json=payload)
    assert accepted.status_code == 202, accepted.text
    _poll(client, accepted.json()["job_id"], payload["dossier_id"])

    assert captured["runtime"].egress_allowed is expected
    assert captured["egress_approved"] is expected
    assert (captured["llm"] is not None) is expected


def test_kafka_processing_ignores_request_egress_when_env_is_off(monkeypatch):
    captured = _spy_run_idp(monkeypatch, kafka_worker)
    payload = _processing_request({"egress_allowed": True, "use_vector": False})
    command = {
        "event_id": f"evt-{uuid4().hex}",
        "event_type": kafka_worker.EVENT_COMMAND,
        "tenant_id": TENANT,
        "payload": payload,
    }

    kafka_worker._handle_command(command)

    assert captured["llm"] is None
    assert captured["runtime"].egress_allowed is False
    assert captured["egress_approved"] is False
    assert _llm_calls() == 0


def test_request_without_egress_and_vector_flags_is_valid():
    payload = _processing_request({})
    assert "egress_allowed" not in payload["policy_flags"]
    assert "use_vector" not in payload["policy_flags"]

    validate_contract(
        payload, "be.ai2.processing.request.v1.schema.json", error_code="PROCESSING_REQUEST_SCHEMA_INVALID"
    )
    request, adapted = adapt_be_ai2_processing_request(payload, tenant_id=TENANT, actor_id="backend")
    assert adapted.record.egress_approved is False
    assert request.policy_flags.use_vector is False

    client = TestClient(main.app)
    accepted = client.post("/jobs/idp", json=payload)
    assert accepted.status_code == 202, accepted.text
    wire = _poll(client, accepted.json()["job_id"], payload["dossier_id"])
    assert wire["status"] == "SUCCEEDED", wire["errors"]


# --- /query: AI2_QUERY_* -----------------------------------------------------


def _compare_record():
    record = mock_record()
    record.nodes.append(
        record.nodes[0].model_copy(
            update={
                "node_id": "annex_1",
                "raw_label": "Phụ lục 1",
                "order": 8,
                "text": "Phụ lục 1 liên quan đến điều khoản thanh toán.",
                "structured_key": None,
                "structured_value": None,
            }
        )
    )
    return record


def _signed_query(policy_flags: dict[str, Any] | None = None) -> dict:
    payload: dict[str, Any] = {
        "query": "Điều 5 liên quan đến phụ lục 1?",
        "dossier_id": "dossier_001",
        "snapshot_version": "ai1.snapshot.v1",
    }
    if policy_flags is not None:
        payload["policy_flags"] = policy_flags
    payload["service_envelope"] = build_service_envelope(
        payload,
        secret=SECRET,
        tenant_id=TENANT,
        dossier_id="dossier_001",
        actor_id="user_001",
        scopes=["ai2.query"],
    )
    return payload


def test_query_ignores_request_egress_when_env_is_off(monkeypatch):
    monkeypatch.setattr(main, "NineRouterClient", FakeLLM)
    main.STORE.put(_compare_record())

    response = TestClient(main.app).post(
        "/query", json=_signed_query({"egress_allowed": True, "use_llm": True, "use_vector": False})
    )

    assert response.status_code == 200, response.text
    assert _llm_calls() == 0
    assert response.json()["used_llm"] is False


def test_query_uses_llm_only_when_env_allows_it(monkeypatch):
    monkeypatch.setenv("AI2_QUERY_EGRESS_ALLOWED", "true")
    monkeypatch.setenv("AI2_QUERY_USE_LLM", "true")
    monkeypatch.setattr(main, "NineRouterClient", FakeLLM)
    main.STORE.put(_compare_record())

    response = TestClient(main.app).post("/query", json=_signed_query())

    assert response.status_code == 200, response.text
    assert _llm_calls() == 1
    assert response.json()["used_llm"] is True


@pytest.mark.parametrize(("env_value", "expected"), [(None, False), ("true", True)])
def test_query_vector_comes_from_env(monkeypatch, env_value: str | None, expected: bool):
    if env_value is not None:
        monkeypatch.setenv("AI2_QUERY_USE_VECTOR", env_value)
    requested: list[bool] = []
    real = main._vector_service

    def spy(use_vector: bool, runtime: Any = None) -> Any:
        requested.append(use_vector)
        return real(use_vector, runtime)

    monkeypatch.setattr(main, "_vector_service", spy)
    main.STORE.put(_compare_record())

    response = TestClient(main.app).post(
        "/query", json=_signed_query({"use_vector": not expected, "use_llm": False})
    )

    assert response.status_code == 200, response.text
    assert requested == [expected]


@pytest.mark.parametrize(
    ("env_value", "expected"),
    [(None, 15.0), ("30", 15.0), ("15", 15.0), ("2.5", 2.5), ("0", 15.0), ("-1", 15.0), ("abc", 15.0)],
)
def test_query_llm_timeout_is_min_of_15s_and_env(monkeypatch, env_value: str | None, expected: float):
    if env_value is not None:
        monkeypatch.setenv("AI2_QUERY_LLM_TIMEOUT_SECONDS", env_value)

    assert query_llm_timeout_seconds() == expected


def test_slow_query_llm_returns_retrieval_answer_within_deadline(monkeypatch):
    monkeypatch.setenv("AI2_QUERY_EGRESS_ALLOWED", "true")
    monkeypatch.setenv("AI2_QUERY_USE_LLM", "true")
    monkeypatch.setenv("AI2_QUERY_LLM_TIMEOUT_SECONDS", "0.5")
    monkeypatch.setattr(main, "NineRouterClient", FakeLLM)
    FakeLLM.block = True
    main.STORE.put(_compare_record())

    started = time.monotonic()
    response = TestClient(main.app).post("/query", json=_signed_query())
    elapsed = time.monotonic() - started
    FakeLLM.release.set()

    assert response.status_code == 200, response.text
    assert elapsed < 0.5 + 3.0, elapsed
    body = response.json()
    assert _llm_calls() == 1
    assert body["citations"]
    # The result falls back to retrieval, but the provider call was actually
    # attempted and must be reflected in telemetry.
    assert body["used_llm"] is True
    assert body["state"] != "BLOCKED"
    assert FakeLLM.instances[0].kwargs.get("timeout") == 0.5


def test_l2_replan_failure_falls_back_to_retrieval():
    class SlowLLM:
        def configured(self) -> bool:
            return True

        def complete_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            raise TimeoutError("query LLM deadline exceeded")

    class FlakyGateway:
        def __init__(self) -> None:
            self.calls = 0

        def call(self, name: str, _envelope: Any, **kwargs: Any) -> dict[str, Any]:
            self.calls += 1
            if self.calls == 1:
                raise TypeError("bad tool args")
            return {
                "node_id": kwargs.get("node_id"),
                "raw_label": "Điều 5",
                "text": "Thanh toán trong 15 ngày.",
                "citation": {"node_id": kwargs.get("node_id"), "text_span": "Thanh toán"},
            }

    result = L2Planner(FlakyGateway(), SlowLLM()).run(
        fixture_envelope(),
        {"type": "compare", "query": "Điều 5 liên quan đến phụ lục 1?"},
        {"hits": [{"node_id": "clause_5_3"}]},
    )

    assert result["fallback"] is True
    assert result["draft"]["citations"]
