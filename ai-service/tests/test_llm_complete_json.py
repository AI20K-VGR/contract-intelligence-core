"""NineRouterClient.complete_json must be a real method. A nested function is an AttributeError."""

from __future__ import annotations

from types import SimpleNamespace

from app.llm.client import NineRouterClient
from app.pipeline.runtime import ProcessingRuntime


def test_runtime_normalizes_through_complete_json() -> None:
    client = NineRouterClient(api_key="sk-test", model="gh/gpt-4o-mini")

    def create(**_kwargs: object) -> SimpleNamespace:
        message = SimpleNamespace(content='{"normalized": "CONG TY CO PHAN PHUC THINH", "unit": null}')
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None)

    client._client.chat.completions.create = create  # type: ignore[method-assign]
    runtime = ProcessingRuntime(egress_allowed=True, max_llm_calls=2)
    data = runtime.complete_json(
        client,
        "Normalize a contract field. Return JSON {normalized, unit}.",
        "raw=CÔNG TY CỔ PHẦN PHÚC THỊNH",
    )
    assert data == {"normalized": "CONG TY CO PHAN PHUC THINH", "unit": None}
    assert runtime.issues == []
    assert runtime.llm_calls_used == 1
    trace = client.traces[-1]
    assert trace["trace_id"]
    assert trace["http_calls"] == 1
    assert "raw=" not in str(trace)


def test_runtime_snapshot_reports_remaining_budgets_without_payload_data() -> None:
    runtime = ProcessingRuntime(max_llm_calls=3, max_embedding_tokens=20)
    runtime.llm_calls_used = 2
    runtime.embedding_tokens_used = 7

    snapshot = runtime.snapshot()

    assert snapshot["llm_calls_remaining"] == 1
    assert snapshot["embedding_tokens_remaining"] == 13
