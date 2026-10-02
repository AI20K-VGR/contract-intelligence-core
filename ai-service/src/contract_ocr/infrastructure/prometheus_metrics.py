"""Prometheus metrics for the AI1 OCR worker — aggregates only.

Langfuse keeps the per-document story (trace, model, latency, cost, errors,
fallback, pages). Prometheus gets counters Grafana can chart over time. Every
label value comes from a small bounded set — engine id, page status, error
code, model id — and never from the request: no document id, tenant, file
name, OCR text or URL.

Served on ``AI1_METRICS_PORT`` (internal network only). With the variable
unset, or ``prometheus_client`` missing, nothing is served and the model-call
metering in ``observability.observation`` stays off.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

try:
    from prometheus_client import Counter, Gauge, Histogram, start_http_server
except ImportError:  # pragma: no cover - the worker image always installs it
    Counter = Gauge = Histogram = start_http_server = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

_ENGINES = frozenset({"pymupdf", "openai", "gemini", "mistral"})
_PAGE_STATUSES = frozenset({"SUCCESS", "PARTIAL", "FAILED"})
_CODE = re.compile(r"^[A-Z0-9_]{1,64}$")
_MODEL = re.compile(r"^[A-Za-z0-9._:/-]{1,64}$")
# Page warnings written by VerifiedMistralOCREngine when its fallback reader
# (GPT) read the page instead of Mistral.
_FALLBACK_PREFIXES = ("ocr:text_reader_fallback", "ocr:text_reader_empty_fallback")
# Page warnings that put the page in front of a reviewer (HITL).
_REVIEW_PREFIXES = ("needs_review:", "possible_duplicate_of:")

_AVAILABLE = Counter is not None

if _AVAILABLE:
    OCR_REQUESTS = Counter(
        "ai1_ocr_requests_total",
        "OCR commands handled by the AI1 worker.",
        ["engine", "status"],
    )
    OCR_FAILURES = Counter(
        "ai1_ocr_failures_total",
        "Failed OCR commands by error code.",
        ["engine", "error_code"],
    )
    OCR_DURATION = Histogram(
        "ai1_ocr_request_duration_seconds",
        "Time from command received to result ready (download + OCR + snapshot).",
        ["engine"],
        buckets=(5, 10, 20, 30, 60, 120, 180, 300, 600, 900, 1200, 1800, 3600),
    )
    OCR_PAGES = Counter(
        "ai1_ocr_pages_processed_total",
        "Pages in finished OCR results, by page status.",
        ["engine", "page_status"],
    )
    OCR_FALLBACK_PAGES = Counter(
        "ai1_ocr_fallback_pages_total",
        "Pages read by the fallback reader because the primary reader failed or was empty.",
        ["engine"],
    )
    OCR_REVIEW_PAGES = Counter(
        "ai1_ocr_review_pages_total",
        "Pages flagged for human review (needs_review / possible duplicate).",
        ["engine"],
    )
    OCR_IN_PROGRESS = Gauge(
        "ai1_ocr_in_progress",
        "OCR commands currently being processed.",
    )
    MODEL_CALLS = Counter(
        "ai1_ocr_model_calls_total",
        "Completed model calls (Mistral / OpenAI / Gemini) made while reading pages.",
        ["model"],
    )
    MODEL_COST = Counter(
        "ai1_ocr_cost_usd_total",
        "Estimated model cost in USD, same figures as the Langfuse cost_details.",
        ["model"],
    )


def metrics_enabled() -> bool:
    return _AVAILABLE and bool(os.environ.get("AI1_METRICS_PORT", "").strip())


def start_metrics_server() -> None:
    """Serve /metrics on AI1_METRICS_PORT; never stops the worker if it cannot."""
    if not metrics_enabled():
        return
    port = os.environ["AI1_METRICS_PORT"].strip()
    try:
        start_http_server(int(port))
    except (OSError, ValueError):
        logger.exception("ai1.metrics.server_failed port=%s", port)
        return
    logger.info("ai1.metrics.server_started port=%s", port)


def _engine(value: Any) -> str:
    return value if value in _ENGINES else "other"


def _code(value: Any) -> str:
    return value if isinstance(value, str) and _CODE.match(value) else "OTHER"


def _model(value: Any) -> str:
    return value if isinstance(value, str) and _MODEL.match(value) else "other"


@contextmanager
def ocr_in_progress() -> Iterator[None]:
    if not _AVAILABLE:
        yield
        return
    OCR_IN_PROGRESS.inc()
    try:
        yield
    finally:
        OCR_IN_PROGRESS.dec()


def record_ocr_job(
    *,
    engine: Any,
    status: str,
    error: Any = None,
    duration_seconds: float | None = None,
    result: Any = None,
) -> None:
    """Count one finished OCR command from its status and snapshot result."""
    if not _AVAILABLE:
        return
    engine_label = _engine(engine)
    succeeded = status == "completed"
    OCR_REQUESTS.labels(engine_label, "completed" if succeeded else "failed").inc()
    if not succeeded:
        code = error.get("code") if isinstance(error, dict) else None
        OCR_FAILURES.labels(engine_label, _code(code or "AI1_OCR_FAILED")).inc()
    if duration_seconds is not None:
        OCR_DURATION.labels(engine_label).observe(duration_seconds)

    snapshot = result.get("snapshot") if isinstance(result, dict) else None
    pages = snapshot.get("pages") if isinstance(snapshot, dict) else None
    for page in pages if isinstance(pages, list) else []:
        if not isinstance(page, dict):
            continue
        status_label = page.get("status")
        OCR_PAGES.labels(
            engine_label, status_label if status_label in _PAGE_STATUSES else "OTHER"
        ).inc()
        warnings = [w for w in page.get("warnings") or [] if isinstance(w, str)]
        if any(w.startswith(_FALLBACK_PREFIXES) for w in warnings):
            OCR_FALLBACK_PAGES.labels(engine_label).inc()
        if any(w.startswith(_REVIEW_PREFIXES) for w in warnings):
            OCR_REVIEW_PAGES.labels(engine_label).inc()


def record_model_call(model: Any, cost_details: Any) -> None:
    """Count a completed model call and its cost (cost_details["total"], USD)."""
    if not _AVAILABLE:
        return
    label = _model(model)
    MODEL_CALLS.labels(label).inc()
    total = cost_details.get("total") if isinstance(cost_details, dict) else None
    if isinstance(total, (int, float)) and total > 0:
        MODEL_COST.labels(label).inc(float(total))


__all__ = [
    "metrics_enabled",
    "ocr_in_progress",
    "record_model_call",
    "record_ocr_job",
    "start_metrics_server",
]
