"""One processing job's cost and speed summary for ``app.llm.metrics.record_idp_job``.

Numbers and bounded labels only (status, phase, operation, model): no dossier,
tenant, document or contract text. The summary is a plain dict so a job child
can send it to the API process over its pipe.
"""

from __future__ import annotations

import os
from typing import Any

from app.llm.observability import cost_details

_PHASES = {
    "snapshot_load_ms": "snapshot_load",
    "claim_ms": "claim",
    "pipeline_ms": "pipeline",
    "persist_ms": "persist",
}


def build_idp_summary(
    *,
    status: str | None,
    timing: dict[str, int | None],
    llm_timing: dict[str, Any] | None = None,
    chat_usage: dict[str, dict[str, float]] | None = None,
    embedding_tokens: int = 0,
    wire: dict[str, Any] | None = None,
) -> dict[str, Any]:
    phases = {
        name: timing[key] / 1000
        for key, name in _PHASES.items()
        if isinstance(timing.get(key), (int, float))
    }
    operations = {
        operation: {
            "calls": int(entry.get("llm_calls") or 0),
            "seconds": float(entry.get("llm_ms_total") or 0) / 1000,
        }
        for operation, entry in ((llm_timing or {}).get("by_operation") or {}).items()
        if isinstance(entry, dict)
    }
    models: list[dict[str, Any]] = []
    for model, entry in sorted((chat_usage or {}).items()):
        usage = {key: int(entry.get(key) or 0) for key in ("input", "input_cached", "output")}
        cost = cost_details(model, {key: value for key, value in usage.items() if value})
        models.append(
            {"kind": "chat", "model": model, **usage, "cost": (cost or {}).get("total", 0.0)}
        )
    if embedding_tokens > 0:
        model = os.getenv("AI2_EMBEDDING_MODEL") or "text-embedding-3-small"
        cost = cost_details(model, {"input": embedding_tokens})
        models.append(
            {
                "kind": "embedding",
                "model": model,
                "input": embedding_tokens,
                "input_cached": 0,
                "output": 0,
                "cost": (cost or {}).get("total", 0.0),
            }
        )
    result = (wire or {}).get("result") if isinstance(wire, dict) else None
    findings = {
        "finding": len(result.get("findings") or []) if isinstance(result, dict) else 0,
        "context_finding": len(result.get("context_findings") or [])
        if isinstance(result, dict)
        else 0,
    }
    return {
        "status": status,
        "duration_seconds": sum(phases.values()) if phases else None,
        "phases": phases,
        "operations": operations,
        "models": models,
        "findings": findings,
    }


__all__ = ["build_idp_summary"]
