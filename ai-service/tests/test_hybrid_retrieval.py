from types import SimpleNamespace

from fixtures.catalog import make_node, make_page, make_record, make_pins
from app.contracts.models import LifecycleState, SourceFile, TenantProfile
from app.llm.embeddings import OpenAICompatibleEmbeddingClient
from app.pipeline.runtime import ProcessingRuntime
from app.reasoning.query import classify_ask
from app.reasoning.relations import build_relation_graph
from app.reasoning.vector_recall import SQLiteVectorIndex, VectorRecallService


class FakeEmbeddingAPI:
    def __init__(self, *, multiple: bool = False):
        names = ["chat-model", "text-embedding-test"]
        if multiple:
            names.append("bge-embedding-test")
        self.models = SimpleNamespace(list=lambda: {"data": [{"id": name} for name in names]})
        self.embeddings = SimpleNamespace(create=self._create)

    def _create(self, *, model, input, **kwargs):
        return {"data": [{"index": i, "embedding": [1.0, float(i % 2)]} for i, _ in enumerate(input)]}


def _record():
    nodes = [
        make_node("cl_5", "CLAUSE", "Dieu 5", "Dieu 5. Payment follows Phu luc 1.", page=5),
        make_node("annex_1", "SECTION", "Phu luc 1", "Phu luc 1. Payment schedule.", page=8),
        make_node("cl_5_annex", "CLAUSE", "Dieu 5", "Dieu 5 in the annex repeats the payment rule.", page=9, source_file_id="annex_file"),
    ]
    return make_record(
        case_id="HYBRID",
        dossier="hybrid-1",
        pages=[make_page(5, "Dieu 5"), make_page(8, "Phu luc 1"), make_page(9, "Dieu 5")],
        nodes=nodes,
        pins=make_pins(source_snapshot_digest="sha256:hybrid"),
        profile=TenantProfile(version=1),
        source_files=[
            SourceFile(file_id="body_file", filename="contract.pdf", role="body"),
            SourceFile(file_id="annex_file", filename="annex.pdf", role="annex"),
        ],
    )


def test_relation_query_is_explicitly_routed():
    task = classify_ask("Dieu 5 anh huong den Phu luc 1 nhu the nao?")
    assert task["type"] == "cascade"
    assert task["focus_clause_labels"] == ["\u0110i\u1ec1u 5"]
    assert task["annex_numbers"] == ["1"]


def test_relation_graph_keeps_structural_and_cross_source_edges():
    graph = build_relation_graph(_record())
    kinds = {edge.relation_type.value for edge in graph.edges}
    assert "REFERENCES" in kinds
    assert "SAME_CLAUSE" in kinds
    assert all(edge.source_snapshot_digest == "sha256:hybrid" for edge in graph.edges)
    assert all(citation.node_id in {node.node_id for node in _record().nodes} for edge in graph.edges for citation in edge.citations)


def test_embedding_discovery_rejects_ambiguous_models(monkeypatch):
    monkeypatch.delenv("AI2_EMBEDDING_MODEL", raising=False)
    client = OpenAICompatibleEmbeddingClient(api_key="test-key", dimensions=2, client=FakeEmbeddingAPI(multiple=True))
    capability = client.discover()
    assert capability.status == "CONFIG_REQUIRED"


def test_vector_recall_is_snapshot_and_citation_checked(tmp_path):
    record = _record()
    client = OpenAICompatibleEmbeddingClient(api_key="test-key", model="text-embedding-test", dimensions=2, client=FakeEmbeddingAPI())
    service = VectorRecallService(client, SQLiteVectorIndex(tmp_path / "vectors.sqlite"), enabled=True)
    result = service.recall(record, "payment schedule", filters={"source_role": "annex"})
    assert result.status == "READY"
    assert result.candidates
    assert all(candidate.citation.node_id == "cl_5_annex" for candidate in result.candidates)


def test_vector_recall_disabled_without_feature_flag():
    record = _record()
    client = OpenAICompatibleEmbeddingClient(api_key="test-key", model="text-embedding-test", dimensions=2, client=FakeEmbeddingAPI())
    result = VectorRecallService(client, enabled=False).recall(record, "payment")
    assert result.status == "DISABLED"


def test_vector_recall_stops_before_provider_when_embedding_budget_is_exceeded(tmp_path):
    record = _record()
    client = OpenAICompatibleEmbeddingClient(api_key="test-key", model="text-embedding-test", dimensions=2, client=FakeEmbeddingAPI())
    runtime = ProcessingRuntime(egress_allowed=True, max_embedding_tokens=1)
    service = VectorRecallService(
        client,
        SQLiteVectorIndex(tmp_path / "vectors.sqlite"),
        enabled=True,
        runtime=runtime,
    )

    result = service.recall(record, "payment schedule")

    assert result.status == "BUDGET_EXCEEDED"
    assert runtime.embedding_tokens_used == 0
