"""HTTP adapters for external AI1 (OCR) and AI2 (Semantics) services.

Async non-blocking calls via ``httpx``. Used by the Kafka worker / orchestrator
to submit jobs without blocking the API request path.
"""

from __future__ import annotations

from typing import Any

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


async def submit_to_ai1(payload: dict[str, Any]) -> dict[str, Any]:
    """Submit an OCR job to AI1.

    Expected contract::

        {
            "dossier_id": str,
            "document_id": str,
            "file_ref": str,
            "ocr_profile": str,
            "run_id": str,
        }

    POSTs to ``{AI1_BASE_URL}/jobs``.
    """
    _validate_keys(
        payload,
        {"dossier_id", "document_id", "file_ref", "ocr_profile", "run_id"},
        "AI1",
    )
    settings = get_settings()
    url = f"{settings.ai1_base_url.rstrip('/')}/jobs"
    return await _post_json(url, payload, service="ai1")


async def submit_to_ai2(payload: dict[str, Any]) -> dict[str, Any]:
    """Submit a semantics job to AI2.

    Expected contract::

        {
            "snapshot_id": str,
            "snapshot_version": str | int,
            "digest": str,
            "dossier_members": list,
            "role_relation_map": dict,
            "policy_flags": dict,
        }

    POSTs to ``{AI2_BASE_URL}/process``.
    """
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


__all__ = [
    "AiAdapterError",
    "AiAdapterHTTPError",
    "AiAdapterTimeoutError",
    "submit_to_ai1",
    "submit_to_ai2",
]
