"""The shared embedding client must not answer one dossier's egress from another's.

``/readyz`` and vector recall share one ``OpenAICompatibleEmbeddingClient``. Its
``discover`` result is cached per process, so the cache may hold only what the
provider said, never an egress decision, and a transient provider failure must
not stay cached until restart.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import main
from app.llm.embeddings import OpenAICompatibleEmbeddingClient


class FakeEmbeddingAPI:
    def __init__(self, *, fail_first: int = 0) -> None:
        self.calls = 0
        self._fail_first = fail_first
        self.embeddings = self

    def create(self, *, model, input, **kwargs):
        self.calls += 1
        if self.calls <= self._fail_first:
            raise ConnectionError("provider down")
        return {"data": [{"index": i, "embedding": [1.0, 0.0]} for i, _ in enumerate(input)]}


def _client(api: FakeEmbeddingAPI) -> OpenAICompatibleEmbeddingClient:
    return OpenAICompatibleEmbeddingClient(
        api_key="test-key", model="text-embedding-test", dimensions=2, client=api
    )


def test_ready_cache_does_not_answer_a_dossier_without_consent():
    api = FakeEmbeddingAPI()
    client = _client(api)
    assert client.discover(egress_approved=True).status == "READY"

    assert client.discover(egress_approved=False).status == "EGRESS_DENIED"
    assert client.discover(egress_approved=True).status == "READY"
    assert api.calls == 1


def test_denied_dossier_first_does_not_poison_later_consented_dossiers():
    api = FakeEmbeddingAPI()
    client = _client(api)

    assert client.discover(egress_approved=False).status == "EGRESS_DENIED"

    assert client.discover(egress_approved=True).status == "READY"


def test_transient_provider_error_is_retried_after_the_failure_ttl(monkeypatch):
    monkeypatch.setenv("AI2_EMBEDDING_FAILURE_TTL_SECONDS", "0")
    api = FakeEmbeddingAPI(fail_first=1)
    client = _client(api)

    assert client.discover(egress_approved=True).status == "PROVIDER_ERROR"

    assert client.discover(egress_approved=True).status == "READY"
    assert api.calls == 2


def test_provider_error_is_not_reprobed_on_every_call_within_the_ttl(monkeypatch):
    monkeypatch.setenv("AI2_EMBEDDING_FAILURE_TTL_SECONDS", "300")
    api = FakeEmbeddingAPI(fail_first=1)
    client = _client(api)

    assert client.discover(egress_approved=True).status == "PROVIDER_ERROR"
    assert client.discover(egress_approved=True).status == "PROVIDER_ERROR"

    assert api.calls == 1


def _full_path(monkeypatch) -> None:
    for name in (
        "AI2_SEMANTIC_ENABLED",
        "AI2_PROCESSING_EGRESS_ALLOWED",
        "AI2_QUERY_EGRESS_ALLOWED",
        "AI2_QUERY_USE_LLM",
        "AI2_QUERY_USE_VECTOR",
        "AI2_VECTOR_RECALL_ENABLED",
    ):
        monkeypatch.setenv(name, "true")


def _snapshot_without_discovery(llm_status: str = "ready"):
    return lambda: {
        "llm_status": llm_status,
        "llm": llm_status,
        "model": "gpt-5.5",
        "persist": "postgres",
        "embedding": {
            "status": "NOT_RUN",
            "models": [],
            "selected_model": None,
            "dimensions": None,
        },
    }


def test_readyz_checks_embedding_on_the_full_path_even_with_discovery_flag_off(monkeypatch):
    _full_path(monkeypatch)
    monkeypatch.delenv("AI2_EMBEDDING_DISCOVERY_ENABLED", raising=False)
    monkeypatch.setattr(main, "_capability_snapshot", _snapshot_without_discovery())
    api = FakeEmbeddingAPI()
    monkeypatch.setattr(main, "EMBEDDING_CLIENT", _client(api))

    response = TestClient(main.app).get("/readyz")

    assert response.status_code == 200
    assert response.json()["embedding"]["status"] == "READY"
    assert api.calls == 1


def test_readyz_stays_blocked_when_the_embedding_provider_is_down(monkeypatch):
    _full_path(monkeypatch)
    monkeypatch.setenv("AI2_EMBEDDING_FAILURE_TTL_SECONDS", "0")
    monkeypatch.setattr(main, "_capability_snapshot", _snapshot_without_discovery())
    monkeypatch.setattr(main, "EMBEDDING_CLIENT", _client(FakeEmbeddingAPI(fail_first=10)))

    response = TestClient(main.app).get("/readyz")

    assert response.status_code == 503
    assert response.json()["detail"]["reason"] == "full_llm_vector_capability_not_ready"


def test_readyz_does_not_call_the_embedding_provider_when_the_full_path_is_off(monkeypatch):
    _full_path(monkeypatch)
    monkeypatch.setenv("AI2_VECTOR_RECALL_ENABLED", "false")
    monkeypatch.setattr(main, "_capability_snapshot", _snapshot_without_discovery())
    api = FakeEmbeddingAPI()
    monkeypatch.setattr(main, "EMBEDDING_CLIENT", _client(api))

    response = TestClient(main.app).get("/readyz")

    assert response.status_code == 200
    assert api.calls == 0


def test_readyz_probe_leaves_other_dossiers_egress_gate_intact(monkeypatch):
    _full_path(monkeypatch)
    monkeypatch.setattr(main, "_capability_snapshot", _snapshot_without_discovery())
    client = _client(FakeEmbeddingAPI())
    monkeypatch.setattr(main, "EMBEDDING_CLIENT", client)
    assert TestClient(main.app).get("/readyz").status_code == 200

    assert client.discover(egress_approved=False).status == "EGRESS_DENIED"
