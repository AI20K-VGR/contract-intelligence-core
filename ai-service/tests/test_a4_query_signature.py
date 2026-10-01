"""A4: /query requires a signed service envelope; the signed lane trusts the
Backend principal for READ_CONTENT inside the signed tenant/dossier (D-5)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import main
from app.reasoning.query import QueryRouter
from app.security.service_envelope import build_service_envelope
from app.tools.gateway import ToolBlocked, ToolGateway
from app.tools.store import InMemorySnapshotStore
from fixtures import envelope as fixture_envelope
from fixtures import mock_record

SECRET = "test-secret"
DOSSIER = "dossier_001"
PROCESSING_ACTOR = "user_001"  # mock_record grants READ_CONTENT to this actor only


def _query(**extra: object) -> dict:
    return {
        "query": "contract value",
        "dossier_id": DOSSIER,
        "snapshot_version": "ai1.snapshot.v1",
        **extra,
    }


def _signed(payload: dict, *, tenant_id: str = "tenant_a", actor_id: str = PROCESSING_ACTOR) -> dict:
    payload = dict(payload)
    payload["service_envelope"] = build_service_envelope(
        payload,
        secret=SECRET,
        tenant_id=tenant_id,
        dossier_id=DOSSIER,
        actor_id=actor_id,
        scopes=["ai2.query"],
    )
    return payload


@pytest.fixture(autouse=True)
def _record_in_store(monkeypatch):
    monkeypatch.setenv("AI2_SERVICE_HMAC_SECRET", SECRET)
    monkeypatch.delenv("AI2_QUERY_REQUIRE_SIGNATURE", raising=False)
    main.STORE._dossiers.clear()
    main.STORE.put(mock_record())
    yield
    main.STORE._dossiers.clear()


@pytest.mark.parametrize("path", ["/query", "/api/v1/query"])
def test_unsigned_query_is_rejected_by_default(path: str):
    response = TestClient(main.app).post(path, json=_query())

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "SERVICE_ENVELOPE_MISSING"


@pytest.mark.parametrize("value", ["true", "1", "yes"])
def test_unsigned_query_is_rejected_when_signature_flag_is_on(monkeypatch, value: str):
    monkeypatch.setenv("AI2_QUERY_REQUIRE_SIGNATURE", value)

    response = TestClient(main.app).post("/query", json=_query())

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "SERVICE_ENVELOPE_MISSING"


def test_signature_flag_off_keeps_unsigned_compatibility_lane(monkeypatch):
    monkeypatch.setenv("AI2_QUERY_REQUIRE_SIGNATURE", "false")

    response = TestClient(main.app).post("/query", json=_query(dossier_id="dossier-unknown"))

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "INSUFFICIENT_EVIDENCE"
    assert body["citations"] == []


def test_signed_query_by_another_actor_reads_content():
    response = TestClient(main.app).post("/query", json=_signed(_query(), actor_id="reviewer-42"))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["state"] != "BLOCKED", body
    assert body["citations"]
    codes = [step.get("code") for step in body["reasoning_trace"] if isinstance(step, dict)]
    assert "TOOL_BLOCKED" not in codes


def test_signed_query_for_another_tenant_reads_nothing():
    response = TestClient(main.app).post("/query", json=_signed(_query(), tenant_id="tenant_b"))

    assert response.status_code == 200
    body = response.json()
    assert body["state"] in {"BLOCKED", "INSUFFICIENT_EVIDENCE"}
    assert body["citations"] == []


def test_signed_query_with_tampered_payload_is_rejected():
    payload = _signed(_query())
    payload["dossier_id"] = "dossier_other"

    response = TestClient(main.app).post("/query", json=payload)

    assert response.status_code == 401


def test_signed_gateway_lane_blocks_cross_tenant_envelope():
    store = InMemorySnapshotStore()
    store.put(mock_record())
    foreign = fixture_envelope(actor="reviewer-42")
    foreign = foreign.model_copy(update={"auth": foreign.auth.model_copy(update={"tenant_id": "tenant_b"})})

    with pytest.raises(ToolBlocked):
        ToolGateway(store, signed_principal=True).call("list_structure", foreign, dossier_id=DOSSIER)
    blocked = QueryRouter(store, ToolGateway(store, signed_principal=True)).query(foreign, "contract value")
    assert blocked["review_state"] == "BLOCKED"


def test_unsigned_gateway_keeps_record_acl():
    store = InMemorySnapshotStore()
    store.put(mock_record())

    with pytest.raises(ToolBlocked):
        ToolGateway(store).call("list_structure", fixture_envelope(actor="reviewer-42"), dossier_id=DOSSIER)
    assert ToolGateway(store, signed_principal=True).call(
        "list_structure", fixture_envelope(actor="reviewer-42"), dossier_id=DOSSIER
    )
