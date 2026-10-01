"""HMAC-signed service envelope verification for the canonical AI2 API."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from collections.abc import Mapping
from typing import Any
from uuid import uuid4

from app.contracts.wire import ServiceEnvelope


class ServiceEnvelopeError(ValueError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


def canonical_payload(payload: Mapping[str, Any]) -> bytes:
    data = dict(payload)
    data.pop("service_envelope", None)
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def payload_sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_payload(payload)).hexdigest()


def _signature_material(envelope: ServiceEnvelope) -> bytes:
    unsigned = envelope.model_dump(exclude={"signature"})
    return json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sign(envelope: ServiceEnvelope, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), _signature_material(envelope), hashlib.sha256).hexdigest()


def build_service_envelope(
    payload: Mapping[str, Any],
    *,
    secret: str,
    tenant_id: str,
    dossier_id: str,
    actor_id: str = "backend",
    issuer: str = "backend-service",
    audience: str = "vsf-ai2",
    key_id: str = "default",
    scopes: list[str] | None = None,
    now: int | None = None,
    ttl_seconds: int = 300,
    nonce: str | None = None,
) -> dict[str, Any]:
    issued_at = int(time.time()) if now is None else now
    envelope = ServiceEnvelope(
        schema_version="ai2.service-envelope.v1",
        issuer=issuer,
        audience=audience,
        tenant_id=tenant_id,
        actor_id=actor_id,
        dossier_id=dossier_id,
        scopes=scopes or ["ai2.jobs.submit"],
        key_id=key_id,
        issued_at=issued_at,
        expires_at=issued_at + ttl_seconds,
        nonce=nonce or uuid4().hex,
        payload_sha256=payload_sha256(payload),
        signature="0" * 64,
    )
    envelope.signature = _sign(envelope, secret)
    return envelope.model_dump()


def verify_service_envelope(
    payload: Mapping[str, Any],
    *,
    now: int | None = None,
    required_scope: str = "ai2.jobs.submit",
) -> ServiceEnvelope:
    raw = payload.get("service_envelope")
    if not isinstance(raw, Mapping):
        raise ServiceEnvelopeError("service_envelope is required", code="SERVICE_ENVELOPE_MISSING")
    try:
        envelope = ServiceEnvelope.model_validate(raw)
    except Exception as exc:
        raise ServiceEnvelopeError(f"invalid service envelope: {exc}", code="SERVICE_ENVELOPE_INVALID") from exc

    secret = os.getenv("AI2_SERVICE_HMAC_SECRET", "")
    if not secret:
        raise ServiceEnvelopeError("AI2_SERVICE_HMAC_SECRET is not configured", code="SERVICE_SECRET_UNCONFIGURED")
    expected_issuer = os.getenv("AI2_SERVICE_ISSUER", "backend-service")
    expected_audience = os.getenv("AI2_SERVICE_AUDIENCE", "vsf-ai2")
    expected_key_id = os.getenv("AI2_SERVICE_KEY_ID", "default")
    if envelope.issuer != expected_issuer or envelope.audience != expected_audience:
        raise ServiceEnvelopeError("service envelope issuer/audience mismatch", code="SERVICE_ENVELOPE_AUDIENCE_INVALID")
    if envelope.key_id != expected_key_id:
        raise ServiceEnvelopeError("service envelope key_id is not accepted", code="SERVICE_ENVELOPE_KEY_INVALID")
    if required_scope not in envelope.scopes:
        raise ServiceEnvelopeError("service envelope scope is missing", code="SERVICE_SCOPE_MISSING")

    current = int(time.time()) if now is None else now
    skew = int(os.getenv("AI2_SERVICE_CLOCK_SKEW_SECONDS", "30"))
    max_ttl = int(os.getenv("AI2_SERVICE_MAX_TTL_SECONDS", "3600"))
    if envelope.issued_at > current + skew:
        raise ServiceEnvelopeError("service envelope is issued in the future", code="SERVICE_ENVELOPE_NOT_YET_VALID")
    if envelope.expires_at <= current - skew:
        raise ServiceEnvelopeError("service envelope has expired", code="SERVICE_ENVELOPE_EXPIRED")
    if envelope.expires_at - envelope.issued_at > max_ttl:
        raise ServiceEnvelopeError("service envelope lifetime is too long", code="SERVICE_ENVELOPE_TTL_INVALID")

    expected_hash = payload_sha256(payload)
    if not hmac.compare_digest(envelope.payload_sha256.lower(), expected_hash):
        raise ServiceEnvelopeError("service envelope payload hash mismatch", code="SERVICE_PAYLOAD_HASH_MISMATCH")
    expected_signature = _sign(envelope, secret)
    if not hmac.compare_digest(envelope.signature.lower(), expected_signature):
        raise ServiceEnvelopeError("service envelope signature mismatch", code="SERVICE_SIGNATURE_INVALID")
    if str(payload.get("dossier_id") or "") != envelope.dossier_id:
        raise ServiceEnvelopeError("service envelope dossier binding mismatch", code="SERVICE_DOSSIER_MISMATCH")
    return envelope
