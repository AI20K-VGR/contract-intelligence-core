"""HTTP adapters for external AI1 (OCR) and AI2 (Semantics) services.

Async non-blocking calls via ``httpx``. Used by the Kafka worker / orchestrator
to submit jobs without blocking the API request path.
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


class AiAdapterDeadlineExceeded(AiAdapterTimeoutError):
    """The remote job did not reach a terminal state within its whole budget."""


def is_transient(error: Exception) -> bool:
    """Worth retrying: timeouts, transport errors, 429 and 5xx — not other 4xx."""
    if isinstance(error, AiAdapterHTTPError):
        return error.status_code == 429 or error.status_code >= 500
    return isinstance(error, AiAdapterError) and not isinstance(error, AiAdapterDeadlineExceeded)


def _validate_keys(payload: dict[str, Any], required: set[str], label: str) -> None:
    missing = required - payload.keys()
    if missing:
        msg = f"{label} payload missing required keys: {sorted(missing)}"
        raise ValueError(msg)


async def _post_json(url: str, payload: dict[str, Any], *, service: str) -> dict[str, Any]:
    """POST JSON to ``url`` and return the response body.

    Raises:
        AiAdapterTimeoutError: on connect/read timeout.
        AiAdapterHTTPError: on non-2xx responses.
        AiAdapterError: on other transport failures.
    """
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
    url: str, *, headers: dict[str, str] | None = None, service: str
) -> dict[str, Any]:
    logger.info("ai_adapter.request", service=service, url=url)
    try:
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            response = await client.get(url, headers=headers)
    except httpx.TimeoutException as exc:
        raise AiAdapterTimeoutError(f"{service} request timed out: {url}") from exc
    except httpx.HTTPError as exc:
        raise AiAdapterError(f"{service} transport error: {exc}") from exc
    if response.is_success:
        data = response.json()
        if isinstance(data, dict):
            return data
        raise AiAdapterError(f"{service} returned non-object JSON")
    raise AiAdapterHTTPError(response.status_code, response.text[:500])


def _canonical_payload(payload: dict[str, Any]) -> bytes:
    unsigned = dict(payload)
    unsigned.pop("service_envelope", None)
    return json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _service_envelope(
    payload: dict[str, Any],
    *,
    tenant_id: str,
    dossier_id: str,
    actor_id: str,
    scopes: list[str] | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    secret = (settings.ai2_service_hmac_secret or "").strip()
    if not secret:
        raise AiAdapterError(
            "AI2_SERVICE_HMAC_SECRET is not configured; canonical AI2 calls are fail-closed"
        )
    issued_at = int(time.time())
    envelope = {
        "schema_version": "ai2.service-envelope.v1",
        "issuer": settings.ai2_service_issuer,
        "audience": settings.ai2_service_audience,
        "tenant_id": tenant_id,
        "actor_id": actor_id,
        "dossier_id": dossier_id,
        "scopes": scopes or ["ai2.jobs.submit"],
        "key_id": settings.ai2_service_key_id,
        "issued_at": issued_at,
        "expires_at": issued_at + 300,
        "nonce": uuid4().hex,
        "payload_sha256": hashlib.sha256(_canonical_payload(payload)).hexdigest(),
        "signature": "0" * 64,
    }
    material = json.dumps(
        {key: value for key, value in envelope.items() if key != "signature"},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    envelope["signature"] = hmac.new(secret.encode("utf-8"), material, hashlib.sha256).hexdigest()
    return envelope


def _canonical_ai2_base_url() -> str:
    base = get_settings().ai2_base_url.rstrip("/")
    if base.endswith("/api/v1"):
        return base[: -len("/api/v1")]
    return base


async def submit_ai2_processing(
    payload: dict[str, Any], *, tenant_id: str, dossier_id: str, actor_id: str = "backend"
) -> dict[str, Any]:
    """Submit the canonical Backend ? AI2 async processing request."""
    _validate_keys(
        payload,
        {
            "schema_version",
            "request_id",
            "idempotency_key",
            "attempt",
            "task_id",
            "dossier_id",
            "snapshots",
            "snapshot_identities",
            "dossier_members",
            "role_relation_map",
            "policy_flags",
        },
        "AI2.processing",
    )
    settings = get_settings()
    url = f"{_canonical_ai2_base_url()}/jobs/idp"
    failures = 0
    while True:
        wire = dict(payload)
        # A fresh envelope (nonce) per attempt; AI2 dedupes the job itself on
        # (idempotency_key, attempt), so a resend after a lost reply is safe.
        wire["service_envelope"] = _service_envelope(
            wire, tenant_id=tenant_id, dossier_id=dossier_id, actor_id=actor_id
        )
        try:
            return await _post_json(url, wire, service="ai2.processing")
        except AiAdapterError as exc:
            failures += 1
            if not is_transient(exc) or failures >= settings.ai2_max_consecutive_errors:
                raise
            logger.warning("ai2.submit.retry", failures=failures, error=str(exc))
            await asyncio.sleep(min(30.0, 2.0 ** (failures - 1)))


async def poll_ai2_processing(
    job_id: str,
    *,
    tenant_id: str,
    dossier_id: str,
    timeout_seconds: float,
    actor_id: str = "backend",
) -> dict[str, Any]:
    """Poll canonical AI2 until the job is terminal or ``timeout_seconds`` pass.

    Transient errors (timeout, transport, 429, 5xx) are retried up to
    ``ai2_max_consecutive_errors`` in a row, so one slow or failed poll no
    longer fails a run whose AI2 job is still healthy.

    Raises:
        AiAdapterDeadlineExceeded: the job was still running at the deadline.
        AiAdapterError: a non-transient error, or too many transient ones in a row.
    """
    settings = get_settings()
    interval = settings.ai_dispatcher_poll_interval_seconds
    deadline = time.monotonic() + timeout_seconds
    failures = 0
    while True:
        request = {
            "operation": "get_job",
            "job_id": job_id,
            "dossier_id": dossier_id,
        }
        envelope = _service_envelope(
            request, tenant_id=tenant_id, dossier_id=dossier_id, actor_id=actor_id
        )
        try:
            report = await _get_json(
                f"{_canonical_ai2_base_url()}/jobs/{job_id}",
                headers={"X-AI2-Service-Envelope": json.dumps(envelope)},
                service="ai2.processing.poll",
            )
        except AiAdapterError as exc:
            failures += 1
            if not is_transient(exc) or failures >= settings.ai2_max_consecutive_errors:
                raise
            logger.warning("ai2.poll.retry", job_id=job_id, failures=failures, error=str(exc))
        else:
            failures = 0
            if str(report.get("status", "")).upper() in {"SUCCEEDED", "FAILED"}:
                return report
        if time.monotonic() >= deadline:
            raise AiAdapterDeadlineExceeded(
                f"AI2 job {job_id} did not finish within {int(timeout_seconds)}s"
            )
        await asyncio.sleep(interval)


async def query_ai2(payload: dict[str, Any]) -> dict[str, Any]:
    """Forward a dossier Q&A query to AI2.

    Expected contract::

        {
            "query": str,
            "dossier_id": str,
            "snapshot_version": str,
            "query_contract_version": str,
            "acl_context": str,
            "policy_flags": dict,
        }

    POSTs to ``{AI2_BASE_URL}/query``.
    """
    _validate_keys(
        payload,
        {
            "query",
            "dossier_id",
            "snapshot_version",
            "snapshot_digest",
            "query_contract_version",
            "acl_context",
            "policy_flags",
            "tenant_id",
            "actor_id",
        },
        "AI2.query",
    )
    wire = dict(payload)
    wire["service_envelope"] = _service_envelope(
        wire,
        tenant_id=str(payload["tenant_id"]),
        dossier_id=str(payload["dossier_id"]),
        actor_id=str(payload["actor_id"]),
        scopes=["ai2.query"],
    )
    settings = get_settings()
    url = f"{settings.ai2_base_url.rstrip('/')}/query"
    return await _post_json(url, wire, service="ai2.query")


__all__ = [
    "AiAdapterDeadlineExceeded",
    "AiAdapterError",
    "AiAdapterHTTPError",
    "AiAdapterTimeoutError",
    "is_transient",
    "poll_ai2_processing",
    "query_ai2",
    "submit_ai2_processing",
]
