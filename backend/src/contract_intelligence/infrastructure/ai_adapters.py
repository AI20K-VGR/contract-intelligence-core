"""HMAC service envelope + canonical AI2 /jobs/idp HTTP adapters.

Lane C (production): POST /jobs/idp + poll GET /jobs/{id} with
``be.ai2.processing.request.v1`` / ``ai2.be.processing.result.v1``.

Legacy ``submit_to_ai2`` → ``/process`` remains for lab/compat only.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
from typing import Any
from uuid import uuid4

import httpx
import structlog

from contract_intelligence.config.settings import get_settings

logger = structlog.get_logger(__name__)

_DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class AiAdapterError(Exception):
    """Base error for AI HTTP adapter failures."""


class AiAdapterTimeoutError(AiAdapterError):
    """Raised when the remote AI service does not respond in time."""


class AiAdapterHTTPError(AiAdapterError):
    """Raised when the remote AI service returns a non-2xx status."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"AI service returned HTTP {status_code}: {detail}")


def _validate_keys(payload: dict[str, Any], required: set[str], label: str) -> None:
    missing = required - payload.keys()
    if missing:
        msg = f"{label} payload missing required keys: {sorted(missing)}"
        raise ValueError(msg)


def canonical_payload_bytes(payload: dict[str, Any]) -> bytes:
    """JSON bytes for envelope payload_sha256 (excludes service_envelope)."""
    data = {k: v for k, v in payload.items() if k != "service_envelope"}
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def payload_sha256(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_payload_bytes(payload)).hexdigest()


def snapshot_payload_digest(snapshot: dict[str, Any]) -> str:
    encoded = json.dumps(
        snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_service_envelope(
    payload: dict[str, Any],
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
    """Build ``ai2.service-envelope.v1`` matching AI2's HMAC verifier."""
    issued_at = int(time.time()) if now is None else now
    envelope: dict[str, Any] = {
        "schema_version": "ai2.service-envelope.v1",
        "issuer": issuer,
        "audience": audience,
        "tenant_id": tenant_id,
        "actor_id": actor_id,
        "dossier_id": dossier_id,
        "scopes": scopes or ["ai2.jobs.submit"],
        "key_id": key_id,
        "issued_at": issued_at,
        "expires_at": issued_at + ttl_seconds,
        "nonce": nonce or uuid4().hex,
        "payload_sha256": payload_sha256(payload),
        "signature": "0" * 64,
    }
    material = json.dumps(
        {k: v for k, v in envelope.items() if k != "signature"},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    envelope["signature"] = hmac.new(secret.encode("utf-8"), material, hashlib.sha256).hexdigest()
    return envelope


async def _post_json(url: str, payload: dict[str, Any], *, service: str) -> dict[str, Any]:
    """POST JSON to ``url`` and return the response body."""
    logger.info("ai_adapter.request", service=service, url=url)
    try:
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            response = await client.post(url, json=payload)
    except httpx.TimeoutException as exc:
        logger.error("ai_adapter.timeout", service=service, url=url, error=str(exc))
        msg = f"{service} request timed out: {url}"
        raise AiAdapterTimeoutError(msg) from exc
    except httpx.HTTPError as exc:
        logger.error("ai_adapter.transport_error", service=service, url=url, error=str(exc))
        msg = f"{service} transport error: {exc}"
        raise AiAdapterError(msg) from exc

    if response.is_success:
        data = response.json()
        if not isinstance(data, dict):
            msg = f"{service} returned non-object JSON"
            raise AiAdapterError(msg)
        logger.info(
            "ai_adapter.response_ok",
            service=service,
            status_code=response.status_code,
        )
        return data

    detail = response.text[:500]
    logger.error(
        "ai_adapter.http_error",
        service=service,
        status_code=response.status_code,
        detail=detail,
    )
    raise AiAdapterHTTPError(response.status_code, detail)


async def _get_json(
    url: str,
    *,
    service: str,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    logger.info("ai_adapter.get", service=service, url=url)
    try:
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            response = await client.get(url, headers=headers)
    except httpx.TimeoutException as exc:
        msg = f"{service} request timed out: {url}"
        raise AiAdapterTimeoutError(msg) from exc
    except httpx.HTTPError as exc:
        msg = f"{service} transport error: {exc}"
        raise AiAdapterError(msg) from exc

    if response.is_success:
        data = response.json()
        if not isinstance(data, dict):
            msg = f"{service} returned non-object JSON"
            raise AiAdapterError(msg)
        return data

    detail = response.text[:500]
    raise AiAdapterHTTPError(response.status_code, detail)


async def submit_to_ai1(payload: dict[str, Any]) -> dict[str, Any]:
    """Submit an OCR job to AI1 (legacy HTTP). POSTs to ``{AI1_BASE_URL}/jobs``."""
    _validate_keys(
        payload,
        {"dossier_id", "document_id", "file_ref", "ocr_profile", "run_id"},
        "AI1",
    )
    settings = get_settings()
    url = f"{settings.ai1_base_url.rstrip('/')}/jobs"
    return await _post_json(url, payload, service="ai1")


async def submit_to_ai2(payload: dict[str, Any]) -> dict[str, Any]:
    """Legacy lab path: POST ``{AI2_BASE_URL}/process`` (metadata-only → fail-closed)."""
    _validate_keys(
        payload,
        {
            "snapshot_id",
            "snapshot_version",
            "digest",
            "dossier_members",
            "role_relation_map",
            "policy_flags",
        },
        "AI2",
    )
    settings = get_settings()
    url = f"{settings.ai2_base_url.rstrip('/')}/process"
    return await _post_json(url, payload, service="ai2")


async def query_ai2(payload: dict[str, Any]) -> dict[str, Any]:
    """Forward a dossier Q&A query to AI2 ``/query``."""
    _validate_keys(
        payload,
        {"query", "dossier_id", "snapshot_version", "acl_context", "policy_flags"},
        "AI2.query",
    )
    settings = get_settings()
    url = f"{settings.ai2_base_url.rstrip('/')}/query"
    return await _post_json(url, payload, service="ai2.query")


def build_idp_request(
    *,
    tenant_id: str,
    dossier_id: str,
    snapshot: dict[str, Any],
    document_id: str,
    source_digest: str,
    request_id: str | None = None,
    idempotency_key: str | None = None,
    attempt: int = 1,
    role: str = "body",
) -> dict[str, Any]:
    """Assemble ``be.ai2.processing.request.v1`` (unsigned; envelope attached next)."""
    settings = get_settings()
    snap = dict(snapshot)
    if snap.get("schema_version") != "ai1.snapshot.v1":
        msg = "AI2 IDP requires snapshot schema_version=ai1.snapshot.v1"
        raise ValueError(msg)

    snapshot_id = str(snap.get("snapshot_id") or "")
    if not snapshot_id:
        msg = "snapshot.snapshot_id is required"
        raise ValueError(msg)

    # Align dossier_id on the snapshot with the request (AI1 may use a task-scoped id).
    snap["dossier_id"] = dossier_id
    if not snap.get("document_id"):
        snap["document_id"] = document_id
    if not snap.get("source_digest"):
        snap["source_digest"] = source_digest

    digest = snapshot_payload_digest(snap)
    member_id = f"mem_{document_id}"
    req_id = request_id or f"req_{uuid4().hex[:24]}"
    idem = idempotency_key or f"idem_{dossier_id}_{snapshot_id}_{attempt}"

    body: dict[str, Any] = {
        "schema_version": "be.ai2.processing.request.v1",
        "request_id": req_id,
        "idempotency_key": idem,
        "attempt": attempt,
        "task_id": f"task_{snapshot_id}",
        "dossier_id": dossier_id,
        "snapshots": [snap],
        "snapshot_identities": [
            {
                "snapshot_id": snapshot_id,
                "snapshot_version": "ai1.snapshot.v1",
                "source_digest": str(snap.get("source_digest") or source_digest),
                "snapshot_digest": digest,
            }
        ],
        "dossier_members": [
            {
                "member_id": member_id,
                "document_id": document_id,
                "snapshot_id": snapshot_id,
                "role": role if role in ("body", "annex") else "body",
                "source_digest": str(snap.get("source_digest") or source_digest),
            }
        ],
        "role_relation_map": [
            {
                "relation_id": f"rel_member_{member_id}",
                "relation_type": "MEMBER_OF",
                "member_id": member_id,
                "related_member_id": None,
                "dossier_id": dossier_id,
            }
        ],
        "policy_flags": {
            "egress_allowed": False,
            "use_vector": False,
            "budget_limits": {
                "max_processing_seconds": 120,
                "max_llm_calls": 0,
                "max_embedding_tokens": 0,
            },
        },
    }
    envelope = build_service_envelope(
        body,
        secret=settings.ai2_service_hmac_secret,
        tenant_id=tenant_id,
        dossier_id=dossier_id,
        issuer=settings.ai2_service_issuer,
        audience=settings.ai2_service_audience,
        key_id=settings.ai2_service_key_id,
        scopes=["ai2.jobs.submit"],
    )
    body["service_envelope"] = envelope
    return body


async def submit_idp_job(request: dict[str, Any]) -> dict[str, Any]:
    """POST ``{AI2_BASE_URL}/jobs/idp`` — returns wire job envelope (QUEUED/…)."""
    settings = get_settings()
    url = f"{settings.ai2_base_url.rstrip('/')}/jobs/idp"
    return await _post_json(url, request, service="ai2.idp")


async def get_idp_job(job_id: str, *, dossier_id: str, tenant_id: str) -> dict[str, Any]:
    """GET ``{AI2_BASE_URL}/jobs/{job_id}`` with a signed poll envelope header."""
    settings = get_settings()
    poll_body: dict[str, Any] = {
        "operation": "get_job",
        "job_id": job_id,
        "dossier_id": dossier_id,
    }
    envelope = build_service_envelope(
        poll_body,
        secret=settings.ai2_service_hmac_secret,
        tenant_id=tenant_id,
        dossier_id=dossier_id,
        issuer=settings.ai2_service_issuer,
        audience=settings.ai2_service_audience,
        key_id=settings.ai2_service_key_id,
        scopes=["ai2.jobs.submit"],
    )
    url = f"{settings.ai2_base_url.rstrip('/')}/jobs/{job_id}"
    return await _get_json(
        url,
        service="ai2.idp.poll",
        headers={"X-AI2-Service-Envelope": json.dumps(envelope, separators=(",", ":"))},
    )


_TERMINAL_OK = frozenset({"SUCCEEDED", "succeeded", "completed", "COMPLETED"})
_TERMINAL_FAIL = frozenset({"FAILED", "failed", "CANCELLED", "cancelled"})


async def poll_idp_job(
    job_id: str,
    *,
    dossier_id: str,
    tenant_id: str,
    interval_seconds: float | None = None,
    max_polls: int | None = None,
) -> dict[str, Any]:
    """Poll until AI2 job reaches a terminal wire status."""
    settings = get_settings()
    interval = (
        interval_seconds if interval_seconds is not None else settings.ai2_idp_poll_interval_seconds
    )
    polls = max_polls if max_polls is not None else settings.ai2_idp_max_polls
    last: dict[str, Any] = {}
    for _ in range(polls):
        last = await get_idp_job(job_id, dossier_id=dossier_id, tenant_id=tenant_id)
        status = str(last.get("status") or "")
        if status in _TERMINAL_OK or status in _TERMINAL_FAIL:
            return last
        await asyncio.sleep(interval)
    msg = f"AI2 IDP job {job_id} did not complete within {polls} polls"
    raise AiAdapterTimeoutError(msg)


def wire_result_to_findings_payload(wire: dict[str, Any], *, run_id: str) -> dict[str, Any]:
    """Map ``ai2.be.processing.result.v1`` → webhook-shaped flat payload."""
    raw_result = wire.get("result")
    result: dict[str, Any] = raw_result if isinstance(raw_result, dict) else {}
    facts = list(result.get("facts") or [])
    findings = list(result.get("findings") or [])
    index_contribution = dict(result.get("index_contribution") or {})
    return {
        "run_id": run_id,
        "job_id": wire.get("job_id"),
        "status": wire.get("status"),
        "facts": facts,
        "findings": findings,
        "index_contribution": index_contribution,
        "errors": list(wire.get("errors") or []),
    }


__all__ = [
    "AiAdapterError",
    "AiAdapterHTTPError",
    "AiAdapterTimeoutError",
    "build_idp_request",
    "build_service_envelope",
    "get_idp_job",
    "payload_sha256",
    "poll_idp_job",
    "query_ai2",
    "snapshot_payload_digest",
    "submit_idp_job",
    "submit_to_ai1",
    "submit_to_ai2",
    "wire_result_to_findings_payload",
]
