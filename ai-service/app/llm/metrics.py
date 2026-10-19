"""Prometheus metrics for AI2 questions (``/query``) — aggregates only.

Langfuse keeps the per-question story; Prometheus gets counters that Grafana
(``ci-overview`` → "AI2 – Question cost") charts over time. Labels come from
small bounded sets: call kind, model id, answer state, token type. Never the
question, dossier, tenant or user.

Served on ``AI2_METRICS_PORT`` (internal ``ci-monitoring`` network only), like
AI1's ``AI1_METRICS_PORT``. Unset, nothing is served and nothing is counted.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

try:
    from prometheus_client import Counter, Histogram, start_http_server
except ImportError:  # pragma: no cover - prometheus-client is a core dependency
    Counter = Histogram = start_http_server = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

_KINDS = frozenset({"chat", "embedding"})
_TOKEN_TYPES = ("input", "input_cached", "output")
_STATE = re.compile(r"^[A-Z0-9_]{1,40}$")
_MODEL = re.compile(r"^[A-Za-z0-9._:/-]{1,64}$")

_AVAILABLE = Counter is not None

if _AVAILABLE:
    QUERIES = Counter(
        "ai2_query_requests_total",
        "Questions answered by AI2 /query, by answer state.",
        ["state"],
    )
    QUERY_DURATION = Histogram(
        "ai2_query_duration_seconds",
        "Time AI2 spent answering one question (retrieval + LLM).",
        buckets=(0.25, 0.5, 1, 2, 3, 5, 8, 13, 20, 30, 60),
    )
    MODEL_CALLS = Counter(
        "ai2_query_model_calls_total",
        "LLM and embedding calls made while answering questions.",
        ["kind", "model", "status"],
    )
    TOKENS = Counter(
        "ai2_query_tokens_total",
        "Tokens of those calls; input excludes cached input.",
        ["kind", "model", "type"],
    )
    COST = Counter(
        "ai2_query_cost_usd_total",
        "Estimated USD cost of those calls, same figures as the Langfuse cost_details.",
        ["kind", "model"],
    )


def metrics_enabled() -> bool:
    return _AVAILABLE and bool(os.environ.get("AI2_METRICS_PORT", "").strip())


def start_metrics_server() -> None:
    """Serve /metrics on AI2_METRICS_PORT; never stops the service if it cannot."""
    if not metrics_enabled():
        return
    port = os.environ["AI2_METRICS_PORT"].strip()
    try:
        start_http_server(int(port))
    except (OSError, ValueError):
        logger.exception("ai2.metrics.server_failed port=%s", port)
        return
    _create_zero_series()
    logger.info("ai2.metrics.server_started port=%s", port)


def _create_zero_series() -> None:
    """Expose the usual series at 0 so the first question after a restart is counted
    (``increase()`` only sees growth between two samples of one series)."""
    for state in ("ANSWERED", "INSUFFICIENT_EVIDENCE", "NEEDS_REVIEW"):
        QUERIES.labels(state)
    for kind, env, default in (
        ("chat", "AI2_LLM_MODEL", "gpt-5.5"),
        ("embedding", "AI2_EMBEDDING_MODEL", "text-embedding-3-small"),
    ):
        model = _model(os.environ.get(env) or default)
        for status in ("ok", "error"):
            MODEL_CALLS.labels(kind, model, status)
        for token_type in _TOKEN_TYPES:
            TOKENS.labels(kind, model, token_type)
        COST.labels(kind, model)


def _model(value: Any) -> str:
    return value if isinstance(value, str) and _MODEL.match(value) else "other"


def record_query(state: Any, duration_seconds: float) -> None:
    if not metrics_enabled():
        return
    QUERIES.labels(state if isinstance(state, str) and _STATE.match(state) else "OTHER").inc()
    QUERY_DURATION.observe(max(0.0, duration_seconds))


def record_model_call(
    kind: str,
    model: Any,
    usage: dict[str, int] | None,
    cost: dict[str, float] | None,
    *,
    failed: bool,
) -> None:
    if not metrics_enabled():
        return
    kind_label = kind if kind in _KINDS else "other"
    model_label = _model(model)
    MODEL_CALLS.labels(kind_label, model_label, "error" if failed else "ok").inc()
    for token_type in _TOKEN_TYPES:
        tokens = (usage or {}).get(token_type)
        if isinstance(tokens, int) and tokens > 0:
            TOKENS.labels(kind_label, model_label, token_type).inc(tokens)
    total = (cost or {}).get("total")
    if isinstance(total, (int, float)) and total > 0:
        COST.labels(kind_label, model_label).inc(total)


__all__ = ["metrics_enabled", "record_model_call", "record_query", "start_metrics_server"]
