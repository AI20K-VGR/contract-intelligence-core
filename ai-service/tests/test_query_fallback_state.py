from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import main
from app.api.main import app
from app.reasoning.query import QueryRouter
from app.reasoning.vector_recall import VectorRecallResult
from app.security.service_envelope import build_service_envelope
from app.tools.gateway import ToolGateway
from app.tools.store import InMemorySnapshotStore
from fixtures import envelope, mock_record


def _record_with_query_terms():
    record = mock_record()
    record.pages[0].text += (
        " Supplier duties include maintaining the delivery schedule. "
        "Payment is due within fifteen days after acceptance. "
        "Either party may terminate this agreement after written notice."
    )
    record.nodes.extend(
        [
            record.nodes[0].model_copy(
                update={
                    "node_id": "duties",
                    "raw_label": "Duties",
                    "order": 6,
                    "text": "Supplier duties include maintaining the delivery schedule.",
                    "structured_key": None,
                    "structured_value": None,
                }
            ),
            record.nodes[0].model_copy(
                update={
                    "node_id": "termination",
                    "raw_label": "Termination",
                    "order": 7,
                    "text": "Either party may terminate this agreement after written notice.",
                    "structured_key": None,
                    "structured_value": None,
                }
            ),
        ]
    )
    return record


@pytest.mark.parametrize(
    ("question", "node_id"),
    [
        ("What are the supplier duties?", "duties"),
        ("When is payment due after acceptance?", "clause_5_3"),
        ("When can either party terminate the agreement?", "termination"),
    ],
)
def test_lexical_fallback_returns_evidence_before_outline_hint(question: str, node_id: str) -> None:
    store = InMemorySnapshotStore()
    store.put(_record_with_query_terms())

    result = QueryRouter(store, ToolGateway(store)).query(envelope(), question)

    assert result["review_state"] != "INSUFFICIENT_EVIDENCE"
    assert result["citations"]
    assert any(citation["node_id"] == node_id for citation in result["citations"])
    assert result["retrieval_layer"]["selected"] == "LEXICAL"
    assert result["used_llm"] is False
    assert result["reasoning_trace"]


class SpyVector:
    def __init__(self) -> None:
        self.calls = 0

    def recall(self, record: Any, query: str, **kwargs: Any) -> VectorRecallResult:
        self.calls += 1
        return VectorRecallResult("READY", trace={"vector_hits": 0})


class SpyLlm:
    def __init__(self) -> None:
        self.calls = 0
        self.traces: list[dict[str, Any]] = []

    def configured(self) -> bool:
        return True

    def complete_json(self, system: str, user: str, **kwargs: Any) -> dict[str, Any]:
        self.calls += 1
        return {
            "answer": "The sources require review.",
            "citations": [{"node_id": "clause_5_3", "text_span": "payment"}],
            "sufficient": False,
        }


@pytest.mark.parametrize(
    ("flags", "vector_calls", "llm_calls"),
    [
        ({"use_vector": False, "use_llm": True, "egress_allowed": True}, 0, 0),
        ({"use_vector": True, "use_llm": False, "egress_allowed": True}, 1, 0),
        ({"use_vector": True, "use_llm": True, "egress_allowed": False}, 1, 0),
    ],
)
def test_vector_and_llm_policy_matrix_is_fail_closed(
    flags: dict[str, bool], vector_calls: int, llm_calls: int
) -> None:
    record = _record_with_query_terms()
    record.nodes.append(
        record.nodes[0].model_copy(
            update={
                "node_id": "annex_1",
                "raw_label": "Phụ lục 1",
                "order": 8,
                "text": "Phụ lục 1 liên quan đến điều khoản thanh toán.",
            }
        )
    )
    store = InMemorySnapshotStore()
    store.put(record)
    vector = SpyVector()
    llm = SpyLlm()
    result = QueryRouter(
        store,
        ToolGateway(store),
        llm=llm,
        vector_recall=vector,
    ).query(envelope(), "Điều 5 liên quan đến phụ lục 1?", policy_flags=flags)

    assert vector.calls == vector_calls
    assert llm.calls == llm_calls
    assert result["review_state"] in {"NEEDS_REVIEW", "INSUFFICIENT_EVIDENCE"}
    assert "retrieval_layer" in result
    assert "reasoning_trace" in result
    assert result["used_llm"] is (llm_calls > 0)


def _signed_query(payload: dict[str, Any]) -> dict[str, Any]:
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


@pytest.mark.parametrize("state", ["PASS", "NEEDS_REVIEW", "INSUFFICIENT_EVIDENCE", "BLOCKED"])
def test_query_endpoint_round_trips_state_and_operational_fields(monkeypatch, state: str) -> None:
    monkeypatch.setenv("AI2_SERVICE_HMAC_SECRET", "test-secret")
    main.STORE._dossiers.clear()
    main.STORE.put(mock_record())

    def fake_query(
        self: Any, envelope: Any, text: str, task: Any = None, policy_flags: Any = None
    ) -> dict[str, Any]:
        return {
            "review_state": state,
            "answer": "answer should not change state",
            "citations": [{"node_id": "field_value", "text_span": "1.000.000.000 VND"}],
            "retrieval_layer": {"selected": "LEXICAL"},
            "reasoning_trace": [{"code": "TEST_TRACE"}],
            "used_llm": False,
        }

    monkeypatch.setattr(QueryRouter, "query", fake_query)
    response = TestClient(app).post(
        "/api/v1/query",
        json=_signed_query(
            {
                "query": "contract value",
                "dossier_id": "dossier_001",
                "snapshot_digest": "sha256:aaa",
                "snapshot_version": "ai1.snapshot.v1",
                "query_contract_version": "ai2.query.v1",
                "policy_flags": {"use_vector": False, "use_llm": False},
            }
        ),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == state
    assert body["connected"] is True
    assert body["used_llm"] is False
    assert body["reasoning_trace"] == [{"code": "TEST_TRACE"}]
    assert body["retrieval_layer"]["selected"] == "LEXICAL"
