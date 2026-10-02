from __future__ import annotations

from evals.real_pipeline import load_catalog_case, run_processing, run_query


def test_offline_is_hermetic(monkeypatch, tmp_path) -> None:
    from app.llm.client import NineRouterClient
    from app.llm.embeddings import OpenAICompatibleEmbeddingClient

    from evals.golden.build_golden import build_golden
    from evals.golden.catalog import CONTRACTS

    calls = {"complete": 0, "discover": 0, "embed": 0}

    def count_complete(self, *args, **kwargs):
        calls["complete"] += 1
        return {}

    def count_discover(self, *args, **kwargs):
        calls["discover"] += 1

    def count_embed(self, *args, **kwargs):
        calls["embed"] += 1
        return []

    monkeypatch.setenv("AI2_VECTOR_RECALL_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    monkeypatch.setattr(NineRouterClient, "complete_json", count_complete)
    monkeypatch.setattr(OpenAICompatibleEmbeddingClient, "discover", count_discover)
    monkeypatch.setattr(OpenAICompatibleEmbeddingClient, "embed", count_embed)
    golden = tmp_path / "golden"
    assert build_golden(golden) == 0
    snapshot = golden / "snapshots" / "G01.json"
    query = CONTRACTS[0].questions[0].text
    result = run_query(snapshot, query)
    assert calls == {"complete": 0, "discover": 0, "embed": 0}
    assert result["status"] == "PASS"
    assert result["production_entry"] == "app.reasoning.stack.FourLayerReasoner.run"


def test_offline_is_deterministic(tmp_path, monkeypatch) -> None:
    from evals.golden.build_golden import build_golden
    from evals.golden.catalog import CONTRACTS

    monkeypatch.delenv("AI2_VECTOR_RECALL_ENABLED", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    golden = tmp_path / "golden"
    assert build_golden(golden) == 0
    snapshot = golden / "snapshots" / "G01.json"
    query = CONTRACTS[0].questions[0].text
    assert run_query(snapshot, query) == run_query(snapshot, query)


def test_production_entry_and_no_mirror() -> None:
    import evals.real_pipeline as pipeline

    assert pipeline.QUERY_ENTRY == "app.reasoning.stack.FourLayerReasoner.run"
    assert pipeline.PROCESSING_ENTRY == "app.pipeline.idp.run_idp"
    assert not hasattr(pipeline, "pipeline_mirror")


def test_catalog_loader_and_processing_entry_are_real(tmp_path) -> None:
    from evals.golden.build_golden import build_golden

    golden = tmp_path / "golden"
    assert build_golden(golden) == 0
    case = load_catalog_case(golden, "G01")
    assert case["contract_id"] == "G01"
    assert len(case["questions"]) == 12
    result = run_processing(case["snapshot"])
    assert result["status"] == "PASS", result
    assert result["parity_executed"] is True
    assert result["production_entry"] == "app.pipeline.idp.run_idp"
