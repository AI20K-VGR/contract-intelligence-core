"""HTTP adapters for external AI1 (OCR) and AI2 (Semantics) services.

Async non-blocking calls via ``httpx``. Used by the Kafka worker / orchestrator
to submit jobs without blocking the API request path.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import re
import time
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import quote, urlencode
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


async def _get_json_bounded(
    url: str,
    *,
    headers: dict[str, str] | None,
    service: str,
    max_response_bytes: int,
) -> dict[str, Any]:
    """Fetch JSON with a streaming byte ceiling for graph and trace projections."""
    logger.info("ai_adapter.request", service=service, url=url)
    try:
        chunks: list[bytes] = []
        size = 0
        async with (
            httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client,
            client.stream("GET", url, headers=headers) as response,
        ):
            content_length = response.headers.get("content-length")
            if content_length:
                try:
                    declared_size = int(content_length)
                except ValueError as exc:
                    raise AiAdapterError(f"{service} returned malformed Content-Length") from exc
                if declared_size < 0 or declared_size > max_response_bytes:
                    raise AiAdapterError(f"{service} response exceeded the size limit")
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > max_response_bytes:
                    raise AiAdapterError(f"{service} response exceeded the size limit")
                chunks.append(chunk)
            raw = b"".join(chunks)
            if not response.is_success:
                detail = raw[:500].decode("utf-8", "replace")
                raise AiAdapterHTTPError(response.status_code, detail)
    except httpx.TimeoutException as exc:
        raise AiAdapterTimeoutError(f"{service} request timed out: {url}") from exc
    except httpx.HTTPError as exc:
        raise AiAdapterError(f"{service} transport error: {exc}") from exc
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise AiAdapterError(f"{service} returned invalid JSON") from exc
    if not isinstance(data, dict):
        raise AiAdapterError(f"{service} returned non-object JSON")
    return data


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
    on_progress: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> dict[str, Any]:
    """Poll canonical AI2 until the job is terminal or ``timeout_seconds`` pass.

    ``on_progress`` receives the ``progress`` object of each non-terminal
    report (BE-AI2-PROCESSING-CONTRACT §3). It is advisory: an error in it is logged and the
    poll goes on.

    Transient errors (timeout, transport, 429, 5xx) are retried up to
    ``ai2_max_consecutive_errors`` in a row, so one slow or failed poll no
    longer fails a run whose AI2 job is still healthy.

    AI2 runs a bounded number of jobs at once and keeps the rest QUEUED. Its
    processing budget starts when a job leaves the queue, so ``timeout_seconds``
    is counted from then too; time spent QUEUED is capped separately by
    ``ai2_max_queue_wait_seconds``.

    Raises:
        AiAdapterDeadlineExceeded: the job was still running at the deadline,
            or still queued past the queue cap.
        AiAdapterError: a non-transient error, or too many transient ones in a row.
    """
    settings = get_settings()
    interval = settings.ai_dispatcher_poll_interval_seconds
    started = time.monotonic()
    queue_deadline = started + settings.ai2_max_queue_wait_seconds
    deadline = started + timeout_seconds
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
            status = str(report.get("status", "")).upper()
            if status in {"SUCCEEDED", "FAILED"}:
                return report
            progress = report.get("progress")
            if on_progress is not None and isinstance(progress, dict):
                try:
                    await on_progress(progress)
                except Exception:
                    logger.warning("ai2.poll.progress_failed", job_id=job_id, exc_info=True)
            if status == "QUEUED":
                now = time.monotonic()
                if now >= queue_deadline:
                    raise AiAdapterDeadlineExceeded(
                        f"AI2 job {job_id} was still queued after "
                        f"{settings.ai2_max_queue_wait_seconds}s"
                    )
                # Not started yet: the processing budget has not begun.
                deadline = now + timeout_seconds
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


_GRAPH_STATUSES = frozenset(
    {
        "READY",
        "PENDING",
        "STALE",
        "UNAVAILABLE",
        "PERSISTENCE_UNKNOWN",
        "PERSIST_FAILED",
        "FAILED",
        "SKIPPED",
    }
)
_GRAPH_TOP_KEYS = frozenset(
    {
        "status",
        "graph_kind",
        "tenant_id",
        "dossier_id",
        "job_id",
        "snapshot_digest",
        "edges",
        "total_count",
        "has_more",
        "next_cursor",
        "error_code",
    }
)
_GRAPH_EDGE_KEYS = frozenset(
    {
        "tenant_id",
        "dossier_id",
        "job_id",
        "snapshot_digest",
        "id",
        "kind",
        "label",
        "directed",
        "source_node_id",
        "target_node_id",
        "source_document_id",
        "target_document_id",
        "target_address",
        "review_state",
        "source_citation_ref",
        "target_citation_ref",
        "digest",
    }
)
_EDGE_OPS = frozenset({"INSERTION", "SUBSTITUTION", "REPEAL", "REJECTION", "SCOPE_LIMIT"})
_PAIR_LABELS = frozenset({"GENERAL_SPECIFIC", "CONFLICT", "DUPLICATE", "REFERENCE"})
_REVIEW_STATES = frozenset(
    {"PASS", "NEEDS_REVIEW", "INSUFFICIENT_EVIDENCE", "BLOCKED", "ANSWERED", "NOT_COMPARABLE"}
)
_TRACE_STATUSES = frozenset(
    {
        "COMPLETE",
        "IN_PROGRESS",
        "INTERRUPTED_UNKNOWN",
        "INCOMPLETE_UNKNOWN",
        "TRACE_UNAVAILABLE",
    }
)
_TRACE_STAGE_STATUSES = frozenset(
    {
        "RUNNING",
        "COMPLETED",
        "FAILED",
        "SKIPPED",
        "INTERRUPTED_UNKNOWN",
        "INCOMPLETE_UNKNOWN",
    }
)
_TRACE_STAGE_IDS = frozenset(
    {"extraction", "contract_graph_operation", "contract_graph_pairs", "semantic"}
)
_SAFE_REASON_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


def _validate_ai2_graph_page(
    payload: dict[str, Any],
    *,
    tenant_id: str,
    dossier_id: str,
    job_id: str,
    snapshot_digest: str,
    graph_kind: str,
    limit: int,
) -> dict[str, Any]:
    if set(payload) - _GRAPH_TOP_KEYS:
        raise AiAdapterError("AI2 graph response contains unsupported fields")
    status_value = payload.get("status")
    if status_value not in _GRAPH_STATUSES:
        raise AiAdapterError("AI2 graph response has an unknown status")
    if payload.get("graph_kind") not in (None, graph_kind):
        raise AiAdapterError("AI2 graph response scope mismatch")
    for field, expected in (
        ("tenant_id", tenant_id),
        ("dossier_id", dossier_id),
        ("job_id", job_id),
    ):
        if field in payload and payload[field] != expected:
            raise AiAdapterError("AI2 graph response scope mismatch")
    if payload.get("snapshot_digest") != snapshot_digest:
        raise AiAdapterError("AI2 graph response snapshot mismatch")
    if status_value == "READY" and any(
        payload.get(key) != expected
        for key, expected in (
            ("tenant_id", tenant_id),
            ("dossier_id", dossier_id),
            ("job_id", job_id),
        )
    ):
        raise AiAdapterError("AI2 graph page identity is missing")
    edges = payload.get("edges")
    count = payload.get("total_count")
    has_more = payload.get("has_more")
    cursor = payload.get("next_cursor")
    if (
        not isinstance(edges, list)
        or len(edges) > limit
        or isinstance(count, bool)
        or not isinstance(count, int)
        or count < 0
        or not isinstance(has_more, bool)
        or (cursor is not None and (not isinstance(cursor, str) or len(cursor) > 80))
        or (has_more and not cursor)
        or (not has_more and cursor is not None)
    ):
        raise AiAdapterError("AI2 graph response page is malformed")
    if status_value != "READY" and edges:
        raise AiAdapterError("AI2 returned graph rows for a non-ready status")
    for edge in edges:
        if not isinstance(edge, dict) or set(edge) - _GRAPH_EDGE_KEYS:
            raise AiAdapterError("AI2 graph edge contains unsupported fields")
        if any(
            edge.get(key) != expected
            for key, expected in (
                ("tenant_id", tenant_id),
                ("dossier_id", dossier_id),
                ("job_id", job_id),
                ("snapshot_digest", snapshot_digest),
            )
        ):
            raise AiAdapterError("AI2 graph row identity mismatch")
        if not all(
            isinstance(edge.get(key), str) and edge[key] and len(edge[key]) <= 512
            for key in (
                "id",
                "kind",
                "label",
                "source_node_id",
                "target_node_id",
                "review_state",
                "source_citation_ref",
                "target_citation_ref",
                "digest",
            )
        ):
            raise AiAdapterError("AI2 graph edge identity is malformed")
        labels = _EDGE_OPS if graph_kind == "operation" else _PAIR_LABELS
        if edge["label"] not in labels or edge["review_state"] not in _REVIEW_STATES:
            raise AiAdapterError("AI2 graph edge has an unknown label")
        if not isinstance(edge.get("directed"), bool):
            raise AiAdapterError("AI2 graph edge direction is malformed")
        if (
            "target_address" in edge
            and edge["target_address"] is not None
            and (not isinstance(edge["target_address"], str) or len(edge["target_address"]) > 512)
        ):
            raise AiAdapterError("AI2 graph edge address is malformed")
        for field in ("source_document_id", "target_document_id"):
            value = edge.get(field)
            if field not in edge or (
                value is not None and (not isinstance(value, str) or not value or len(value) > 512)
            ):
                raise AiAdapterError("AI2 graph edge document identity is malformed")
    return {
        "status": status_value,
        "graph_kind": graph_kind,
        "snapshot_digest": snapshot_digest,
        "edges": edges,
        "total_count": count,
        "has_more": has_more,
        "next_cursor": cursor,
        **(
            {"error_code": payload["error_code"]}
            if isinstance(payload.get("error_code"), str)
            else {}
        ),
    }


def _validate_ai2_trace(payload: dict[str, Any], *, snapshot_digest: str) -> dict[str, Any]:
    allowed = {
        "schema_version",
        "trace_status",
        "status",
        "execution_id",
        "snapshot_digest",
        "job_status",
        "reason_code",
        "stages",
    }
    if set(payload) - allowed or payload.get("schema_version") != "ai2.processing-trace.v1":
        raise AiAdapterError("AI2 trace response contains unsupported fields")
    if payload.get("snapshot_digest") != snapshot_digest:
        raise AiAdapterError("AI2 trace response snapshot mismatch")
    job_status = payload.get("job_status")
    if job_status is not None and (
        not isinstance(job_status, str)
        or job_status not in {"QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"}
    ):
        raise AiAdapterError("AI2 trace response has an unknown job status")
    status_value = payload.get("status")
    if status_value not in _TRACE_STATUSES or payload.get("trace_status") not in {
        "AVAILABLE",
        "UNAVAILABLE",
    }:
        raise AiAdapterError("AI2 trace response has an unknown status")
    stages = payload.get("stages")
    if not isinstance(stages, list) or len(stages) > 32:
        raise AiAdapterError("AI2 trace response stages are malformed")
    stage_keys = {"stage_id", "status", "started_ms", "duration_ms", "item_count", "reason_code"}
    for stage in stages:
        if not isinstance(stage, dict) or set(stage) != stage_keys:
            raise AiAdapterError("AI2 trace stage contains unsupported fields")
        if (
            stage["stage_id"] not in _TRACE_STAGE_IDS
            or stage["status"] not in _TRACE_STAGE_STATUSES
        ):
            raise AiAdapterError("AI2 trace stage is malformed")
        for key in ("started_ms", "duration_ms", "item_count"):
            value = stage[key]
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise AiAdapterError("AI2 trace timing/count is malformed")
        if stage["reason_code"] is not None and (
            not isinstance(stage["reason_code"], str)
            or not _SAFE_REASON_CODE.fullmatch(stage["reason_code"])
        ):
            raise AiAdapterError("AI2 trace reason code is malformed")
    return {
        "schema_version": "ai2.processing-trace.v1",
        "trace_status": payload["trace_status"],
        "status": status_value,
        "snapshot_digest": snapshot_digest,
        "stages": stages,
        **(
            {"execution_id": payload["execution_id"]}
            if isinstance(payload.get("execution_id"), str)
            else {}
        ),
        **(
            {"job_status": payload["job_status"]}
            if isinstance(payload.get("job_status"), str)
            else {}
        ),
        **(
            {"reason_code": payload["reason_code"]}
            if isinstance(payload.get("reason_code"), str)
            else {}
        ),
    }


async def read_ai2_contract_graph(
    job_id: str,
    *,
    dossier_id: str,
    snapshot_digest: str,
    graph_kind: str,
    tenant_id: str,
    actor_id: str,
    cursor: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    if graph_kind not in {"operation", "pair"} or not 1 <= limit <= 100:
        raise AiAdapterError("AI2 graph request is invalid")
    if cursor is not None and (
        len(cursor) > 80
        or not cursor.startswith("cedge:" if graph_kind == "operation" else "cpair:")
    ):
        raise AiAdapterError("AI2 graph cursor is invalid")
    request = {
        "job_id": job_id,
        "dossier_id": dossier_id,
        "snapshot_digest": snapshot_digest,
        "graph_kind": graph_kind,
        "cursor": cursor,
        "limit": limit,
    }
    envelope = _service_envelope(
        request,
        tenant_id=tenant_id,
        dossier_id=dossier_id,
        actor_id=actor_id,
        scopes=["ai2.graph.read"],
    )
    query = urlencode({key: value for key, value in request.items() if value is not None})
    payload = await _get_json_bounded(
        f"{_canonical_ai2_base_url()}/internal/contract-graph/{quote(job_id, safe='')}?{query}",
        headers={"X-AI2-Service-Envelope": json.dumps(envelope)},
        max_response_bytes=512_000,
        service="ai2.contract_graph.read",
    )
    return _validate_ai2_graph_page(
        payload,
        tenant_id=tenant_id,
        dossier_id=dossier_id,
        job_id=job_id,
        snapshot_digest=snapshot_digest,
        graph_kind=graph_kind,
        limit=limit,
    )


async def read_ai2_contract_graph_evidence(
    job_id: str,
    *,
    dossier_id: str,
    snapshot_digest: str,
    graph_kind: str,
    node_id: str,
    citation_ref: str,
    tenant_id: str,
    actor_id: str,
) -> dict[str, Any]:
    """Read source text from the persisted AI2 citation under a signed scope."""
    if graph_kind not in {"operation", "pair"} or not node_id or len(node_id) > 512:
        raise AiAdapterError("AI2 graph evidence request is invalid")
    if not citation_ref or len(citation_ref) > 256:
        raise AiAdapterError("AI2 graph evidence reference is invalid")
    request = {
        "job_id": job_id,
        "dossier_id": dossier_id,
        "snapshot_digest": snapshot_digest,
        "graph_kind": graph_kind,
        "node_id": node_id,
        "citation_ref": citation_ref,
    }
    envelope = _service_envelope(
        request,
        tenant_id=tenant_id,
        dossier_id=dossier_id,
        actor_id=actor_id,
        scopes=["ai2.graph.read"],
    )
    query = urlencode(request)
    evidence_url = (
        f"{_canonical_ai2_base_url()}/internal/contract-graph/{quote(job_id, safe='')}/evidence"
    )
    payload = await _get_json_bounded(
        f"{evidence_url}?{query}",
        headers={"X-AI2-Service-Envelope": json.dumps(envelope)},
        max_response_bytes=128_000,
        service="ai2.contract_graph.evidence",
    )
    if (
        not isinstance(payload, dict)
        or set(payload)
        != {
            "job_id",
            "snapshot_digest",
            "graph_kind",
            "node_id",
            "citation_ref",
            "quote",
            "page",
        }
        or payload.get("job_id") != job_id
        or payload.get("snapshot_digest") != snapshot_digest
        or payload.get("graph_kind") != graph_kind
        or payload.get("node_id") != node_id
        or payload.get("citation_ref") != citation_ref
        or not isinstance(payload.get("quote"), str)
        or not payload["quote"].strip()
        or len(payload["quote"]) > 20_000
        or (
            payload.get("page") is not None
            and (isinstance(payload["page"], bool) or not isinstance(payload["page"], int))
        )
    ):
        raise AiAdapterError("AI2 graph evidence response is malformed")
    return payload


async def read_ai2_processing_trace(
    job_id: str,
    *,
    dossier_id: str,
    snapshot_digest: str,
    tenant_id: str,
    actor_id: str,
) -> dict[str, Any]:
    request = {"job_id": job_id, "dossier_id": dossier_id, "snapshot_digest": snapshot_digest}
    envelope = _service_envelope(
        request,
        tenant_id=tenant_id,
        dossier_id=dossier_id,
        actor_id=actor_id,
        scopes=["ai2.trace.read"],
    )
    query = urlencode(request)
    payload = await _get_json_bounded(
        f"{_canonical_ai2_base_url()}/internal/processing-trace/{quote(job_id, safe='')}?{query}",
        headers={"X-AI2-Service-Envelope": json.dumps(envelope)},
        max_response_bytes=64_000,
        service="ai2.processing_trace.read",
    )
    return _validate_ai2_trace(payload, snapshot_digest=snapshot_digest)


__all__ = [
    "AiAdapterDeadlineExceeded",
    "AiAdapterError",
    "AiAdapterHTTPError",
    "AiAdapterTimeoutError",
    "is_transient",
    "read_ai2_contract_graph",
    "read_ai2_contract_graph_evidence",
    "read_ai2_processing_trace",
    "poll_ai2_processing",
    "query_ai2",
    "submit_ai2_processing",
]
