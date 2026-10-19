"""Service-to-service trust: AI2 HMAC envelope, Keycloak webhook, callbacks.

AI2 accepts work only with a `service_envelope` HMAC-signed by the backend
(docs/contracts/BE-AI2-PROCESSING-CONTRACT.vi.md). The envelopes here are
built like ai-service/app/security/service_envelope.py does, but signed with
a key the attacker controls, so they must all be refused before any work.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid

import httpx
import pytest

pytestmark = pytest.mark.security


def _canonical(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _envelope(payload: dict, *, secret: str, tenant: str, issued_at: int | None = None, audience="vsf-ai2") -> dict:
    now = int(time.time()) if issued_at is None else issued_at
    env = {
        "schema_version": "ai2.service-envelope.v1",
        "issuer": "backend-service",
        "audience": audience,
        "tenant_id": tenant,
        "actor_id": "qa-attacker",
        "dossier_id": payload["dossier_id"],
        "scopes": ["ai2.jobs.submit"],
        "key_id": "default",
        "issued_at": now,
        "expires_at": now + 300,
        "nonce": uuid.uuid4().hex,
        "payload_sha256": hashlib.sha256(_canonical(payload)).hexdigest(),
    }
    env["signature"] = hmac.new(secret.encode(), _canonical(env), hashlib.sha256).hexdigest()
    return env


@pytest.fixture(scope="module")
def ai2(cfg):
    if not cfg.ai2_direct:
        pytest.skip("AI2 is internal to ci-network in this environment; its port is not reachable")
    try:
        health = httpx.get(f"{cfg.ai2_url}/health", timeout=5)
    except httpx.ConnectError:
        pytest.skip("AI2 port not published on this host (production layout)")
    # On prod QA_AI2_URL points at the backend host; make sure we really reached
    # AI2 (it reports an "embedding"/"persist" block) and not the backend.
    body = health.json() if health.headers.get("content-type", "").startswith("application/json") else {}
    if "persist" not in body and "embedding" not in body:
        pytest.skip("QA_AI2_URL does not resolve to the AI2 service here; skipping direct AI2 checks")
    with httpx.Client(base_url=cfg.ai2_url, timeout=20) as client:
        yield client


PAYLOAD = {"dossier_id": "dos_qa_forged", "tenant_id": "tenant_vgr_01", "job_id": "job_qa_forged"}


@pytest.mark.parametrize("path", ["/jobs/idp", "/query", "/api/v1/query"])
def test_ai2_requires_envelope(ai2, path):
    """AI2 work endpoints refuse requests with no service_envelope (401)."""
    r = ai2.post(path, json=PAYLOAD)
    assert r.status_code == 401
    assert "SERVICE_ENVELOPE" in r.text


def test_ai2_rejects_wrong_hmac_secret(ai2):
    """Well-formed envelope signed with the wrong secret -> 401 SERVICE_SIGNATURE_INVALID."""
    body = dict(PAYLOAD, service_envelope=_envelope(PAYLOAD, secret="attacker-secret", tenant="tenant_vgr_01"))
    r = ai2.post("/jobs/idp", json=body)
    assert r.status_code == 401
    assert "SIGNATURE_INVALID" in r.text


def test_ai2_rejects_tampered_payload(ai2):
    """Envelope hash computed over another payload -> 401 (payload hash mismatch)."""
    env = _envelope(PAYLOAD, secret="attacker-secret", tenant="tenant_vgr_01")
    body = dict(PAYLOAD, dossier_id="dos_someone_else", service_envelope=env)
    r = ai2.post("/jobs/idp", json=body)
    assert r.status_code == 401


def test_ai2_rejects_expired_envelope(ai2):
    """Envelope issued two hours ago -> 401 SERVICE_ENVELOPE_EXPIRED."""
    env = _envelope(PAYLOAD, secret="x", tenant="tenant_vgr_01", issued_at=int(time.time()) - 7200)
    r = ai2.post("/jobs/idp", json=dict(PAYLOAD, service_envelope=env))
    assert r.status_code == 401
    assert "EXPIRED" in r.text


def test_ai2_rejects_wrong_audience(ai2):
    """Envelope addressed to another audience -> 401."""
    env = _envelope(PAYLOAD, secret="x", tenant="tenant_vgr_01", audience="some-other-service")
    r = ai2.post("/jobs/idp", json=dict(PAYLOAD, service_envelope=env))
    assert r.status_code == 401
    assert "AUDIENCE" in r.text


@pytest.mark.xfail(
    reason="FINDING SEC-03: AI2 lab/workspace endpoints (/api/workspace/*, /api/cases) have no auth; "
    "port 8002 is published in dev compose (not in prod)",
    strict=True,
)
def test_ai2_lab_endpoints_require_auth(ai2):
    """AI2 workspace endpoints should refuse anonymous callers."""
    r = ai2.post("/api/workspace/upload", files={"file": ("a.txt", b"", "text/plain")})
    assert r.status_code in (401, 403)


LEGACY_PROCESS_BODY = {
    "dossier_id": "dos_qa",
    "snapshot_id": "snap_qa",
    "snapshot_version": "ai1.snapshot.v1",
    "digest": "qa",
    "dossier_members": [],
    "role_relation_map": {},
    "policy_flags": {},
}


@pytest.mark.parametrize("path", ["/process", "/api/v1/process"])
def test_ai2_legacy_process_has_no_side_effects(ai2, path):
    """Unsigned legacy /process only returns a static INSUFFICIENT_EVIDENCE stub (no facts, no findings)."""
    r = ai2.post(path, json=LEGACY_PROCESS_BODY)
    if r.status_code in (401, 403, 404, 410):
        return
    body = r.json()
    assert body["state"] == "INSUFFICIENT_EVIDENCE"
    assert body["facts"] == [] and body["findings"] == []


@pytest.mark.xfail(
    reason="FINDING SEC-05: legacy /process and /api/v1/process accept unsigned requests (202 stub); "
    "should require the service envelope or be removed",
    strict=True,
)
def test_ai2_legacy_process_requires_envelope(ai2):
    """Legacy /process should refuse unsigned callers like /jobs/idp does."""
    assert ai2.post("/api/v1/process", json=LEGACY_PROCESS_BODY).status_code in (401, 403, 404, 410)


def test_keycloak_webhook_requires_signature(api):
    """Keycloak user-sync webhook without X-Keycloak-Signature -> 401."""
    r = api.post("/api/v1/auth/webhooks/keycloak", json={"type": "REGISTER", "userId": "x"})
    assert r.status_code == 401


def test_keycloak_webhook_rejects_bad_signature(api):
    """Keycloak webhook with a forged signature -> 401."""
    r = api.post(
        "/api/v1/auth/webhooks/keycloak",
        json={"type": "REGISTER", "userId": "x"},
        headers={"X-Keycloak-Signature": "sha256=" + "0" * 64},
    )
    assert r.status_code == 401


def test_external_approval_callback_requires_auth(api):
    """External approval callback without credentials -> 401."""
    assert api.post("/api/v1/external-approvals/callback", json={}).status_code == 401
