from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.security.service_envelope import ServiceEnvelopeError, build_service_envelope, verify_service_envelope


def _payload() -> dict:
    return {
        "schema_version": "be.ai2.processing.request.v1",
        "request_id": "req-security-1",
        "idempotency_key": "idem-security-1",
        "attempt": 1,
        "task_id": "process-dossier",
        "dossier_id": "dossier-security-1",
    }


def _signed(payload: dict, *, now: int = 1_700_000_000) -> dict:
    result = copy.deepcopy(payload)
    result["service_envelope"] = build_service_envelope(
        result,
        secret="test-secret",
        tenant_id="tenant-a",
        dossier_id=payload["dossier_id"],
        now=now,
        ttl_seconds=60,
    )
    return result


def test_service_envelope_binds_payload_and_identity(monkeypatch):
    monkeypatch.setenv("AI2_SERVICE_HMAC_SECRET", "test-secret")
    payload = _signed(_payload())
    envelope = verify_service_envelope(payload, now=1_700_000_010)
    assert envelope.tenant_id == "tenant-a"
    assert envelope.dossier_id == "dossier-security-1"

    tampered = copy.deepcopy(payload)
    tampered["task_id"] = "other-task"
    with pytest.raises(ServiceEnvelopeError, match="payload hash"):
        verify_service_envelope(tampered, now=1_700_000_010)


def test_service_envelope_rejects_signature_expiry_and_binding(monkeypatch):
    monkeypatch.setenv("AI2_SERVICE_HMAC_SECRET", "test-secret")
    payload = _signed(_payload())

    bad_signature = copy.deepcopy(payload)
    bad_signature["service_envelope"]["signature"] = "0" * 64
    with pytest.raises(ServiceEnvelopeError, match="signature"):
        verify_service_envelope(bad_signature, now=1_700_000_010)

    with pytest.raises(ServiceEnvelopeError, match="expired"):
        verify_service_envelope(payload, now=1_700_000_100)

    wrong_dossier = copy.deepcopy(payload)
    wrong_dossier["service_envelope"]["dossier_id"] = "another-dossier"
    with pytest.raises(ServiceEnvelopeError):
        verify_service_envelope(wrong_dossier, now=1_700_000_010)


def test_jobs_endpoint_requires_signed_service_envelope():
    response = TestClient(app).post("/jobs/idp", json={})
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "SERVICE_ENVELOPE_MISSING"
