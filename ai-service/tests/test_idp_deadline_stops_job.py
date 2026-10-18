from app.contracts.models import JobStatus
from app.pipeline import idp
from app.pipeline.runtime import ProcessingRuntime


def test_job_past_its_deadline_skips_the_remaining_stages_and_keeps_its_facts(monkeypatch):
    from fixtures import envelope
    from fixtures.contract_graph_pair_records import pair_record

    monkeypatch.setenv("AI2_CONTRACT_GRAPH_ENABLED", "1")
    now = [0.0]
    runtime = ProcessingRuntime(
        egress_allowed=False, max_processing_seconds=10, max_llm_calls=0, clock=lambda: now[0]
    )
    real_dedupe = idp._dedupe_same_published_key

    def slow_extraction(facts):
        now[0] = 100.0  # extraction ran past the deadline without any LLM call
        return real_dedupe(facts)

    reached = []
    monkeypatch.setattr(idp, "_dedupe_same_published_key", slow_extraction)
    monkeypatch.setattr(
        "app.pipeline.contract_graph.builder.build_contract_graph",
        lambda *a, **k: reached.append("graph"),
    )

    result = idp.run_idp(pair_record(), envelope(), llm=None, runtime=runtime)

    assert result.status == JobStatus.SUCCEEDED
    assert "PROCESSING_TIMEOUT" in [i.code for i in result.handoff_issues]
    assert reached == []
