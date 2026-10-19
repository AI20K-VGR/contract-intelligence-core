"""PR #135 review (P1): a provider error must not carry its text into Langfuse.

Uses the real Langfuse SDK with an in-memory OpenTelemetry exporter: nothing is
sent over the network and no provider is called.
"""

from __future__ import annotations

import pytest
from langfuse import Langfuse
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import app.llm.observability as obs
from app.llm.client import NineRouterClient
from contract_ocr.infrastructure.observability import _mask_otel_spans

SENTINEL = "PRIVATE-CONTRACT-SENTINEL"


@pytest.fixture
def exported(monkeypatch):
    exporter = InMemorySpanExporter()
    client = Langfuse(
        public_key="pk-lf-local-test",
        secret_key="sk-lf-local-test",
        base_url="http://127.0.0.1:9",
        tracing_enabled=True,
        span_exporter=exporter,
        mask_otel_spans=_mask_otel_spans,
    )
    monkeypatch.setattr(obs, "get_langfuse", lambda: client)
    monkeypatch.delenv("AI2_METRICS_PORT", raising=False)

    def spans():
        client.flush()
        return exporter.get_finished_spans()

    yield spans
    client.shutdown()


def _failing_llm() -> NineRouterClient:
    llm = NineRouterClient(base_url="http://fake.invalid/v1", api_key="test-key", model="gpt-5.5")

    def create(**_kwargs):
        raise RuntimeError(f"Provider rejected content: {SENTINEL}")

    llm._client = type(
        "C",
        (),
        {"chat": type("H", (), {"completions": type("P", (), {"create": staticmethod(create)})})},
    )()
    return llm


def _dump(spans) -> str:
    parts = []
    for span in spans:
        parts.append(repr(dict(span.attributes or {})))
        parts.append(repr(span.status.description))
        for event in span.events:
            parts.append(event.name + repr(dict(event.attributes or {})))
    return "\n".join(parts)


def test_provider_error_text_is_not_exported(exported):
    with obs.query_trace(
        dossier_id="dos_1", tenant_id="ten_1", actor_id="usr_1", task_type="compare", query_chars=10
    ):
        # /query falls back to retrieval when the LLM fails: the error is caught here.
        with pytest.raises(RuntimeError, match=SENTINEL):
            _failing_llm().complete_json("system json", "user")

    spans = exported()
    names = {span.name for span in spans}
    assert {"ai2.query", "ai2.llm.complete_json"} <= names
    text = _dump(spans)
    assert SENTINEL not in text
    assert "RuntimeError" in text  # the error type is still recorded


def test_error_escaping_the_question_is_not_exported(exported):
    with pytest.raises(RuntimeError, match=SENTINEL):
        with obs.query_trace(
            dossier_id="dos_1", tenant_id="ten_1", actor_id=None, task_type=None, query_chars=1
        ):
            _failing_llm().complete_json("system json", "user")

    text = _dump(exported())
    assert SENTINEL not in text
