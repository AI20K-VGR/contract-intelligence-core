"""Health tells the truth about the configured model without calling the network."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import main
from app.llm.client import NineRouterClient, llm_status


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
        lambda: {"llm_status": "unreachable", "llm": "unreachable", "model": "", "persist": "postgres", "embedding": {"status": "PROVIDER_ERROR"}},
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
        lambda: {"llm_status": "ready", "llm": "ready", "model": "gpt-4o-mini", "persist": "postgres", "embedding": {"status": "READY", "selected_model": "text-embedding-3-small"}},
    )
    response = TestClient(main.app).get("/readyz")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
