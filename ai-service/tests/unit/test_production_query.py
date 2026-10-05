from __future__ import annotations

import pytest
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
from app.tools.store import DossierRecord, InMemorySnapshotStore
from fixtures.catalog import load_case

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


def _unsigned_lane_with_env_policy(monkeypatch, policy_flags: dict) -> None:
    """A4/A8: these cases exercise the unsigned compatibility lane, and /query
    egress/LLM policy now comes from server env instead of the request."""
    monkeypatch.setenv("AI2_QUERY_REQUIRE_SIGNATURE", "false")
    monkeypatch.setenv("AI2_QUERY_EGRESS_ALLOWED", str(bool(policy_flags.get("egress_allowed"))).lower())
    monkeypatch.setenv("AI2_QUERY_USE_LLM", str(bool(policy_flags.get("use_llm"))).lower())


def test_query_without_persisted_snapshot_fails_closed(monkeypatch) -> None:
    _unsigned_lane_with_env_policy(monkeypatch, {"egress_allowed": True, "use_llm": True})
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


def _serve_fixture_dossier(monkeypatch) -> str:
    """Serve one real fixture dossier through the durable query read model."""
    pack = load_case("HD-TONG-HOP")
    monkeypatch.setattr(main, "STORE", InMemorySnapshotStore())
    monkeypatch.setattr(
        main,
        "load_query_snapshot",
        lambda dossier_id, tenant_id=None: (pack.record, pack.envelope),
    )
    return pack.record.dossier_id


def _ask(dossier_id: str, policy_flags: dict, query: str = "Phí tuyển dụng có phải 20 triệu không?") -> dict:
    response = client.post(
        "/query",
        json={
            "query": query,
            "dossier_id": dossier_id,
            "tenant_id": "tenant_a",
            "policy_flags": policy_flags,
        },
    )
    assert response.status_code == 200
    return response.json()


@pytest.mark.parametrize(
    ("policy_flags", "configured", "expect_llm"),
    [
        ({"egress_allowed": True, "use_llm": True}, True, True),
        ({"egress_allowed": False, "use_llm": True}, True, False),
        ({"egress_allowed": True, "use_llm": False}, True, False),
        ({"egress_allowed": True, "use_llm": True}, False, False),
    ],
)
def test_query_enables_llm_only_after_policy_and_evidence(
    monkeypatch, policy_flags, configured, expect_llm
) -> None:
    dossier_id = _serve_fixture_dossier(monkeypatch)
    _unsigned_lane_with_env_policy(monkeypatch, policy_flags)

    class FakeLLM:
        def __init__(self, **_kwargs) -> None:
            pass

        def configured(self) -> bool:
            return configured

    seen: dict[str, object] = {}

    class RecordingRouter:
        def __init__(self, store, gateway, llm=None, vector_recall=None) -> None:
            seen["llm"] = llm

        def query(self, envelope, text, task, *, policy_flags):
            return {"review_state": "ANSWERED", "answer": "x", "citations": [], "used_llm": llm_on()}

    def llm_on() -> bool:
        return seen["llm"] is not None

    monkeypatch.setattr(main, "NineRouterClient", FakeLLM)
    monkeypatch.setattr(main, "QueryRouter", RecordingRouter)

    body = _ask(dossier_id, policy_flags)

    # The configured client reaches the router wrapped in the /query deadline.
    assert isinstance(getattr(seen["llm"], "_llm", None), FakeLLM) is expect_llm
    assert body["used_llm"] is expect_llm


def test_query_provider_failure_falls_back_to_grounded_retrieval(monkeypatch) -> None:
    """A rejected credential must degrade to review, never HTTP 500 or an LLM answer."""
    dossier_id = _serve_fixture_dossier(monkeypatch)
    _unsigned_lane_with_env_policy(monkeypatch, {"egress_allowed": True, "use_llm": True})
    calls: list[str] = []

    class BrokenLLM:
        def __init__(self, **_kwargs) -> None:
            pass

        def configured(self) -> bool:
            return True

        def complete_json(self, *args, **kwargs):
            calls.append("llm")
            raise RuntimeError("provider rejected credential")

    monkeypatch.setattr(main, "NineRouterClient", BrokenLLM)

    body = _ask(
        dossier_id,
        {"egress_allowed": True, "use_llm": True},
        query="So sánh điều 5 hợp đồng và phụ lục",
    )

    assert calls, "the provider must actually be reached for this to test the fallback"
    assert body["state"] == "NEEDS_REVIEW"
    # ``used_llm`` records that the provider lane was attempted; the review
    # state still proves that the rejected provider did not supply an answer.
    assert body["used_llm"] is True
