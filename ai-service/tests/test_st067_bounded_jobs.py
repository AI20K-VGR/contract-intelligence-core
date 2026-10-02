"""ST-067: every job ends with a named reason and keeps the work already done.

Each case runs under a 5 s wall-clock bound (daemon worker; the lock
has no ``pytest-timeout``). Provider failures use real ``openai`` exception
types so the classification is tested against what the SDK actually raises.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
import openai
import pytest

from app.contracts.models import JobStatus, ReviewState
from app.pipeline.idp import run_idp
from app.pipeline.runtime import ISSUE_MESSAGES_VI, ProcessingRuntime
from app.tools.jobs import SQLiteJobStore
from fixtures.llm_units_snapshot import llm_units_envelope, llm_units_record

CASE_BOUND_SECONDS = 5.0
_REQ = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")


def _bounded(fn, *args, **kwargs):
    import threading
    from concurrent.futures import Future

    outcome = Future()

    def run():
        try:
            outcome.set_result(fn(*args, **kwargs))
        except BaseException as exc:
            outcome.set_exception(exc)

    threading.Thread(target=run, daemon=True).start()
    return outcome.result(timeout=CASE_BOUND_SECONDS)


def _rate_limited(retry_after: str | None = None) -> openai.RateLimitError:
    headers = {"retry-after": retry_after} if retry_after else {}
    return openai.RateLimitError("rate limited", response=httpx.Response(429, request=_REQ, headers=headers), body=None)


def _unavailable(status: int = 503) -> openai.APIStatusError:
    return openai.InternalServerError("overloaded", response=httpx.Response(status, request=_REQ), body=None)


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class RaisingLLM:
    def __init__(self, error_factory) -> None:
        self.error_factory = error_factory
        self.calls = 0

    def configured(self) -> bool:
        return True

    def complete_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        self.calls += 1
        raise self.error_factory()


class EchoLLM:
    """Returns the raw value back, which the grounding check accepts."""

    def __init__(self, delay: float = 0.0) -> None:
        self.delay = delay
        self.calls = 0

    def configured(self) -> bool:
        return True

    def complete_json(self, _system: str, user: str, **_kwargs: Any) -> dict[str, Any]:
        self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        raw = user.split("\n", 1)[0].removeprefix("raw=")
        return {"normalized": raw}


def _runtime(clock: FakeClock, **kw: Any) -> ProcessingRuntime:
    return ProcessingRuntime(egress_allowed=True, clock=clock.monotonic, sleep=clock.sleep, **kw)


def _codes(runtime: ProcessingRuntime) -> list[str]:
    return [code for code, _ in runtime.issues]


def _handoff(result, code: str):
    matches = [issue for issue in result.handoff_issues if issue.code == code]
    assert matches, f"{code} missing from {[i.code for i in result.handoff_issues]}"
    return matches[0]


def _fee_fact(result):
    facts = result.contribution.facts if result.contribution else []
    # ``fee`` is not a profile key, so the fact carries no item_key; match its source node.
    return [f for f in facts if f.citation and f.citation.node_id == "n1_fee"]


# 1. 429 x N -> LLM_RATE_LIMITED after exactly N attempts, within the deadline.
def test_rate_limit_stops_after_configured_attempts_with_retry_after(monkeypatch):
    monkeypatch.setenv("AI2_LLM_MAX_RETRIES", "3")
    clock = FakeClock()
    runtime = _runtime(clock, max_llm_calls=10, max_processing_seconds=60)
    client = RaisingLLM(lambda: _rate_limited(retry_after="2"))

    result = _bounded(runtime.complete_json, client, "system", "user")

    assert result is None
    assert client.calls == 3
    assert _codes(runtime) == ["LLM_RATE_LIMITED"]
    assert clock.sleeps == [2.0, 2.0]  # Retry-After honoured between the 3 attempts
    assert clock.now - 1000.0 < 60


def test_backoff_is_cut_by_the_remaining_deadline(monkeypatch):
    monkeypatch.setenv("AI2_LLM_MAX_RETRIES", "5")
    clock = FakeClock()
    runtime = _runtime(clock, max_llm_calls=10, max_processing_seconds=5)
    client = RaisingLLM(lambda: _rate_limited(retry_after="30"))

    assert _bounded(runtime.complete_json, client, "system", "user") is None
    # A 30 s Retry-After cannot fit a 5 s budget: give up now, never sleep past it.
    assert client.calls == 1
    assert clock.sleeps == []
    assert _codes(runtime) == ["LLM_RATE_LIMITED"]


# 2. 503/529/connection -> LLM_UNAVAILABLE.
@pytest.mark.parametrize(
    "factory",
    [
        lambda: _unavailable(503),
        lambda: _unavailable(529),
        lambda: openai.APIConnectionError(request=_REQ),
    ],
    ids=["503", "529", "connection"],
)
def test_overload_and_connection_errors_end_as_llm_unavailable(monkeypatch, factory):
    monkeypatch.setenv("AI2_LLM_MAX_RETRIES", "2")
    clock = FakeClock()
    runtime = _runtime(clock, max_llm_calls=10, max_processing_seconds=60)
    client = RaisingLLM(factory)

    assert _bounded(runtime.complete_json, client, "system", "user") is None
    assert client.calls == 2
    assert _codes(runtime) == ["LLM_UNAVAILABLE"]


# 3. APITimeoutError -> LLM_TIMEOUT (it subclasses APIConnectionError, so order matters).
def test_sdk_timeout_ends_as_llm_timeout(monkeypatch):
    monkeypatch.setenv("AI2_LLM_MAX_RETRIES", "2")
    clock = FakeClock()
    runtime = _runtime(clock, max_llm_calls=10, max_processing_seconds=60)
    client = RaisingLLM(lambda: openai.APITimeoutError(request=_REQ))

    assert _bounded(runtime.complete_json, client, "system", "user") is None
    assert client.calls == 2
    assert _codes(runtime) == ["LLM_TIMEOUT"]


def test_non_retryable_bad_request_is_not_retried(monkeypatch):
    monkeypatch.setenv("AI2_LLM_MAX_RETRIES", "3")
    clock = FakeClock()
    runtime = _runtime(clock, max_llm_calls=10)
    bad = lambda: openai.BadRequestError("bad", response=httpx.Response(400, request=_REQ), body=None)  # noqa: E731
    client = RaisingLLM(bad)

    assert _bounded(runtime.complete_json, client, "system", "user") is None
    assert client.calls == 1
    assert _codes(runtime) == ["LLM_NON_RETRYABLE"]


# 4. max_llm_calls=1 -> SUCCEEDED, deterministic facts kept, budget issue with a message.
def test_llm_call_budget_keeps_deterministic_facts_and_succeeds():
    llm = EchoLLM()
    runtime = ProcessingRuntime(egress_allowed=True, max_llm_calls=1, max_processing_seconds=60)

    result = _bounded(run_idp, llm_units_record(), llm_units_envelope(), llm=llm, runtime=runtime)

    assert result.status == JobStatus.SUCCEEDED
    assert result.review_state == ReviewState.NEEDS_REVIEW
    assert llm.calls == 1
    assert _fee_fact(result)[0].normalized_value == "10000000"
    issue = _handoff(result, "LLM_BUDGET_EXCEEDED")
    assert issue.message == ISSUE_MESSAGES_VI["LLM_BUDGET_EXCEEDED"]


# 5. A call slower than the deadline -> ends within max_processing_seconds + eps, old facts kept.
def test_slow_llm_call_is_cut_at_the_processing_deadline():
    llm = EchoLLM(delay=3.0)
    runtime = ProcessingRuntime(egress_allowed=True, max_llm_calls=10, max_processing_seconds=1)

    started = time.monotonic()
    result = _bounded(run_idp, llm_units_record(), llm_units_envelope(), llm=llm, runtime=runtime)
    elapsed = time.monotonic() - started

    assert elapsed < 1 + 1.0
    assert result.status == JobStatus.SUCCEEDED
    assert result.review_state == ReviewState.NEEDS_REVIEW
    assert _fee_fact(result), "fact extracted before the timeout must be kept"
    issue = _handoff(result, "PROCESSING_TIMEOUT")
    assert issue.message == ISSUE_MESSAGES_VI["PROCESSING_TIMEOUT"]


# 8. Egress off -> SUCCEEDED + NEEDS_REVIEW with EGRESS_DENIED, zero LLM calls.
def test_egress_denied_is_a_review_note_not_a_block():
    llm = EchoLLM()

    result = _bounded(run_idp, llm_units_record(egress_approved=False), llm_units_envelope(), llm=llm)

    assert result.status == JobStatus.SUCCEEDED
    assert result.review_state == ReviewState.NEEDS_REVIEW
    assert llm.calls == 0
    assert _fee_fact(result)[0].normalized_value == "10000000"
    issue = _handoff(result, "EGRESS_DENIED")
    assert issue.review_state == ReviewState.NEEDS_REVIEW
    assert issue.message == ISSUE_MESSAGES_VI["EGRESS_DENIED"]
    assert all(i.review_state != ReviewState.BLOCKED for i in result.handoff_issues)


def test_every_termination_code_has_a_vietnamese_message():
    for code in (
        "LLM_RATE_LIMITED",
        "LLM_UNAVAILABLE",
        "LLM_TIMEOUT",
        "LLM_BUDGET_EXCEEDED",
        "PROCESSING_TIMEOUT",
        "EGRESS_DENIED",
        "AI2_WORKER_RESTARTED",
    ):
        assert ISSUE_MESSAGES_VI[code].strip()


# 9. /query embedding cap (D6): over AI2_QUERY_MAX_EMBEDDING_TOKENS -> no embedding call,
#    vector recall off for that ask, answer still comes from deterministic retrieval.
class FakeEmbeddings:
    def __init__(self) -> None:
        self.embedded_texts = 0

    def discover(self, *, egress_approved: bool = True, force: bool = False):
        from app.llm.embeddings import EmbeddingCapability

        return EmbeddingCapability(status="READY", selected_model="fake-embed", dimensions=3)

    def embed(self, texts, *, model=None, egress_approved=True):
        self.embedded_texts += len(texts)
        return [[1.0, 0.0, 0.0] for _ in texts]


def _signed_query(main, monkeypatch, tmp_path, *, cap: str, egress: str = "true") -> tuple[dict, FakeEmbeddings]:
    from fastapi.testclient import TestClient

    from app.reasoning.vector_recall import VectorRecallService
    from app.security.service_envelope import build_service_envelope
    from fixtures import mock_record

    fake = FakeEmbeddings()
    monkeypatch.setenv("AI2_SERVICE_HMAC_SECRET", "test-secret")
    monkeypatch.setenv("AI2_QUERY_EGRESS_ALLOWED", egress)
    monkeypatch.setenv("AI2_QUERY_USE_VECTOR", "true")
    monkeypatch.setenv("AI2_QUERY_MAX_EMBEDDING_TOKENS", cap)
    monkeypatch.setenv("AI2_VECTOR_DB", str(tmp_path / "vectors.sqlite"))
    monkeypatch.setattr(main, "EMBEDDING_CLIENT", fake)
    monkeypatch.setattr(main, "VECTOR_RECALL", VectorRecallService(embedding_client=fake, enabled=True))
    main.STORE._dossiers.clear()
    main.STORE.put(mock_record())
    payload = {
        "query": "Các bên thoả thuận gì về việc thanh toán và nghiệm thu?",
        "dossier_id": "dossier_001",
        "snapshot_version": "ai1.snapshot.v1",
    }
    payload["service_envelope"] = build_service_envelope(
        payload, secret="test-secret", tenant_id="tenant_a", dossier_id="dossier_001",
        actor_id="user_001", scopes=["ai2.query"],
    )
    try:
        response = TestClient(main.app).post("/query", json=payload)
    finally:
        main.STORE._dossiers.clear()
    assert response.status_code == 200
    return response.json(), fake


def test_query_vector_recall_embeds_within_the_default_cap(monkeypatch, tmp_path):
    from app.api import main

    body, fake = _bounded(_signed_query, main, monkeypatch, tmp_path, cap="100000")

    assert fake.embedded_texts > 0, "control: this ask must reach vector recall"
    assert body["retrieval_layer"]["vector_status"] == "READY"


def test_query_embedding_cap_turns_vector_off_without_calling_the_provider(monkeypatch, tmp_path):
    from app.api import main

    monkeypatch.setenv("AI2_QUERY_USE_LLM", "false")  # deterministic answer path
    body, fake = _bounded(_signed_query, main, monkeypatch, tmp_path, cap="10")

    assert fake.embedded_texts == 0
    assert body["retrieval_layer"]["vector_status"] == "BUDGET_EXCEEDED"
    # Deterministic answer over mock_record; /query never emits PASS (now ANSWERED).
    assert body["state"] == "NEEDS_REVIEW"
    assert body["citations"]
    assert body["retrieval_layer"]["reason_code"] == "EMBEDDING_BUDGET_EXCEEDED"


def test_signed_query_egress_flag_blocks_vector_provider(monkeypatch, tmp_path):
    from app.api import main

    body, fake = _bounded(_signed_query, main, monkeypatch, tmp_path, cap="100000", egress="false")
    assert fake.embedded_texts == 0
    assert body["retrieval_layer"]["vector_status"] == "EGRESS_DENIED"
    assert body["citations"]


# 6. Failure before claim -> the job is FAILED, never stuck in QUEUED.
def _queued_job(store: SQLiteJobStore, job_id_hint: str) -> str:
    wire = {"status": "QUEUED", "review_state": "NEEDS_REVIEW", "result": None, "errors": []}
    stored, created = store.create_or_get(
        tenant_id="tenant_a",
        dossier_id="dossier-st067",
        request_id=f"req-{job_id_hint}",
        idempotency_key=f"idem-{job_id_hint}",
        attempt=1,
        request={"dossier_id": "dossier-st067"},
        wire=wire,
    )
    assert created
    return stored["job_id"]


def test_worker_error_before_claim_marks_the_job_failed(monkeypatch, tmp_path):
    from app.api import main

    store = SQLiteJobStore(tmp_path / "jobs.sqlite")
    monkeypatch.setattr(main, "JOB_STORE", store)
    job_id = _queued_job(store, "preclaim")

    def explode(_payload):
        raise RuntimeError("envelope store unreachable")

    monkeypatch.setattr(main, "verify_service_envelope", explode)
    _bounded(main._run_wire_job, job_id, {"dossier_id": "dossier-st067"})

    job = store.get(job_id)
    assert job["status"] == "FAILED"
    assert job["wire"]["errors"][0]["code"] == "AI2_WORKER_FAILED"


# 7. Restart -> a RUNNING job past its lease (and a stale QUEUED one) is swept to FAILED.
def test_startup_sweep_fails_jobs_left_by_a_dead_worker(monkeypatch, tmp_path):
    from app.api import main

    store = SQLiteJobStore(tmp_path / "jobs.sqlite")
    expired = _queued_job(store, "expired")
    assert store.claim(expired, tenant_id="tenant_a", dossier_id="dossier-st067", lease_ms=-1)
    live = _queued_job(store, "live")
    assert store.claim(live, tenant_id="tenant_a", dossier_id="dossier-st067", lease_ms=60_000)
    orphaned = _queued_job(store, "orphaned")

    swept = _bounded(main._sweep_stale_jobs, store, queued_grace_ms=0)

    assert set(swept) == {expired, orphaned}
    for job_id in (expired, orphaned):
        job = store.get(job_id)
        assert job["status"] == "FAILED"
        error = job["wire"]["errors"][0]
        assert error["code"] == "AI2_WORKER_RESTARTED"
        assert error["message"] == ISSUE_MESSAGES_VI["AI2_WORKER_RESTARTED"]
        assert error["retryable"] is True
    assert store.get(live)["status"] == "RUNNING"


def _http_llm(handler):
    from app.llm.client import NineRouterClient

    client = NineRouterClient(base_url="https://provider.test/v1", api_key="test-local")
    client._client = openai.OpenAI(
        api_key="test-local", base_url="https://provider.test/v1", max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    _ = client._client.chat.completions
    return client


def _provider_reply(request, *, status=200, param="response_format"):
    if status != 200:
        return httpx.Response(status, request=request, json={
            "error": {"message": "unsupported parameter", "type": "invalid_request_error", "param": param},
        })
    return httpx.Response(200, request=request, json={
        "id": "completion-test", "object": "chat.completion", "created": 1, "model": "test",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "{}"}, "finish_reason": "stop"}],
    })


def test_format_fallback_reserves_each_http_request_before_sending():
    requests = []

    def handler(request):
        requests.append(request)
        return _provider_reply(request, status=400 if len(requests) == 1 else 200)

    runtime = ProcessingRuntime(egress_allowed=True, max_llm_calls=1)
    assert runtime.complete_json(_http_llm(handler), "system", "user") is None
    assert len(requests) == runtime.llm_calls_used == 1
    assert "LLM_BUDGET_EXCEEDED" in _codes(runtime)


def test_failed_format_fallback_is_counted_against_retry_budget():
    requests = []

    def handler(request):
        import json
        requests.append(request)
        payload = json.loads(request.content)
        return _provider_reply(request, status=400 if "response_format" in payload else 429)

    runtime = ProcessingRuntime(egress_allowed=True, max_llm_calls=3, sleep=lambda _seconds: None)
    assert runtime.complete_json(_http_llm(handler), "system", "user") is None
    assert len(requests) == runtime.llm_calls_used == 3


@pytest.mark.parametrize("status", [400, 422])
def test_unrelated_request_errors_never_retry_without_json_format(status):
    requests = []

    def handler(request):
        requests.append(request)
        return _provider_reply(request, status=status, param="model")

    with pytest.raises(openai.APIStatusError):
        _http_llm(handler).complete_json("system", "user")
    assert len(requests) == 1


def test_timed_out_http_request_cannot_start_a_later_format_fallback():
    from app.pipeline.runtime import ProcessingTimeout

    requests = []

    def handler(request):
        requests.append(request)
        time.sleep(0.08)
        return _provider_reply(request, status=400)

    client = _http_llm(handler)
    runtime = ProcessingRuntime(egress_allowed=True, max_llm_calls=3, max_processing_seconds=0.03)
    with pytest.raises(ProcessingTimeout):
        runtime.complete_json(client, "system", "user")
    time.sleep(0.2)
    assert len(requests) == runtime.llm_calls_used == 1


def test_call_timeout_cancels_fallback_even_before_the_job_deadline():
    requests = []

    def handler(request):
        requests.append(request)
        time.sleep(0.08)
        return _provider_reply(request, status=400)

    client = _http_llm(handler)
    runtime = ProcessingRuntime(
        egress_allowed=True, max_llm_calls=3, max_processing_seconds=2,
        call_timeout_seconds=0.03, max_attempts=1,
    )
    assert runtime.complete_json(client, "system", "user") is None
    assert _codes(runtime) == ["LLM_TIMEOUT"]
    time.sleep(0.2)
    assert len(requests) == runtime.llm_calls_used == 1


def test_periodic_sweep_catches_jobs_whose_lease_expires_after_startup(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from app.api import main

    store = SQLiteJobStore(tmp_path / "periodic.sqlite")
    now = [1000]
    monkeypatch.setattr(store, "_now_ms", lambda: now[0])
    monkeypatch.setattr(main, "JOB_STORE", store)
    job_id = _queued_job(store, "expires-later")
    store.claim(job_id, tenant_id="tenant_a", dossier_id="dossier-st067", lease_ms=50)
    monkeypatch.setattr(main, "JOB_SWEEP_INTERVAL_SECONDS", 0.01, raising=False)
    with TestClient(main.app):
        assert store.get(job_id)["status"] == "RUNNING"
        now[0] += 100
        until = time.monotonic() + 1
        while store.get(job_id)["status"] != "FAILED" and time.monotonic() < until:
            time.sleep(0.01)
        assert store.get(job_id)["status"] == "FAILED"
        assert store.get(job_id)["wire"]["errors"][0]["code"] == "AI2_WORKER_RESTARTED"


def test_over_cap_dossier_skips_embedding_capability_discovery(tmp_path):
    from app.reasoning.vector_recall import SQLiteVectorIndex, VectorRecallService
    from fixtures import mock_record

    class ColdEmbeddings(FakeEmbeddings):
        def discover(self, **kwargs):
            raise AssertionError("discovery would call the external embedding provider")

    runtime = ProcessingRuntime(egress_allowed=True, max_embedding_tokens=1)
    service = VectorRecallService(
        embedding_client=ColdEmbeddings(), index=SQLiteVectorIndex(tmp_path / "cold.sqlite"),
        enabled=True, runtime=runtime,
    )
    result = service.recall(mock_record(), "Thanh toán?")
    assert result.status == "BUDGET_EXCEEDED"
    assert result.trace["reason_code"] == "EMBEDDING_BUDGET_EXCEEDED"


def test_live_worker_lease_covers_the_processing_budget(monkeypatch, tmp_path):
    from test_a1_query_digest import _body_only_request

    from app.api import main
    from app.tools.store import InMemorySnapshotStore

    monkeypatch.setenv("AI2_SERVICE_HMAC_SECRET", "test-secret")
    monkeypatch.setenv("AI2_PROCESSING_EGRESS_ALLOWED", "false")
    payload = _body_only_request()
    store = SQLiteJobStore(tmp_path / "budget-lease.sqlite")
    now = [1000]
    monkeypatch.setattr(store, "_now_ms", lambda: now[0])
    monkeypatch.setattr(main, "JOB_STORE", store)
    monkeypatch.setattr(main, "STORE", InMemorySnapshotStore())
    monkeypatch.setattr(main, "WIRE_JOBS", {})
    from app.tools import query_store
    monkeypatch.setattr(query_store, "save_query_snapshot", lambda *_args: None)
    job, _ = store.create_or_get(
        tenant_id="tenant_a", dossier_id=payload["dossier_id"], request_id=payload["request_id"],
        idempotency_key=payload["idempotency_key"], attempt=1, request=payload,
        wire={"status": "QUEUED", "result": None, "errors": []},
    )
    original_run = main.run_idp

    def after_seventy_five_seconds(*args, **kwargs):
        now[0] += 75_000
        assert main._sweep_stale_jobs(store) == []
        assert store.get(job["job_id"])["status"] == "RUNNING"
        return original_run(*args, **kwargs)

    monkeypatch.setattr(main, "run_idp", after_seventy_five_seconds)
    main._run_wire_job(job["job_id"], payload)
    assert store.get(job["job_id"])["status"] == "SUCCEEDED"


def test_case_timeout_does_not_keep_the_test_process_alive():
    import ast
    import subprocess
    import sys
    from pathlib import Path

    source = Path(__file__).read_text(encoding="utf-8")
    helper = next(node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == "_bounded")
    code = "import time\nCASE_BOUND_SECONDS=.02\n"
    code += ast.get_source_segment(source, helper)
    code += "\ntry:\n _bounded(time.sleep, 10)\nexcept TimeoutError:\n print('caller_timed_out', flush=True)\n"
    completed = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=2)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "caller_timed_out"


@pytest.mark.parametrize("extra_tokens", [0, 9])
def test_real_embedding_discovery_is_charged_before_provider_requests(tmp_path, extra_tokens):
    from types import SimpleNamespace

    from app.llm.embeddings import OpenAICompatibleEmbeddingClient
    from app.reasoning.vector_recall import SQLiteVectorIndex, VectorRecallService, build_segments
    from fixtures import mock_record

    sent = []

    def create(**kwargs):
        sent.extend(kwargs["input"])
        return {"data": [{"index": i, "embedding": [1.0, 0.0, 0.0]} for i in range(len(kwargs["input"]))]}

    record = mock_record()
    record.egress_approved = True
    query = "nghĩa vụ bảo mật"
    tokens = lambda text: max(1, (len(text) + 3) // 4)  # noqa: E731
    corpus_tokens = sum(tokens(segment.text) for segment in build_segments(record)) + tokens(query)
    cap = corpus_tokens + extra_tokens
    runtime = ProcessingRuntime(egress_allowed=True, max_embedding_tokens=cap)
    client = OpenAICompatibleEmbeddingClient(
        api_key="probe-only", model="fake-embed", dimensions=3,
        client=SimpleNamespace(embeddings=SimpleNamespace(create=create)),
    )
    service = VectorRecallService(
        embedding_client=client, index=SQLiteVectorIndex(tmp_path / "discovery.sqlite"),
        enabled=True, runtime=runtime,
    )
    result = service.recall(record, query)
    provider_tokens = sum(tokens(text) for text in sent)
    assert provider_tokens <= cap
    assert runtime.embedding_tokens_used == provider_tokens
    assert result.status == ("READY" if extra_tokens else "BUDGET_EXCEEDED")


# I3: a QUEUED job still waiting for a worker thread in a live process is not
# an orphan; only jobs nobody holds any more are swept.
def test_sweep_keeps_queued_jobs_this_process_still_holds(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from test_a1_query_digest import _body_only_request

    from app.api import main

    monkeypatch.setenv("AI2_SERVICE_HMAC_SECRET", "test-secret")
    store = SQLiteJobStore(tmp_path / "held.sqlite")
    now = [1_000]
    monkeypatch.setattr(store, "_now_ms", lambda: now[0])
    monkeypatch.setattr(main, "JOB_STORE", store)
    monkeypatch.setattr(main, "WIRE_JOBS", {})
    monkeypatch.setattr(main, "WIRE_IDEMPOTENCY", {})
    monkeypatch.setattr(main, "_HELD_JOB_IDS", set())
    # The accepted task never gets a thread (pool saturated).
    monkeypatch.setattr(main, "_run_wire_job", lambda *_args, **_kwargs: None)
    accepted = TestClient(main.app).post("/jobs/idp", json=_body_only_request())
    assert accepted.status_code == 202, accepted.text
    held = accepted.json()["job_id"]
    orphan = _queued_job(store, "orphan-i3")

    now[0] += 120_000  # both are older than the 60 s queued grace
    swept = _bounded(main._sweep_stale_jobs, store)

    assert swept == [orphan]
    assert store.get(held)["status"] == "QUEUED"
    assert store.get(orphan)["wire"]["errors"][0]["code"] == "AI2_WORKER_RESTARTED"
    # Another replica sharing the store sees the hold as a live lease...
    assert store.sweep_stale({"errors": []}) == []
    # ...until this process stops renewing it (crash), then it is an orphan.
    now[0] += 120_000
    assert store.sweep_stale({"errors": []}) == [held]
