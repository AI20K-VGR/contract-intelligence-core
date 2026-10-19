"""Process-wide totals of AI2 chat completions, for per-job cost and speed metrics.

Every ``NineRouterClient.complete_json`` adds its finished trace here, whatever
client made it (the pair classifier has its own) and whatever thread (pair
batches run in a thread pool that does not copy context variables). A job takes
:func:`snapshot` at its start and :func:`usage_since` at its end.

Exact per job when a job owns its process (``AI2_JOB_ISOLATION=process``, one
job per child, the production setting). In the in-process ``thread`` mode a
``/query`` answered meanwhile is counted with the job.
"""

from __future__ import annotations

import threading
from typing import Any

_FIELDS = ("calls", "errors", "input", "input_cached", "output", "latency_ms")
_lock = threading.Lock()
_totals: dict[str, dict[str, float]] = {}


def record_trace(trace: dict[str, Any]) -> None:
    """Add one finished ``complete_json`` trace (success or failure)."""
    model = trace.get("served_model") or trace.get("model")
    if not isinstance(model, str) or not model:
        return
    prompt = _count(trace.get("prompt_tokens"))
    cached = min(_count(trace.get("cached_tokens")), prompt)
    with _lock:
        entry = _totals.setdefault(model, dict.fromkeys(_FIELDS, 0.0))
        entry["calls"] += _count(trace.get("http_calls")) or 1
        entry["errors"] += 1 if trace.get("error_type") else 0
        entry["input"] += prompt - cached
        entry["input_cached"] += cached
        entry["output"] += _count(trace.get("completion_tokens"))
        latency = trace.get("latency_ms")
        if isinstance(latency, (int, float)) and latency > 0:
            entry["latency_ms"] += float(latency)


def snapshot() -> dict[str, dict[str, float]]:
    with _lock:
        return {model: dict(entry) for model, entry in _totals.items()}


def usage_since(mark: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    """Per-model totals added after ``mark`` (a previous :func:`snapshot`)."""
    now = snapshot()
    delta: dict[str, dict[str, float]] = {}
    for model, entry in now.items():
        before = mark.get(model, {})
        diff = {field: entry[field] - before.get(field, 0.0) for field in _FIELDS}
        if diff["calls"] > 0:
            delta[model] = diff
    return delta


def _count(value: Any) -> int:
    return value if isinstance(value, int) and value > 0 else 0


__all__ = ["record_trace", "snapshot", "usage_since"]
