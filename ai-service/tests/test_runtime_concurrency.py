"""P2: ProcessingRuntime/NineRouterClient state shared by parallel pairs batches."""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace
from typing import Any

import httpx
import openai
import pytest
from openai import BadRequestError

from app.llm.client import NineRouterClient
from app.pipeline import runtime as runtime_module
from app.pipeline.runtime import ISSUE_MESSAGES_VI, LLMRequestCancelled, ProcessingRuntime

_REQ = httpx.Request("POST", "http://router.test/v1/chat/completions")
JOIN_SECONDS = 5.0


def _runtime(**kw: Any) -> ProcessingRuntime:
    kw.setdefault("egress_allowed", True)
    kw.setdefault("max_llm_calls", 20)
    return ProcessingRuntime(**kw)


def _run_threads(target, n: int) -> None:
    threads = [threading.Thread(target=target, daemon=True) for _ in range(n)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(JOIN_SECONDS)
    # A nested lock acquisition would deadlock: every thread must finish in time.
    assert not any(thread.is_alive() for thread in threads)


class _SlowContains(list):
    """Widens the check-then-append window of ``add_issue``."""

    def __contains__(self, item: object) -> bool:
        found = list.__contains__(self, item)
        time.sleep(0.01)
        return found


class _Echo:
    def __init__(self) -> None:
        self.traces: list[dict[str, Any]] = []

    def configured(self) -> bool:
        return True

    def complete_json(self, *_a: Any, **_k: Any) -> dict[str, Any]:
        return {"ok": True}


class _Unavailable:
    def __init__(self) -> None:
        self.calls = 0
        self.traces: list[dict[str, Any]] = []

    def configured(self) -> bool:
        return True

    def complete_json(self, *_a: Any, **_k: Any) -> dict[str, Any]:
        self.calls += 1
        raise openai.InternalServerError(
            "overloaded", response=httpx.Response(503, request=_REQ), body=None
        )


# RC1
def test_fall_back_is_atomic_across_threads():
    runtime = _runtime()
    runtime.issues = _SlowContains()
    barrier = threading.Barrier(8)

    def worker() -> None:
        barrier.wait()
        runtime._fall_back("LLM_UNAVAILABLE")

    _run_threads(worker, 8)
    assert list(runtime.issues) == [("LLM_UNAVAILABLE", ISSUE_MESSAGES_VI["LLM_UNAVAILABLE"])]
    assert runtime.fallback_count == 8


# RC2
def test_reserve_does_not_block_on_global_provider_exhausted():
    runtime = _runtime()
    runtime.provider_exhausted = True
    reserved: list[int] = []
    deadline = runtime.clock() + 30
    runtime._reserve_http_request(deadline, threading.Event(), reserved, lambda: False)
    assert reserved == [1] and runtime.llm_calls_used == 1
    # Only the batch's own abort predicate stops a retry.
    with pytest.raises(LLMRequestCancelled):
        runtime._reserve_http_request(deadline, threading.Event(), reserved, lambda: True)
    assert reserved == [1] and runtime.llm_calls_used == 1


def test_reserve_checks_deadline_and_cancel_before_abort_and_budget():
    runtime = _runtime(max_llm_calls=0)
    deadline = runtime.clock() + 30
    cancelled = threading.Event()
    cancelled.set()
    with pytest.raises(TimeoutError):
        runtime._reserve_http_request(deadline, cancelled, [], lambda: True)
    with pytest.raises(LLMRequestCancelled):
        runtime._reserve_http_request(deadline, threading.Event(), [], lambda: True)


# RC3
def test_abort_returns_none_without_issue_and_stops_retries():
    slept: list[float] = []
    state = {"abort": False}

    def sleep(seconds: float) -> None:
        slept.append(seconds)
        state["abort"] = True  # another batch failed while this one waited

    runtime = _runtime(sleep=sleep, jitter=lambda: 0.0)
    client = _Unavailable()
    result = runtime.complete_json(
        client, "s", "u", operation="pairs", abort=lambda: state["abort"]
    )
    assert result is None
    assert client.calls == 1 and slept == [0.5]
    assert runtime.issues == [] and runtime.fallback_count == 0
    assert runtime.llm_calls_used == 1


def test_abort_already_set_sends_nothing():
    runtime = _runtime()
    client = _Unavailable()
    assert runtime.complete_json(client, "s", "u", abort=lambda: True) is None
    assert client.calls == 0 and runtime.llm_calls_used == 0 and runtime.issues == []


# RC4
def test_issue_sink_collects_fallbacks_until_commit():
    runtime = _runtime(max_attempts=1)
    sink: list[tuple[str, str]] = []
    assert runtime.complete_json(_Unavailable(), "s", "u", issue_sink=sink) is None
    assert runtime.issues == [] and runtime.fallback_count == 0
    assert sink == [("LLM_UNAVAILABLE", ISSUE_MESSAGES_VI["LLM_UNAVAILABLE"])]
    runtime.commit_issues(sink)
    runtime.commit_issues(sink)
    assert runtime.issues == sink and runtime.fallback_count == 2


def test_issue_sink_receives_budget_and_egress_fallbacks():
    sink: list[tuple[str, str]] = []
    runtime = _runtime(max_llm_calls=0)
    assert runtime.complete_json(_Echo(), "s", "u", issue_sink=sink) is None
    assert [code for code, _ in sink] == ["LLM_BUDGET_EXCEEDED"]
    sink.clear()
    runtime = _runtime(egress_allowed=False)
    assert runtime.complete_json(_Echo(), "s", "u", issue_sink=sink) is None
    assert [code for code, _ in sink] == ["EGRESS_DENIED"] and runtime.issues == []


def test_default_complete_json_still_writes_runtime_issues():
    runtime = _runtime(max_attempts=1)
    assert runtime.complete_json(_Unavailable(), "s", "u") is None
    assert [code for code, _ in runtime.issues] == ["LLM_UNAVAILABLE"]
    assert runtime.fallback_count == 1


# RC5
@pytest.mark.parametrize(
    ("retry_after", "jitter", "expected"),
    [(None, 0.0, 0.5), (None, 1.0, 0.75), ("2", 0.0, 2.0), ("2", 0.5, 2.5), ("10", 1.0, 11.0)],
)
def test_backoff_jitter_formula(retry_after, jitter, expected):
    slept: list[float] = []
    headers = {"retry-after": retry_after} if retry_after else {}

    class Limited(_Unavailable):
        def complete_json(self, *_a: Any, **_k: Any) -> dict[str, Any]:
            self.calls += 1
            raise openai.RateLimitError(
                "slow down", response=httpx.Response(429, request=_REQ, headers=headers), body=None
            )

    runtime = _runtime(max_attempts=2, sleep=slept.append, jitter=lambda: jitter)
    runtime.complete_json(Limited(), "s", "u")
    assert slept == [pytest.approx(expected)]


def test_runtime_jitter_defaults_to_random():
    assert ProcessingRuntime().jitter is runtime_module.random.random


# RC6
def test_last_http_calls_is_per_call_under_concurrency():
    client = NineRouterClient(base_url="http://router.test/v1", api_key="k", model="gpt-test")
    b_entered, a_done = threading.Event(), threading.Event()
    ok = SimpleNamespace(
        model="gpt-test",
        usage=None,
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))],
    )

    def create(**kwargs: Any) -> Any:
        if kwargs["messages"][-1]["content"] == "B":
            b_entered.set()
            assert a_done.wait(JOIN_SECONDS)
            return ok
        if "response_format" in kwargs:
            raise BadRequestError(
                "unsupported response_format",
                response=httpx.Response(400, request=_REQ),
                body={"param": "response_format"},
            )
        return ok

    client._client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    thread_b = threading.Thread(target=client.complete_json, args=("json", "B"), daemon=True)
    thread_b.start()
    assert b_entered.wait(JOIN_SECONDS)
    client.complete_json("json", "A")  # format fallback: 2 requests
    a_done.set()
    thread_b.join(JOIN_SECONDS)
    assert [t["http_calls"] for t in client.traces] == [2, 1]
    assert client.last_http_calls == 1


class _QuotaFlagged(_Echo):
    """A client the runtime never reaches: the provider is already exhausted."""

    def complete_json(self, *_a: Any, **_k: Any) -> dict[str, Any]:
        raise AssertionError("no request after provider exhaustion")


def test_exhausted_provider_reports_quota_to_issue_sink():
    # Review F2: batch j<k entering after k set the flag must still carry the quota
    # issue, or consume stops at j and drops k's sink with the only quota issue.
    runtime = _runtime()
    runtime.provider_exhausted = True
    sink: list[tuple[str, str]] = []
    assert runtime.complete_json(_QuotaFlagged(), "s", "u", issue_sink=sink) is None
    assert [code for code, _ in sink] == ["LLM_QUOTA_EXHAUSTED"]


def test_exhausted_provider_without_sink_adds_no_duplicate_issue():
    runtime = _runtime()
    runtime.provider_exhausted = True
    assert runtime.complete_json(_QuotaFlagged(), "s", "u") is None
    assert runtime.issues == [] and runtime.fallback_count == 0


class _ReservesTwice(_Echo):
    def complete_json(self, *_a: Any, before_request=None, **_k: Any) -> dict[str, Any]:
        before_request()
        before_request()  # the client's own retry: budget refuses it
        return {"ok": True}


def test_budget_refused_retry_still_times_the_sent_request():
    # Review F4: the request sent before the refused reserve must reach llm_timing.
    runtime = _runtime(max_llm_calls=1)
    assert runtime.complete_json(_ReservesTwice(), "s", "u", operation="pairs") is None
    timing = runtime.llm_timing()
    assert timing is not None and timing["by_operation"]["pairs"]["llm_calls"] == 1
