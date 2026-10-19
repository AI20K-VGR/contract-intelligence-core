"""Langfuse cost of AI2 questions (app/llm/observability.py), with fake clients only.

No OpenAI or Langfuse request is made: the provider and the Langfuse client are
in-memory fakes, so these tests cost nothing.
"""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from prometheus_client import REGISTRY

import app.llm.observability as obs
from app.llm.client import DeadlineLLM, NineRouterClient
from app.llm.embeddings import OpenAICompatibleEmbeddingClient


class _FakeObservation:
    def __init__(self, store: list[dict], **fields) -> None:
        self.fields = dict(fields)
        self.updates: list[dict] = []
        store.append(self.fields | {"updates": self.updates})

    def update(self, **kwargs) -> None:
        self.updates.append(kwargs)


class _FakeLangfuse:
    def __init__(self) -> None:
        self.observations: list[dict] = []

    @contextmanager
    def start_as_current_observation(self, **fields):
        yield _FakeObservation(self.observations, **fields)


@pytest.fixture
def langfuse(monkeypatch):
    fake = _FakeLangfuse()
    monkeypatch.setattr(obs, "get_langfuse", lambda: fake)
    monkeypatch.setattr(obs, "propagate_attributes", lambda **_kw: _nullcontext())
    monkeypatch.delenv("AI2_LLM_PRICES_JSON", raising=False)
    monkeypatch.delenv("AI2_METRICS_PORT", raising=False)
    return fake


@contextmanager
def _nullcontext():
    yield


def _chat_response(prompt=1200, completion=400, cached=200, reasoning=150):
    usage = SimpleNamespace(
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=prompt + completion,
        completion_tokens_details=SimpleNamespace(reasoning_tokens=reasoning),
        prompt_tokens_details=SimpleNamespace(cached_tokens=cached),
    )
    choice = SimpleNamespace(
        message=SimpleNamespace(content='{"answer": "x"}'), finish_reason="stop"
    )
    return SimpleNamespace(choices=[choice], usage=usage, model="gpt-5.5-2026-09-01")


def _llm(response=None, error: Exception | None = None) -> NineRouterClient:
    client = NineRouterClient(
        base_url="http://fake.invalid/v1", api_key="test-key", model="gpt-5.5"
    )

    def create(**_kwargs):
        if error is not None:
            raise error
        return response or _chat_response()

    client._client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    return client


def _query(**overrides):
    return obs.query_trace(
        **{
            "dossier_id": "dos_1",
            "tenant_id": "ten_1",
            "actor_id": "usr_1",
            "task_type": "compare",
            "query_chars": 42,
            **overrides,
        }
    )


def _generations(fake: _FakeLangfuse) -> list[dict]:
    return [o for o in fake.observations if o.get("as_type") in {"generation", "embedding"}]


def test_gpt55_cost_splits_cached_input_and_includes_reasoning_in_output():
    usage = {"input": 1000, "input_cached": 200, "output": 400}
    cost = obs.cost_details("openai/GPT-5.5", usage)
    assert cost == pytest.approx(
        {
            "input": 1000 * 5.00 / 1e6,
            "input_cached": 200 * 0.50 / 1e6,
            "output": 400 * 30.00 / 1e6,
            "total": (1000 * 5.00 + 200 * 0.50 + 400 * 30.00) / 1e6,
        }
    )


def test_served_snapshot_id_uses_its_base_model_price():
    assert obs.cost_details("gpt-5.5-2026-09-01", {"output": 1_000_000})["total"] == 30.0
    # A different model that only shares a prefix is not priced as gpt-5.5.
    assert obs.cost_details("gpt-5.55", {"output": 1_000_000}) is None


def test_unknown_model_has_no_cost_until_priced_by_env(monkeypatch):
    assert obs.cost_details("gpt-9", {"input": 10}) is None
    monkeypatch.setenv("AI2_LLM_PRICES_JSON", '{"GPT-9": {"input": 1, "output": 2}}')
    assert obs.cost_details("gpt-9", {"input": 1_000_000, "output": 1_000_000})["total"] == 3.0


def test_invalid_price_json_keeps_built_in_prices(monkeypatch):
    monkeypatch.setenv("AI2_LLM_PRICES_JSON", "not json")
    assert obs.cost_details("gpt-5.5", {"output": 1_000_000})["total"] == 30.0


def test_calls_outside_a_question_are_not_traced(langfuse):
    _llm().complete_json("system json", "user")
    assert langfuse.observations == []


def test_question_trace_records_usage_cost_and_no_text(langfuse):
    with _query():
        _llm().complete_json("system json PRIVATE-PROMPT", "user PRIVATE-CLAUSE")

    root, generation = langfuse.observations
    assert root["name"] == "ai2.query" and root["as_type"] == "span"
    assert root["input"] == {"query_chars": 42, "task_type": "compare"}
    assert generation["as_type"] == "generation" and generation["model"] == "gpt-5.5"
    (update,) = generation["updates"]
    assert update["model"] == "gpt-5.5-2026-09-01"
    assert update["usage_details"] == {
        "input": 1000,
        "input_cached": 200,
        "output": 400,
        "total": 1600,
    }
    assert update["cost_details"]["total"] == pytest.approx((1000 * 5 + 200 * 0.5 + 400 * 30) / 1e6)
    assert update["metadata"]["reasoning_tokens"] == 150
    assert "level" not in update
    # Only counts and ids reach Langfuse, never the prompt or the contract text.
    assert "PRIVATE" not in repr(langfuse.observations)


def test_question_deadline_thread_still_belongs_to_the_question(langfuse):
    with _query():
        DeadlineLLM(_llm(), 5.0).complete_json("system json", "user")
    assert len(_generations(langfuse)) == 1


def test_failed_call_is_an_error_generation_and_still_raises(langfuse):
    with _query(), pytest.raises(RuntimeError):
        _llm(error=RuntimeError("provider down")).complete_json("system json", "user")
    (generation,) = _generations(langfuse)
    (update,) = generation["updates"]
    assert update["level"] == "ERROR" and update["status_message"] == "RuntimeError"
    assert "cost_details" not in update


def test_question_embedding_cost(langfuse):
    response = SimpleNamespace(
        data=[{"index": 0, "embedding": [0.1, 0.2]}], usage=SimpleNamespace(prompt_tokens=12)
    )
    fake_openai = SimpleNamespace(embeddings=SimpleNamespace(create=lambda **_kw: response))
    client = OpenAICompatibleEmbeddingClient(
        base_url="http://fake.invalid/v1",
        api_key="k",
        model="text-embedding-3-small",
        client=fake_openai,
    )
    with _query():
        assert client.embed(["Điều 5 thanh toán"]) == [[0.1, 0.2]]
    (generation,) = _generations(langfuse)
    assert generation["as_type"] == "embedding" and generation["metadata"] == {"inputs": 1}
    (update,) = generation["updates"]
    assert update["usage_details"] == {"input": 12, "total": 12}
    assert update["cost_details"]["total"] == pytest.approx(12 * 0.02 / 1e6)


def test_unconfigured_langfuse_and_metrics_is_a_no_op(monkeypatch):
    monkeypatch.setattr(obs, "get_langfuse", lambda: None)
    monkeypatch.delenv("AI2_METRICS_PORT", raising=False)
    with _query() as question:
        assert question.span is None
        assert _llm().complete_json("system json", "user") == {"answer": "x"}
        question.done({"state": "PASS"})


def _sample(name: str, **labels: str) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


def test_grafana_metrics_count_a_question_without_langfuse(monkeypatch):
    """Prometheus (Grafana) gets the question's cost even with Langfuse off."""

    monkeypatch.setattr(obs, "get_langfuse", lambda: None)
    monkeypatch.setenv("AI2_METRICS_PORT", "9109")  # no server is started here
    chat = {"kind": "chat", "model": "gpt-5.5-2026-09-01"}
    before = {
        "answered": _sample("ai2_query_requests_total", state="ANSWERED"),
        "calls": _sample("ai2_query_model_calls_total", **chat, status="ok"),
        "output": _sample("ai2_query_tokens_total", **chat, type="output"),
        "cached": _sample("ai2_query_tokens_total", **chat, type="input_cached"),
        "cost": _sample("ai2_query_cost_usd_total", **chat),
        "seconds": _sample("ai2_query_duration_seconds_count"),
    }
    with _query() as question:
        _llm().complete_json("system json", "user")
        question.done({"review_state": "PASS", "citations": []})

    assert _sample("ai2_query_requests_total", state="ANSWERED") - before["answered"] == 1
    assert _sample("ai2_query_model_calls_total", **chat, status="ok") - before["calls"] == 1
    assert _sample("ai2_query_tokens_total", **chat, type="output") - before["output"] == 400
    assert _sample("ai2_query_tokens_total", **chat, type="input_cached") - before["cached"] == 200
    assert _sample("ai2_query_cost_usd_total", **chat) - before["cost"] == pytest.approx(
        (1000 * 5 + 200 * 0.5 + 400 * 30) / 1e6
    )
    assert _sample("ai2_query_duration_seconds_count") - before["seconds"] == 1


def test_grafana_metrics_count_failed_calls_and_questions(monkeypatch):
    monkeypatch.setattr(obs, "get_langfuse", lambda: None)
    monkeypatch.setenv("AI2_METRICS_PORT", "9109")
    errors = _sample("ai2_query_model_calls_total", kind="chat", model="gpt-5.5", status="error")
    failed = _sample("ai2_query_requests_total", state="FAILED")
    with pytest.raises(RuntimeError), _query():
        _llm(error=RuntimeError("provider down")).complete_json("system json", "user")
    assert (
        _sample("ai2_query_model_calls_total", kind="chat", model="gpt-5.5", status="error")
        - errors
        == 1
    )
    assert _sample("ai2_query_requests_total", state="FAILED") - failed == 1


def test_question_trace_output_is_the_answer_state(langfuse):
    with _query() as question:
        question.done({"state": "PASS", "used_llm": True, "citations": [{}, {}]})
    (root,) = langfuse.observations
    assert root["updates"] == [{"output": {"state": "ANSWERED", "used_llm": True, "citations": 2}}]
