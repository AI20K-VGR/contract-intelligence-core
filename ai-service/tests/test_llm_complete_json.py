"""NineRouterClient.complete_json must be a real method. A nested function is an AttributeError."""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest
from openai import BadRequestError

from app.llm.client import LLMEmptyResponseError, NineRouterClient
from app.pipeline.runtime import ProcessingRuntime


def test_runtime_normalizes_through_complete_json() -> None:
    client = NineRouterClient(api_key="sk-test", model="gh/gpt-4o-mini")

    def create(**_kwargs: object) -> SimpleNamespace:
        message = SimpleNamespace(
            content='{"normalized": "CONG TY CO PHAN PHUC THINH", "unit": null}'
        )
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


@pytest.mark.parametrize(
    ("model", "temperature_expected", "token_limit_key"),
    [
        ("gpt-5.5", False, "max_completion_tokens"),
        ("openai/gpt-5.5", False, "max_completion_tokens"),
        ("gh/gpt-4o-mini", True, "max_tokens"),
    ],
)
def test_reasoning_models_omit_unsupported_temperature(
    model: str, temperature_expected: bool, token_limit_key: str
) -> None:
    client = NineRouterClient(api_key="sk-test", model=model)
    captured: dict[str, object] = {}

    def create(**kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return SimpleNamespace(
            model="gpt-5.5-2026-04-23",
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok":true}'))],
            usage=None,
        )

    client._client.chat.completions.create = create  # type: ignore[method-assign]
    assert client.complete_json("system", "user", max_output_tokens=64) == {"ok": True}
    assert captured[token_limit_key] == 64
    other_token_limit_key = (
        "max_tokens" if token_limit_key == "max_completion_tokens" else "max_completion_tokens"
    )
    assert other_token_limit_key not in captured
    if temperature_expected:
        assert captured["temperature"] == 0
    else:
        assert "temperature" not in captured


@pytest.mark.parametrize("fallback", [False, True])
def test_trace_records_served_model(fallback: bool) -> None:
    client = NineRouterClient(api_key="sk-test", model="gh/gpt-4o-mini")
    calls = 0

    def create(**_kwargs: object) -> SimpleNamespace:
        nonlocal calls
        calls += 1
        if fallback and calls == 1:
            response = httpx.Response(400, request=httpx.Request("POST", "http://example.test"))
            raise BadRequestError(
                "unsupported response_format", response=response, body={"param": "response_format"}
            )
        return SimpleNamespace(
            model="anthropic/claude-x",
            usage=None,
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))],
        )

    client._client.chat.completions.create = create
    assert client.complete_json("system", "user") == {"ok": True}
    assert client.traces[-1]["model"] == "gh/gpt-4o-mini"
    assert client.traces[-1]["served_model"] == "anthropic/claude-x"
    assert client.traces[-1]["fallback_without_json_format"] is fallback


def test_parse_failure_records_safe_error_trace_with_usage() -> None:
    client = NineRouterClient(api_key="sk-test", model="ag/claude-sonnet-4-6")
    usage = SimpleNamespace(prompt_tokens=11, completion_tokens=7, total_tokens=18)

    def create(**_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(
            model="anthropic/claude-sonnet-4-6",
            usage=usage,
            choices=[SimpleNamespace(message=SimpleNamespace(content="{bad-json}"))],
        )

    client._client.chat.completions.create = create
    with pytest.raises(json.JSONDecodeError):
        client.complete_json("system", "user")
    trace = client.traces[-1]
    assert trace["error_type"] == "ResponseParseError"
    assert trace["served_model"] == "anthropic/claude-sonnet-4-6"
    assert (
        trace["prompt_tokens"] == 11
        and trace["completion_tokens"] == 7
        and trace["total_tokens"] == 18
    )


def test_empty_response_fails_closed_with_safe_trace() -> None:
    client = NineRouterClient(api_key="sk-test", model="gemini/gemini-3.8-flash")
    usage = SimpleNamespace(prompt_tokens=11, completion_tokens=0, total_tokens=11)

    def create(**_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(
            model="gemini-3.8-flash",
            usage=usage,
            choices=[SimpleNamespace(message=SimpleNamespace(content=""))],
        )

    client._client.chat.completions.create = create
    with pytest.raises(LLMEmptyResponseError):
        client.complete_json("system", "user")
    trace = client.traces[-1]
    assert trace["error_type"] == "EmptyResponseError"
    assert trace["response_empty"] is True
    assert trace["served_model"] == "gemini-3.8-flash"
    assert trace["completion_tokens"] == 0 and trace["total_tokens"] == 11


def test_runtime_snapshot_reports_remaining_budgets_without_payload_data() -> None:
    runtime = ProcessingRuntime(max_llm_calls=3, max_embedding_tokens=20)
    runtime.llm_calls_used = 2
    runtime.embedding_tokens_used = 7

    snapshot = runtime.snapshot()

    assert snapshot["llm_calls_remaining"] == 1
    assert snapshot["embedding_tokens_remaining"] == 13


def _capture_messages(client: NineRouterClient) -> list[dict[str, object]]:
    requests: list[dict[str, object]] = []

    def create(**kwargs: object) -> SimpleNamespace:
        requests.append(kwargs)
        return SimpleNamespace(
            model="gpt-5.5-2026-04-23",
            usage=None,
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"slots": []}'))],
        )

    client._client.chat.completions.create = create  # type: ignore[method-assign]
    return requests


def test_json_mode_request_always_names_json() -> None:
    # OpenAI answers 400 "'messages' must contain the word 'json'" for
    # response_format=json_object; a Vietnamese prompt naming only {"slots": ...} hit it.
    client = NineRouterClient(api_key="sk-test", model="gpt-5.5")
    requests = _capture_messages(client)

    assert client.complete_json('Chỉ trả {"slots": []}.', '{"frame": "f-1"}') == {"slots": []}

    assert requests[0]["response_format"] == {"type": "json_object"}
    text = " ".join(str(m["content"]) for m in requests[0]["messages"])  # type: ignore[union-attr]
    assert "json" in text.casefold()


def test_prompt_that_already_names_json_is_sent_unchanged() -> None:
    client = NineRouterClient(api_key="sk-test", model="gpt-5.5")
    requests = _capture_messages(client)

    client.complete_json("Return JSON {slots}.", "user")

    assert requests[0]["messages"] == [
        {"role": "system", "content": "Return JSON {slots}."},
        {"role": "user", "content": "user"},
    ]


def test_runtime_logs_provider_rejection_without_payload(caplog: pytest.LogCaptureFixture) -> None:
    client = NineRouterClient(api_key="sk-test", model="gpt-5.5")

    def create(**_kwargs: object) -> SimpleNamespace:
        response = httpx.Response(400, request=httpx.Request("POST", "http://example.test"))
        raise BadRequestError(
            "bad request",
            response=response,
            body={"error": {"param": "messages", "code": None, "message": "secret-raw-text"}},
        )

    client._client.chat.completions.create = create  # type: ignore[method-assign]
    runtime = ProcessingRuntime(egress_allowed=True, max_llm_calls=2)

    with caplog.at_level("WARNING", logger="app.pipeline.runtime"):
        assert runtime.complete_json(client, "Return JSON.", "raw=private") is None

    line = next(r.getMessage() for r in caplog.records if "ai2.llm_call_failed" in r.getMessage())
    assert (
        "error=BadRequestError" in line and "http_status=400" in line and "param=messages" in line
    )
    assert "secret-raw-text" not in line and "raw=private" not in line


def _quota_client(code: str, calls: list) -> NineRouterClient:
    from openai import RateLimitError

    client = NineRouterClient(api_key="sk-test", model="gpt-5.5")

    def create(**_kwargs: object) -> SimpleNamespace:
        calls.append(1)
        response = httpx.Response(429, request=httpx.Request("POST", "http://example.test"))
        raise RateLimitError(
            "429", response=response, body={"error": {"code": code, "message": "x"}}
        )

    client._client.chat.completions.create = create  # type: ignore[method-assign]
    return client


@pytest.mark.parametrize("code", ["credit_balance_exhausted", "insufficient_quota"])
def test_exhausted_quota_fails_fast_and_stops_the_job(code: str) -> None:
    # Observed live: 429 code=credit_balance_exhausted was retried 3x per call as a rate
    # limit, burning the whole call budget and reporting "quá tải" instead of the cause.
    calls: list = []
    client = _quota_client(code, calls)
    runtime = ProcessingRuntime(egress_allowed=True, max_llm_calls=20)

    assert runtime.complete_json(client, "Return JSON.", "u") is None
    assert len(calls) == 1
    assert [issue[0] for issue in runtime.issues] == ["LLM_QUOTA_EXHAUSTED"]
    assert runtime.complete_json(client, "Return JSON.", "u") is None
    assert len(calls) == 1  # later calls in the same job send nothing


def test_plain_rate_limit_is_still_retried() -> None:
    calls: list = []
    client = _quota_client("rate_limit_exceeded", calls)
    runtime = ProcessingRuntime(egress_allowed=True, max_llm_calls=20)
    runtime.sleep = lambda _seconds: None  # type: ignore[method-assign]

    assert runtime.complete_json(client, "Return JSON.", "u") is None
    assert len(calls) == runtime.max_attempts
    assert runtime.issues[0][0] == "LLM_RATE_LIMITED"


def test_provider_failure_log_names_the_calling_stage(caplog: pytest.LogCaptureFixture) -> None:
    # LLM_TIMEOUT showed up intermittently but the log could not say which stage timed out.
    calls: list = []
    client = _quota_client("rate_limit_exceeded", calls)
    runtime = ProcessingRuntime(egress_allowed=True, max_llm_calls=1)
    with caplog.at_level("WARNING", logger="app.pipeline.runtime"):
        runtime.complete_json(client, "Return JSON.", "u", operation="pairs")
    assert any("operation=pairs" in r.getMessage() for r in caplog.records)


def test_pipeline_call_sites_label_their_stage() -> None:
    import inspect

    from app.pipeline import fact, frame_context, table, tenant_aliases
    from app.pipeline.contract_graph import pair_classifier

    for module, label in (
        (pair_classifier, "pairs"),
        (frame_context, "slot_context"),
        (tenant_aliases, "alias"),
        (fact, "fact_normalize"),
        (table, "table"),
    ):
        assert f'operation="{label}"' in inspect.getsource(module), module.__name__


def test_runtime_logs_each_successful_call_with_timing_and_tokens(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = NineRouterClient(api_key="sk-test", model="gpt-5.5")

    def create(**_kwargs: object) -> SimpleNamespace:
        usage = SimpleNamespace(
            prompt_tokens=120,
            completion_tokens=30,
            total_tokens=150,
            completion_tokens_details=SimpleNamespace(reasoning_tokens=12),
        )
        choice = SimpleNamespace(
            message=SimpleNamespace(content='{"ok": true}'), finish_reason="stop"
        )
        return SimpleNamespace(choices=[choice], usage=usage, model="gpt-5.5-2026")

    client._client.chat.completions.create = create  # type: ignore[method-assign]
    runtime = ProcessingRuntime(egress_allowed=True, max_llm_calls=2)

    with caplog.at_level("INFO", logger="app.pipeline.runtime"):
        assert runtime.complete_json(
            client, "Return JSON.", "raw=private", operation="slot_context"
        ) == {"ok": True}

    line = next(r.getMessage() for r in caplog.records if "ai2.llm_call " in r.getMessage())
    assert "operation=slot_context" in line and "served_model=gpt-5.5-2026" in line
    assert "prompt_tokens=120" in line and "reasoning_tokens=12" in line and "latency_ms=" in line
    assert "raw=private" not in line


def _capturing_client(model: str, sent: list[dict]) -> NineRouterClient:
    client = NineRouterClient(api_key="sk-test", model=model)

    def create(**kwargs: object) -> SimpleNamespace:
        sent.append(kwargs)
        choice = SimpleNamespace(
            message=SimpleNamespace(content='{"ok": true}'), finish_reason="stop"
        )
        return SimpleNamespace(choices=[choice], usage=None, model=model)

    client._client.chat.completions.create = create  # type: ignore[method-assign]
    return client


@pytest.mark.parametrize(
    ("model", "operation", "expected"),
    [
        ("gpt-5.5", "slot_context", "low"),
        ("openai/gpt-5.5", "alias", "low"),
        ("gpt-5.5", "pairs", None),  # classifier keeps the default reasoning
        ("gpt-4o-mini", "slot_context", None),  # not a reasoning model
    ],
)
def test_light_reasoning_effort_only_for_span_picking_on_gpt5(
    monkeypatch, model, operation, expected
):
    monkeypatch.setenv("AI2_LLM_LIGHT_REASONING_EFFORT", "low")
    sent: list[dict] = []
    runtime = ProcessingRuntime(egress_allowed=True, max_llm_calls=2)
    runtime.complete_json(_capturing_client(model, sent), "Return JSON.", "u", operation=operation)
    assert sent[0].get("reasoning_effort") == expected


def test_reasoning_effort_is_not_sent_when_unset(monkeypatch):
    monkeypatch.delenv("AI2_LLM_LIGHT_REASONING_EFFORT", raising=False)
    sent: list[dict] = []
    runtime = ProcessingRuntime(egress_allowed=True, max_llm_calls=2)
    runtime.complete_json(
        _capturing_client("gpt-5.5", sent), "Return JSON.", "u", operation="slot_context"
    )
    assert "reasoning_effort" not in sent[0]
