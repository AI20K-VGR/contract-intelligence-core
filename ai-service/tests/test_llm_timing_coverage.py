"""P1: per-attempt LLM timing reaches coverage.llm_timing without touching snapshot()."""

from __future__ import annotations

import threading
from types import SimpleNamespace
from typing import Any

import pytest
from test_st067_bounded_jobs import EchoLLM, FakeClock, RaisingLLM, _rate_limited, _runtime

from app.llm.client import NineRouterClient
from app.pipeline.idp import run_idp
from app.pipeline.runtime import ProcessingRuntime
from fixtures.llm_units_snapshot import llm_units_envelope, llm_units_record

_SNAPSHOT_KEYS = {
    "egress_allowed",
    "use_vector",
    "max_processing_seconds",
    "max_llm_calls",
    "max_embedding_tokens",
    "llm_calls_used",
    "llm_calls_remaining",
    "embedding_tokens_used",
    "embedding_tokens_remaining",
    "fallback_count",
}


def test_snapshot_keys_unchanged_after_llm_call() -> None:
    runtime = ProcessingRuntime(egress_allowed=True, max_llm_calls=2)
    assert runtime.complete_json(EchoLLM(), "s", "raw=x", operation="pairs") == {"normalized": "x"}
    assert set(runtime.snapshot()) == _SNAPSHOT_KEYS


def test_llm_timing_present_only_after_llm_call() -> None:
    runtime = ProcessingRuntime(egress_allowed=True, max_llm_calls=10, max_processing_seconds=60)
    result = run_idp(llm_units_record(), llm_units_envelope(), llm=EchoLLM(), runtime=runtime)
    timing = result.contribution.coverage["llm_timing"]
    assert runtime.llm_calls_used >= 1
    assert timing["llm_calls"] == runtime.llm_calls_used
    assert sum(op["llm_calls"] for op in timing["by_operation"].values()) == timing["llm_calls"]
    assert isinstance(timing["llm_ms_total"], int)
    assert timing["cached_tokens"] is None

    denied = ProcessingRuntime(egress_allowed=False, max_llm_calls=10, max_processing_seconds=60)
    result = run_idp(llm_units_record(), llm_units_envelope(), llm=EchoLLM(), runtime=denied)
    assert "llm_timing" not in result.contribution.coverage


def test_runtime_times_failed_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI2_LLM_MAX_RETRIES", "3")
    clock = FakeClock()
    runtime = _runtime(clock, max_llm_calls=10, max_processing_seconds=60)
    client = RaisingLLM(lambda: _rate_limited(retry_after="1"))

    assert runtime.complete_json(client, "s", "u", operation="pairs") is None

    timing = runtime.llm_timing()
    assert client.calls == 3
    assert timing["llm_calls"] == 3
    assert timing["by_operation"]["pairs"]["llm_calls"] == 3


def test_budget_refusal_is_not_timed() -> None:
    runtime = ProcessingRuntime(egress_allowed=True, max_llm_calls=0)
    assert runtime.complete_json(EchoLLM(), "s", "raw=x") is None
    assert runtime.llm_timing() is None


def test_llm_timing_accumulation_is_thread_safe() -> None:
    runtime = ProcessingRuntime()
    barrier = threading.Barrier(8)

    def work() -> None:
        barrier.wait()
        for _ in range(50):
            runtime._record_llm_attempt("pairs", 2.0, 1, {"cached_tokens": 1})

    threads = [threading.Thread(target=work) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    timing = runtime.llm_timing()
    assert timing["llm_calls"] == 400
    assert timing["llm_ms_total"] == 800
    assert timing["cached_tokens"] == 400
    assert timing["by_operation"]["pairs"] == {
        "llm_calls": 400,
        "llm_ms_total": 800,
        "llm_ms_max": 2,
        "cached_tokens": 400,
    }


def _client_with_usage(usage: Any) -> NineRouterClient:
    client = NineRouterClient(api_key="sk-test", model="gpt-5.5")

    def create(**_kwargs: object) -> SimpleNamespace:
        choice = SimpleNamespace(message=SimpleNamespace(content='{"ok": 1}'), finish_reason="stop")
        return SimpleNamespace(choices=[choice], usage=usage, model="gpt-5.5")

    client._client.chat.completions.create = create  # type: ignore[method-assign]
    return client


def test_trace_records_cached_tokens_when_reported() -> None:
    reported = SimpleNamespace(
        prompt_tokens=2000,
        completion_tokens=10,
        total_tokens=2010,
        prompt_tokens_details=SimpleNamespace(cached_tokens=1024),
    )
    client = _client_with_usage(reported)
    assert client.complete_json("Return JSON.", "u") == {"ok": 1}
    assert client.traces[-1]["cached_tokens"] == 1024

    silent = _client_with_usage(
        SimpleNamespace(prompt_tokens=5, completion_tokens=1, total_tokens=6)
    )
    assert silent.complete_json("Return JSON.", "u") == {"ok": 1}
    assert "cached_tokens" not in silent.traces[-1]


class _StaleTraceLLM(EchoLLM):
    """Carries a trace from an earlier call and appends none for the current one."""

    def __init__(self) -> None:
        super().__init__()
        self.traces = [{"latency_ms": 98765.4, "http_calls": 1, "model": "stale"}]


def test_log_call_ignores_stale_trace(caplog: pytest.LogCaptureFixture) -> None:
    runtime = ProcessingRuntime(egress_allowed=True, max_llm_calls=2)
    with caplog.at_level("INFO", logger="app.pipeline.runtime"):
        assert runtime.complete_json(_StaleTraceLLM(), "s", "raw=x", operation="pairs")

    line = next(r.getMessage() for r in caplog.records if "ai2.llm_call " in r.getMessage())
    assert "98765.4" not in line
    assert "latency_ms=None" in line
