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
