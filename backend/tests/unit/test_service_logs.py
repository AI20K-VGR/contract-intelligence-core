"""Tests for the secret-safe service log receipt contract."""

from __future__ import annotations

from contract_intelligence.api.v1.service_logs import redact_log_payload


def test_redact_log_payload_removes_credentials_recursively() -> None:
    payload = {
        "Authorization": "Bearer eyJ-this-is-not-a-token-to-store",
        "nested": {"api_key": "sk-test-secret-value", "ok": "dossier-123"},
        "message": "api_key=sk-inline-secret-value",
        "items": [{"password": "keep-out"}],
    }

    redacted = redact_log_payload(payload)

    assert redacted["Authorization"] == "[REDACTED]"
    assert redacted["nested"]["api_key"] == "[REDACTED]"
    assert redacted["nested"]["ok"] == "dossier-123"
    assert "sk-inline-secret-value" not in redacted["message"]
    assert redacted["items"][0]["password"] == "[REDACTED]"
