from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.api.main as main
import app.tools.query_store as query_store
from app.contracts.models import (
    AuthContext,
    LifecycleState,
    TenantProfile,
    ToolEnvelope,
    VersionPins,
)
from app.reasoning.l2_plan import _answer_language_instruction
from app.reasoning.query import classify_ask
from app.tools.store import DossierRecord

client = TestClient(main.app)


def test_money_question_routes_to_raw_fact_check() -> None:
    task = classify_ask("Phí tuyển dụng có phải 20 triệu không?")

    assert task["type"] == "raw_fact_check"
    assert task["fact_intent"] == "money"


def test_llm_answer_language_follows_vietnamese_query() -> None:
    instruction = _answer_language_instruction("Phí tuyển dụng có phải 20 triệu không?")

    assert "Answer in Vietnamese" in instruction
    assert "numeric values" in instruction


def test_llm_answer_language_follows_non_vietnamese_query() -> None:
    instruction = _answer_language_instruction("What is the contract value?")

    assert instruction == "Answer in the same language as the query."


def test_query_snapshot_round_trip_preserves_scope_and_citations(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(query_store, "DATA", tmp_path)
    monkeypatch.setattr(query_store, "DB", tmp_path / "query.sqlite")
    pins = VersionPins(
        manifest_version=1,
        source_snapshot_digest="a" * 64,
        tenant_profile_version=1,
        policy_version=1,
        ocr_run_version=1,
        reconstruction_version=1,
        extraction_version=1,
    )
    record = DossierRecord(
        tenant_id="tenant-1",
        dossier_id="dos-1",
        lifecycle=LifecycleState.ACTIVE,
        pins=pins,
        pages=[],
        nodes=[],
        tables=[],
        profile=TenantProfile(version=1),
        acl_revision=1,
        permissions_by_actor={"backend": ["QUERY"]},
    )
    envelope = ToolEnvelope(
        auth=AuthContext(
            actor_id="backend",
            tenant_id="tenant-1",
            dossier_id="dos-1",
            acl_revision=1,
            permissions=["QUERY"],
        ),
        pins=pins,
    )

    query_store.save_query_snapshot(record, envelope)
    loaded = query_store.load_query_snapshot("dos-1", tenant_id="tenant-1")

    assert loaded is not None
    loaded_record, loaded_envelope = loaded
    assert loaded_record.dossier_id == "dos-1"
    assert loaded_envelope.auth.tenant_id == "tenant-1"


def test_query_without_persisted_snapshot_fails_closed() -> None:
    response = client.post(
        "/query",
        json={
            "query": "Phí tuyển dụng có phải 20 triệu không?",
            "dossier_id": "dos-missing",
            "snapshot_version": "latest",
            "policy_flags": {"egress_allowed": True, "use_llm": True},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "INSUFFICIENT_EVIDENCE"
    assert body["citations"] == []
    assert body["reasoning_trace"][0]["code"] == "AI2_QUERY_SNAPSHOT_NOT_FOUND"


def test_query_enables_llm_only_after_policy_and_evidence(monkeypatch) -> None:
    record = SimpleNamespace(tenant_id="tenant-1", dossier_id="dos-1", egress_approved=False)
    seen: dict[str, object] = {}

    monkeypatch.setattr(main, "load_query_snapshot", lambda dossier_id, tenant_id=None: (record, object()))

    class ConfiguredLLM:
        def configured(self) -> bool:
            return True

    monkeypatch.setattr(main, "NineRouterClient", ConfiguredLLM)

    def fake_reason(record_arg, envelope, task, *, use_llm, use_vector):
        seen["use_llm"] = use_llm
        seen["task_use_llm"] = task["use_llm"]
        return {
            "review_state": "ANSWERED",
            "answer": "Có evidence",
            "citations": [{"node_id": "n1", "text_span": "20 triệu"}],
            "layers_used": ["L0", "L1", "L2", "L3"],
            "steps": [],
            "used_llm": True,
        }

    monkeypatch.setattr(main, "_reason_output", fake_reason)
    response = client.post(
        "/query",
        json={
            "query": "Phí tuyển dụng có phải 20 triệu không?",
            "dossier_id": "dos-1",
            "snapshot_version": "latest",
            "policy_flags": {"egress_allowed": True, "use_llm": True},
        },
    )

    assert response.status_code == 200
    assert seen == {"use_llm": True, "task_use_llm": True}
    assert response.json()["retrieval_layer"]["used_llm"] is True


def test_query_provider_failure_falls_back_to_grounded_retrieval(monkeypatch) -> None:
    record = SimpleNamespace(tenant_id="tenant-1", dossier_id="dos-1", egress_approved=False)
    monkeypatch.setattr(main, "load_query_snapshot", lambda dossier_id, tenant_id=None: (record, object()))

    class ConfiguredLLM:
        def configured(self) -> bool:
            return True

    monkeypatch.setattr(main, "NineRouterClient", ConfiguredLLM)
    calls: list[bool] = []

    def fake_reason(record_arg, envelope, task, *, use_llm, use_vector):
        calls.append(use_llm)
        if use_llm:
            raise RuntimeError("provider rejected credential")
        return {
            "review_state": "NEEDS_REVIEW",
            "answer": "Evidence raw",
            "citations": [{"node_id": "n1", "text_span": "20 triệu"}],
            "layers_used": ["L0", "L1", "L3"],
            "steps": [],
            "used_llm": False,
        }

    monkeypatch.setattr(main, "_reason_output", fake_reason)
    response = client.post(
        "/query",
        json={
            "query": "Phí tuyển dụng có phải 20 triệu không?",
            "dossier_id": "dos-1",
            "policy_flags": {"egress_allowed": True, "use_llm": True},
        },
    )

    assert response.status_code == 200
    assert calls == [True, False]
    assert response.json()["state"] == "NEEDS_REVIEW"
    assert response.json()["reasoning_trace"][-1]["code"] == "AI2_LLM_UNAVAILABLE"
