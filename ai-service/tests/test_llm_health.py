"""Health tells the truth about the configured model without calling the network."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import main
from app.llm import embeddings as embedding_module
from app.llm.client import NineRouterClient, _ping_configured_model, llm_status


def test_llm_status_is_off_without_a_key(monkeypatch) -> None:
    monkeypatch.delenv("AI2_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = NineRouterClient(api_key="", model="gpt-4o-mini")
    assert llm_status(client, probe=lambda _client: None) == "off"


def test_llm_status_is_ready_when_the_probe_succeeds() -> None:
    client = NineRouterClient(api_key="sk-test", model="gpt-4o-mini")
    assert llm_status(client, probe=lambda _client: None) == "ready"


def test_llm_status_is_unreachable_when_the_probe_fails() -> None:
    client = NineRouterClient(api_key="sk-test", model="gpt-4o-mini")

    def fail(_client: NineRouterClient) -> None:
        raise ConnectionError("gateway down")

    assert llm_status(client, probe=fail) == "unreachable"


@pytest.mark.parametrize(
    ("model", "token_limit_key", "temperature_expected"),
    [
        ("gpt-5.5", "max_completion_tokens", False),
        ("openai/gpt-5.5", "max_completion_tokens", False),
        ("gh/gpt-4o-mini", "max_tokens", True),
    ],
)
def test_health_probe_uses_model_compatible_sampling_and_token_limit(
    model: str, token_limit_key: str, temperature_expected: bool
) -> None:
    client = NineRouterClient(api_key="sk-test", model=model)
    captured: dict[str, object] = {}

    def create(**kwargs: object) -> None:
        captured.update(kwargs)

    client._client.chat.completions.create = create  # type: ignore[method-assign]
    client._client.with_options = lambda **_kwargs: client._client  # type: ignore[method-assign]

    _ping_configured_model(client)

    assert captured[token_limit_key] == (64 if token_limit_key == "max_completion_tokens" else 1)
    other_token_limit_key = (
        "max_tokens" if token_limit_key == "max_completion_tokens" else "max_completion_tokens"
    )
    assert other_token_limit_key not in captured
    assert ("temperature" in captured) is temperature_expected
    if temperature_expected:
        assert captured["temperature"] == 0


def test_llm_status_logs_safe_failure_details_without_exception_message(caplog) -> None:
    client = NineRouterClient(api_key="sk-test", model="gpt-5.5")

    def fail(_client: NineRouterClient) -> None:
        raise ConnectionError("provider rejected request; key=sk-secret")

    assert llm_status(client, probe=fail) == "unreachable"
    assert "ConnectionError" in caplog.text
    assert "sk-secret" not in caplog.text


def test_health_keeps_status_ok_when_the_model_is_unreachable(monkeypatch) -> None:
    monkeypatch.setattr(main, "llm_status", lambda _client: "unreachable")
    body = TestClient(main.app).get("/health").json()
    assert body["status"] == "ok"
    assert body["llm"] == "unreachable"
    assert "api_key" not in body
    assert "sk-" not in str(body)


def test_readyz_blocks_full_path_when_provider_capability_is_missing(monkeypatch) -> None:
    for name in (
        "AI2_SEMANTIC_ENABLED",
        "AI2_PROCESSING_EGRESS_ALLOWED",
        "AI2_QUERY_EGRESS_ALLOWED",
        "AI2_QUERY_USE_LLM",
        "AI2_QUERY_USE_VECTOR",
        "AI2_VECTOR_RECALL_ENABLED",
    ):
        monkeypatch.setenv(name, "true")
    monkeypatch.setattr(
        main,
        "_capability_snapshot",
        lambda **_kwargs: {
            "llm_status": "unreachable",
            "llm": "unreachable",
            "model": "",
            "persist": "postgres",
            "embedding": {"status": "PROVIDER_ERROR"},
        },
    )
    response = TestClient(main.app).get("/readyz")
    assert response.status_code == 503
    assert response.json()["detail"]["reason"] == "full_llm_vector_capability_not_ready"


def test_readyz_passes_full_path_when_both_capabilities_are_ready(monkeypatch) -> None:
    for name in (
        "AI2_SEMANTIC_ENABLED",
        "AI2_PROCESSING_EGRESS_ALLOWED",
        "AI2_QUERY_EGRESS_ALLOWED",
        "AI2_QUERY_USE_LLM",
        "AI2_QUERY_USE_VECTOR",
        "AI2_VECTOR_RECALL_ENABLED",
    ):
        monkeypatch.setenv(name, "true")
    monkeypatch.setattr(
        main,
        "_capability_snapshot",
        lambda **_kwargs: {
            "llm_status": "ready",
            "llm": "ready",
            "model": "gpt-4o-mini",
            "persist": "postgres",
            "embedding": {"status": "READY", "selected_model": "text-embedding-3-small"},
        },
    )
    response = TestClient(main.app).get("/readyz")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_readyz_checks_configured_embedding_when_discovery_diagnostics_are_off(monkeypatch) -> None:
    for name in (
        "AI2_SEMANTIC_ENABLED",
        "AI2_PROCESSING_EGRESS_ALLOWED",
        "AI2_QUERY_EGRESS_ALLOWED",
        "AI2_QUERY_USE_LLM",
        "AI2_QUERY_USE_VECTOR",
        "AI2_VECTOR_RECALL_ENABLED",
    ):
        monkeypatch.setenv(name, "true")
    monkeypatch.setenv("AI2_EMBEDDING_DISCOVERY_ENABLED", "false")
    monkeypatch.setattr(main, "llm_status", lambda _client: "ready")
    probe_calls: list[bool] = []

    def discover(*, egress_approved: bool):
        probe_calls.append(egress_approved)
        return type(
            "Capability",
            (),
            {
                "as_dict": lambda _self: {
                    "status": "READY",
                    "selected_model": "text-embedding-3-small",
                }
            },
        )()

    monkeypatch.setattr(main.EMBEDDING_CLIENT, "discover", discover)

    response = TestClient(main.app).get("/readyz")

    assert response.status_code == 200
    assert response.json()["embedding"]["status"] == "READY"
    assert probe_calls == [True]


def test_readyz_recovers_embedding_failure_after_cache_ttl(monkeypatch) -> None:
    for name in (
        "AI2_SEMANTIC_ENABLED", "AI2_PROCESSING_EGRESS_ALLOWED", "AI2_QUERY_EGRESS_ALLOWED",
        "AI2_QUERY_USE_LLM", "AI2_QUERY_USE_VECTOR", "AI2_VECTOR_RECALL_ENABLED",
    ):
        monkeypatch.setenv(name, "true")
    monkeypatch.setenv("AI2_EMBEDDING_DISCOVERY_ENABLED", "false")
    monkeypatch.setattr(main, "llm_status", lambda _: "ready")
    clock = [0.0]
    monkeypatch.setattr(embedding_module, "monotonic", lambda: clock[0], raising=False)
    embedding = embedding_module.OpenAICompatibleEmbeddingClient(api_key="sk-test", model="test-embedding")
    calls = []

    def embed(_texts, *, model):
        calls.append(model)
        if len(calls) == 1:
            raise ConnectionError("temporary failure")
        return [[1.0, 0.0]]

    monkeypatch.setattr(embedding, "_embed", embed)
    monkeypatch.setattr(main, "EMBEDDING_CLIENT", embedding)
    client = TestClient(main.app)
    assert client.get("/readyz").status_code == 503
    clock[0] = 1.0
    assert client.get("/readyz").status_code == 503
    assert len(calls) == 1
    clock[0] = 11.0
    assert client.get("/readyz").status_code == 200
    assert len(calls) == 2
    clock[0] = 100.0
    assert client.get("/readyz").status_code == 200
    assert len(calls) == 2
