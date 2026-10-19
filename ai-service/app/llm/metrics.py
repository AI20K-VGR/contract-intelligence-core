"""Prometheus metrics for AI2 — aggregates only, kept apart from AI1's ``ai1_*``.

Two families, both charted on the Grafana dashboard ``ai2-cost``:

- ``ai2_query_*``: questions (``/query``). Langfuse keeps the per-question story.
- ``ai2_idp_*``: processing jobs (facts, conflicts, contract graph). A job runs in
  a spawned child (``AI2_JOB_ISOLATION=process``): the child sends one summary
  over its pipe and the API process, which serves /metrics, records it.

Labels come from small bounded sets: call kind, model id, answer or job state,
token type, pipeline operation. Never the question, dossier, tenant or user.

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
_OPERATION = re.compile(r"^[a-z0-9_.:-]{1,48}$")
_PHASES = ("snapshot_load", "claim", "pipeline", "persist")
# The ``operation=`` names job code passes to ``PipelineRuntime.complete_json``.
_OPERATIONS = ("alias", "fact_normalize", "pairs", "slot_context", "table")
_FINDING_KINDS = ("finding", "context_finding")
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
    IDP_JOBS = Counter(
        "ai2_idp_jobs_total",
        "Processing jobs (facts, conflicts, contract graph) that ended, by status.",
        ["status"],
    )
    IDP_DURATION = Histogram(
        "ai2_idp_job_duration_seconds",
        "Wall time of one processing job: snapshot load, claim, pipeline, persist.",
        buckets=(10, 30, 60, 120, 180, 300, 450, 600, 900, 1200, 1800),
    )
    IDP_PHASE_SECONDS = Counter(
        "ai2_idp_phase_seconds_total",
        "Seconds processing jobs spent in each phase.",
        ["phase"],
    )
    IDP_LLM_CALLS = Counter(
        "ai2_idp_llm_calls_total",
        "LLM requests processing jobs sent, by pipeline operation (retries included).",
        ["operation"],
    )
    IDP_LLM_SECONDS = Counter(
        "ai2_idp_llm_seconds_total",
        "Seconds processing jobs waited on the LLM, by pipeline operation.",
        ["operation"],
    )
    IDP_TOKENS = Counter(
        "ai2_idp_tokens_total",
        "Tokens processing jobs used; input excludes cached input.",
        ["kind", "model", "type"],
    )
    IDP_COST = Counter(
        "ai2_idp_cost_usd_total",
        "Estimated USD cost of processing jobs, same price table as /query.",
        ["kind", "model"],
    )
    IDP_JOB_COST = Histogram(
        "ai2_idp_job_cost_usd",
        "Estimated USD cost of one processing job.",
        buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
    )
    IDP_FINDINGS = Counter(
        "ai2_idp_findings_total",
        "Findings (conflicts) and context findings processing jobs produced.",
        ["kind"],
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
    for state in ("ANSWERED", "INSUFFICIENT_EVIDENCE", "NEEDS_REVIEW", "FAILED"):
        QUERIES.labels(state)
    for status in ("SUCCEEDED", "FAILED", "CANCELLED"):
        IDP_JOBS.labels(status)
    for phase in _PHASES:
        IDP_PHASE_SECONDS.labels(phase)
    for operation in _OPERATIONS:
        IDP_LLM_CALLS.labels(operation)
        IDP_LLM_SECONDS.labels(operation)
    for finding_kind in _FINDING_KINDS:
        IDP_FINDINGS.labels(finding_kind)
    for kind, model in _configured_models():
        for status in ("ok", "error"):
            MODEL_CALLS.labels(kind, model, status)
        for token_type in _TOKEN_TYPES:
            TOKENS.labels(kind, model, token_type)
        COST.labels(kind, model)
        for token_type in _TOKEN_TYPES:
            IDP_TOKENS.labels(kind, model, token_type)
        IDP_COST.labels(kind, model)


def _configured_models() -> list[tuple[str, str]]:
    """``(kind, model label)`` of the models AI2 is configured to call (questions and
    processing jobs; the pair classifier may run its own model)."""
    chat = os.environ.get("AI2_LLM_MODEL") or "gpt-5.5"
    pairs = [
        ("chat", chat),
        ("chat", os.environ.get("AI2_LLM_STRONG_MODEL") or chat),
        ("chat", os.environ.get("AI2_CONTRACT_GRAPH_PAIRS_MODEL") or chat),
        ("embedding", os.environ.get("AI2_EMBEDDING_MODEL") or "text-embedding-3-small"),
    ]
    return sorted({(kind, _model(model)) for kind, model in pairs})


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


def record_idp_job(summary: dict[str, Any]) -> None:
    """Record one finished processing job from its summary (``app.pipeline.job_metrics``)."""
    if not metrics_enabled() or not isinstance(summary, dict):
        return
    status = summary.get("status")
    IDP_JOBS.labels(status if isinstance(status, str) and _STATE.match(status) else "OTHER").inc()
    duration = summary.get("duration_seconds")
    if isinstance(duration, (int, float)) and duration >= 0:
        IDP_DURATION.observe(duration)
    for phase, seconds in (summary.get("phases") or {}).items():
        if phase in _PHASES and isinstance(seconds, (int, float)) and seconds > 0:
            IDP_PHASE_SECONDS.labels(phase).inc(seconds)
    for operation, entry in (summary.get("operations") or {}).items():
        label = operation if isinstance(operation, str) and _OPERATION.match(operation) else "other"
        calls = entry.get("calls") if isinstance(entry, dict) else None
        seconds = entry.get("seconds") if isinstance(entry, dict) else None
        if isinstance(calls, (int, float)) and calls > 0:
            IDP_LLM_CALLS.labels(label).inc(calls)
        if isinstance(seconds, (int, float)) and seconds > 0:
            IDP_LLM_SECONDS.labels(label).inc(seconds)
    job_cost = 0.0
    for usage in summary.get("models") or []:
        if not isinstance(usage, dict):
            continue
        kind = usage.get("kind") if usage.get("kind") in _KINDS else "other"
        model = _model(usage.get("model"))
        for token_type in _TOKEN_TYPES:
            tokens = usage.get(token_type)
            if isinstance(tokens, (int, float)) and tokens > 0:
                IDP_TOKENS.labels(kind, model, token_type).inc(tokens)
        cost = usage.get("cost")
        if isinstance(cost, (int, float)) and cost > 0:
            IDP_COST.labels(kind, model).inc(cost)
            job_cost += cost
    if status == "SUCCEEDED" or job_cost > 0:
        IDP_JOB_COST.observe(job_cost)
    for finding_kind, count in (summary.get("findings") or {}).items():
        if finding_kind in _FINDING_KINDS and isinstance(count, int) and count > 0:
            IDP_FINDINGS.labels(finding_kind).inc(count)


__all__ = [
    "metrics_enabled",
    "record_idp_job",
    "record_model_call",
    "record_query",
    "start_metrics_server",
]
