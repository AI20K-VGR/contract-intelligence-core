"""NineRouterClient.complete_json must be a real method. A nested function is an AttributeError."""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from openai import BadRequestError

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


@pytest.mark.parametrize("fallback", [False, True])
def test_trace_records_served_model(fallback: bool) -> None:
    client = NineRouterClient(api_key="sk-test", model="gh/gpt-4o-mini")
    calls = 0

    def create(**_kwargs: object) -> SimpleNamespace:
        nonlocal calls
        calls += 1
        if fallback and calls == 1:
            response = httpx.Response(400, request=httpx.Request("POST", "http://example.test"))
            raise BadRequestError("unsupported response_format", response=response,
                                  body={"param": "response_format"})
        return SimpleNamespace(model="anthropic/claude-x", usage=None,
                               choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))])

    client._client.chat.completions.create = create
    assert client.complete_json("system", "user") == {"ok": True}
    assert client.traces[-1]["model"] == "gh/gpt-4o-mini"
    assert client.traces[-1]["served_model"] == "anthropic/claude-x"
    assert client.traces[-1]["fallback_without_json_format"] is fallback
