"""Cost tracking for AI2 questions (``/query``): Langfuse per question, Prometheus totals.

One question is one Langfuse trace (``ai2.query``); every LLM and embedding call
it makes is a child generation with token usage and USD cost, so Langfuse sums
the cost per question, per dossier (session) and per user. The same usage and
cost also feed ``app.llm.metrics`` for Grafana; either side works without the other.

Calls are recorded only inside :func:`query_trace`: processing jobs make hundreds
of calls per dossier and are not traced here. The privacy rule is AI1's,
with AI2's own client (``app.llm.langfuse_client``; the AI2 image has no AI1
code): no question, prompt, answer or contract text, only ids, counts,
timings and token usage.
"""

from __future__ import annotations

import json
import logging
import os
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

from app.llm.langfuse_client import flush_langfuse, get_langfuse
from app.llm.metrics import metrics_enabled, record_model_call, record_query

try:
    from langfuse import propagate_attributes
except ImportError:  # pragma: no cover - get_langfuse() is None then too
    propagate_attributes = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# True while a /query is being answered; copied into worker threads with the context.
_IN_QUERY: ContextVar[bool] = ContextVar("ai2_langfuse_in_query", default=False)

# USD per 1M tokens, Standard tier (https://developers.openai.com/api/docs/models,
# checked 2026-10-19). Langfuse shows $0 for a model it cannot price, so the cost
# is computed here. AI2_LLM_PRICES_JSON adds or overrides models with the same
# shape, e.g. {"gpt-5.5": {"input": 5, "input_cached": 0.5, "output": 30}}.
_PRICES_PER_1M_USD: dict[str, dict[str, float]] = {
    "gpt-5.5": {"input": 5.00, "input_cached": 0.50, "output": 30.00},
    "text-embedding-3-small": {"input": 0.02},
}


def _prices() -> dict[str, dict[str, float]]:
    raw = os.getenv("AI2_LLM_PRICES_JSON", "").strip()
    if not raw:
        return _PRICES_PER_1M_USD
    try:
        extra = json.loads(raw)
        if not isinstance(extra, dict):
            raise ValueError("not an object")
        overrides = {
            _price_key(model): {key: float(value) for key, value in prices.items()}
            for model, prices in extra.items()
        }
    except (AttributeError, TypeError, ValueError):
        logger.warning("ai2.llm_prices_invalid AI2_LLM_PRICES_JSON is ignored")
        return _PRICES_PER_1M_USD
    return {**_PRICES_PER_1M_USD, **overrides}


def _price_key(model: str) -> str:
    """``openai/gpt-5.5`` and ``GPT-5.5`` are priced as ``gpt-5.5``."""

    return str(model).rsplit("/", 1)[-1].strip().casefold()


def _model_prices(table: dict[str, dict[str, float]], key: str) -> dict[str, float] | None:
    """Exact id first; else the longest priced id that the served snapshot extends
    (OpenAI answers ``gpt-5.5-2026-09-01`` for ``gpt-5.5``)."""

    if key in table:
        return table[key]
    bases = [base for base in table if key.startswith(base + "-")]
    return table[max(bases, key=len)] if bases else None


def cost_details(model: str | None, usage: dict[str, int]) -> dict[str, float] | None:
    """USD cost of one call from Langfuse ``usage_details``.

    ``input`` excludes the cached prompt tokens, which have their own rate;
    reasoning tokens are already inside ``output``.
    """

    prices = _model_prices(_prices(), _price_key(model or ""))
    if not prices or not usage:
        return None
    costs: dict[str, float] = {}
    for key, rate_key in (
        ("input", "input"),
        ("input_cached", "input_cached"),
        ("output", "output"),
    ):
        tokens = usage.get(key)
        if tokens:
            rate = prices.get(rate_key, prices.get("input", 0.0))
            costs[key] = tokens * rate / 1_000_000
    return {**costs, "total": sum(costs.values())} if costs else None


class QueryTrace:
    """The question being answered: its Langfuse span (``None`` when Langfuse is off)."""

    def __init__(self) -> None:
        self.span: Any | None = None
        self.state: str | None = None

    def done(self, result: dict[str, Any]) -> None:
        """Record the answer's state (as ``/query`` reports it) and its counts."""

        state = result.get("review_state") or result.get("state") or "INSUFFICIENT_EVIDENCE"
        self.state = "ANSWERED" if state == "PASS" else str(state)
        if self.span is not None:
            _update(
                self.span,
                output={
                    "state": self.state,
                    "used_llm": bool(result.get("used_llm", False)),
                    "citations": len(result.get("citations") or []),
                },
            )


@contextmanager
def query_trace(
    *,
    dossier_id: str,
    tenant_id: str,
    actor_id: str | None,
    task_type: str | None,
    query_chars: int,
) -> Iterator[QueryTrace]:
    """One Langfuse trace and one Prometheus count per question; no-op when both are off."""

    trace = QueryTrace()
    client = get_langfuse() if propagate_attributes is not None else None
    metered = metrics_enabled()
    if client is None and not metered:
        yield trace
        return
    marker = _IN_QUERY.set(True)
    started = time.perf_counter()
    try:
        if client is None:
            yield trace
        else:
            with _contained_errors() as caught:
                with client.start_as_current_observation(
                    name="ai2.query",
                    as_type="span",
                    input={"query_chars": query_chars, "task_type": task_type},
                    metadata={"tenant_id": tenant_id, "dossier_id": dossier_id},
                ) as span:
                    trace.span = span
                    with propagate_attributes(
                        trace_name="ai2.query",
                        session_id=dossier_id,
                        user_id=actor_id or None,
                        tags=["ai2", "query"],
                        metadata={"tenant_id": tenant_id, "dossier_id": dossier_id},
                    ):
                        with caught.inside(span):
                            yield trace
    finally:
        _IN_QUERY.reset(marker)
        record_query(trace.state or "FAILED", time.perf_counter() - started)


class _Generation:
    """A question's call: the same usage and cost go to Prometheus and to Langfuse."""

    __slots__ = ("_inner", "_kind", "_model")

    def __init__(self, inner: Any | None, kind: str, model: str | None) -> None:
        self._inner = inner
        self._kind = kind
        self._model = model

    def update(self, **fields: Any) -> None:
        # Prometheus keys by the configured model, so the series made at startup is
        # the one that grows; the served snapshot (gpt-5.5-2026-04-23) goes to Langfuse.
        record_model_call(
            self._kind,
            self._model or fields.get("model"),
            fields.get("usage_details"),
            fields.get("cost_details"),
            failed=fields.get("level") == "ERROR",
        )
        if self._inner is not None:
            self._inner.update(**fields)


@contextmanager
def llm_generation(
    name: str,
    *,
    model: str | None,
    as_type: str = "generation",
    metadata: dict[str, Any] | None = None,
) -> Iterator[Any | None]:
    """A child call of the current question, or ``None`` outside one."""

    if not _IN_QUERY.get():
        yield None
        return
    kind = "embedding" if as_type == "embedding" else "chat"
    client = get_langfuse()
    if client is None:
        yield _Generation(None, kind, model) if metrics_enabled() else None
        return
    with _contained_errors() as caught:
        with client.start_as_current_observation(
            name=name, as_type=as_type, model=model, metadata=metadata
        ) as generation:
            # record_completion/record_embedding already mark the call as an error.
            with caught.inside(generation, mark=False):
                yield _Generation(generation, kind, model)


class _ErrorFence:
    """Keeps an exception from crossing a Langfuse observation's context manager.

    The SDK (OpenTelemetry) records a crossing exception's message, stacktrace and
    status description, and a provider error can quote the request (contract text).
    Inside the observation only the error type is recorded; the exception itself is
    re-raised unchanged once the observation has closed (PR #135 review, P1).
    """

    def __init__(self) -> None:
        self.error: Exception | None = None

    @contextmanager
    def inside(self, observation: Any, *, mark: bool = True) -> Iterator[None]:
        try:
            yield
        except Exception as exc:
            self.error = exc
            if mark:
                _update(observation, level="ERROR", status_message=type(exc).__name__)


@contextmanager
def _contained_errors() -> Iterator[_ErrorFence]:
    fence = _ErrorFence()
    yield fence
    if fence.error is not None:
        raise fence.error


def record_completion(generation: Any | None, trace: dict[str, Any]) -> None:
    """Report one ``NineRouterClient.complete_json`` call from its trace dict."""

    if generation is None or not trace:
        return
    prompt = trace.get("prompt_tokens")
    completion = trace.get("completion_tokens")
    cached = trace.get("cached_tokens") or 0
    usage: dict[str, int] = {}
    if isinstance(prompt, int):
        usage["input"] = max(0, prompt - cached)
        if cached:
            usage["input_cached"] = cached
    if isinstance(completion, int):
        usage["output"] = completion
    if isinstance(trace.get("total_tokens"), int):
        usage["total"] = trace["total_tokens"]
    model = trace.get("served_model") or trace.get("model")
    error = trace.get("error_type")
    metadata = {
        key: trace[key]
        for key in (
            "strong",
            "http_calls",
            "latency_ms",
            "finish_reason",
            "truncated",
            "reasoning_tokens",
            "fallback_without_json_format",
            "system_chars",
            "user_chars",
            "response_chars",
            # Not request_digest: a fixed hash of the prompt (contract or question
            # text) links repeated calls and can be guessed for short inputs.
            "error_type",
        )
        if key in trace
    }
    _update(
        generation,
        model=model,
        usage_details=usage or None,
        cost_details=cost_details(model, usage),
        metadata=metadata,
        level="ERROR" if error else None,
        status_message=error,
    )


def record_embedding(
    generation: Any | None, model: str, response: Any = None, error: BaseException | None = None
) -> None:
    """Report one embeddings request (the question's vector for recall)."""

    if generation is None:
        return
    usage_source = getattr(response, "usage", None)
    tokens = getattr(usage_source, "prompt_tokens", None)
    if tokens is None and isinstance(usage_source, dict):
        tokens = usage_source.get("prompt_tokens")
    usage = {"input": tokens, "total": tokens} if isinstance(tokens, int) else {}
    _update(
        generation,
        model=model,
        usage_details=usage or None,
        cost_details=cost_details(model, usage),
        level="ERROR" if error else None,
        status_message=type(error).__name__ if error else None,
    )


def _update(generation: Any, **fields: Any) -> None:
    try:
        generation.update(**{key: value for key, value in fields.items() if value is not None})
    except Exception:
        # Observability must never fail a question.
        logger.exception("ai2.langfuse_update_failed")


__all__ = [
    "QueryTrace",
    "cost_details",
    "flush_langfuse",
    "llm_generation",
    "query_trace",
    "record_completion",
    "record_embedding",
]
