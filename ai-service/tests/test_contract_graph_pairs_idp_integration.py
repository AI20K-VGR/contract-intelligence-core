from __future__ import annotations

import pytest

from app.pipeline.contract_graph import pair_builder
from app.pipeline.idp import run_idp
from fixtures import envelope
from fixtures.contract_graph_pair_records import FakePairLLM, pair_record, pair_record_embedded
from scripts.capture_idp_golden import deterministic_uuid4


@pytest.fixture(autouse=True)
def flags(monkeypatch):
    monkeypatch.setenv("AI2_CONTRACT_GRAPH_ENABLED", "1")
    monkeypatch.setenv("AI2_CONTRACT_GRAPH_PAIRS_ENABLED", "1")
    monkeypatch.setenv("AI2_CONTRACT_GRAPH_PAIRS_MODEL", "claude-fixture")
    for key in ("AI2_CONTRACT_GRAPH_PAIRS_BASE_URL", "AI2_CONTRACT_GRAPH_PAIRS_API_KEY"):
        monkeypatch.delenv(key, raising=False)


def run(*, embedded=False, consent=True, llm=None, egress=True, runtime=None):
    rec = pair_record_embedded(test_pairs=True) if embedded else pair_record()
    rec.content_sharing_consent = consent
    env = envelope()
    rec.egress_approved = egress
    with deterministic_uuid4():
        res = run_idp(rec, env, llm=llm, job_id="job_pairs", runtime=runtime)
    return rec, res


def test_no_consent_is_rule_only_without_llm_call_and_one_issue():
    llm = FakePairLLM()
    rec, res = run(consent=False, llm=llm)
    assert llm.calls == 0
    cov = res.contribution.coverage["contract_graph"]["pairs"]
    assert cov["rule_only_reason"] == "NO_CONSENT" and cov["candidates_kept"] > 0
    issues = res.contribution.evidence_issues
    assert sum(i.missing == "CONTRACT_GRAPH_PAIRS_LIMITED_COVERAGE" for i in issues) == 1
    assert issues[-1].missing == "CONTRACT_GRAPH_PAIRS_LIMITED_COVERAGE"
    assert rec.pair_relations_ran and not rec.pair_relations


def test_consent_llm_mode_emits_relations_and_conflict_candidate():
    rec, res = run(llm=FakePairLLM())
    assert {r.label.value for r in rec.pair_relations} >= {"GENERAL_SPECIFIC", "CONFLICT"}
    assert rec.pair_relations_ran
    assert res.contribution.candidates[-1].candidate_id.startswith("cand_pair_")
    assert not any(i.missing == "CONTRACT_GRAPH_PAIRS_LIMITED_COVERAGE" for i in res.contribution.evidence_issues)


@pytest.mark.parametrize("embedded", [False, True])
def test_existing_review_item_ids_prefix_preserved_separate_file_and_embedded(monkeypatch, embedded):
    monkeypatch.setenv("AI2_CONTRACT_GRAPH_PAIRS_ENABLED", "0")
    old, before = run(embedded=embedded, llm=FakePairLLM())
    monkeypatch.setenv("AI2_CONTRACT_GRAPH_PAIRS_ENABLED", "1")
    new, after = run(embedded=embedded, llm=FakePairLLM())
    ids = [i.review_item_id for i in old.review_items]
    assert [i.review_item_id for i in new.review_items][:len(ids)] == ids
    assert before.contribution.contract_context == after.contribution.contract_context
    assert [c for c in after.contribution.candidates if not c.candidate_id.startswith("cand_pair_")] == before.contribution.candidates
    assert old.contract_edges == new.contract_edges


def test_pairs_builder_failure_is_issue_not_job_failure(monkeypatch):
    def boom(*args, **kwargs):
        raise ValueError("secret raw contract must not leak")
    monkeypatch.setattr(pair_builder, "build_pair_relations", boom)
    rec, res = run(llm=FakePairLLM())
    assert res.status.value == "SUCCEEDED" and not rec.pair_relations_ran
    assert res.contribution.evidence_issues[-1].missing == "CONTRACT_GRAPH_PAIRS_FAILED"
    assert "secret" not in res.contribution.evidence_issues[-1].reason
    assert res.contribution.coverage["contract_graph"]["pairs"]["status"] == "FAILED"
    assert rec.contract_edges


def test_graph_failure_skips_pairs(monkeypatch):
    from app.pipeline.contract_graph import builder
    calls = []
    def boom(*args, **kwargs):
        raise ValueError("graph")
    monkeypatch.setattr(builder, "build_contract_graph", boom)
    monkeypatch.setattr(pair_builder, "build_pair_relations", lambda *a, **k: calls.append(1))
    rec, res = run()
    assert not calls and not rec.pair_relations_ran
    assert res.contribution.coverage["contract_graph"]["pairs"]["status"] == "SKIPPED_GRAPH_FAILED"


def test_llm_calls_counted_in_runtime_snapshot():
    llm = FakePairLLM()
    _, res = run(llm=llm)
    cov = res.contribution.coverage
    assert cov["runtime"]["llm_calls_used"] >= cov["contract_graph"]["pairs"]["llm_calls"] > 0


@pytest.mark.parametrize("mode,reason,batches,expected", [
    ("llm", None, 1, True), ("llm", "LLM_FALLBACK", 0, False),
    ("rule_only", "NO_CONSENT", 0, True), ("rule_only", "EGRESS_DENIED", 0, False),
    ("rule_only", "MODEL_UNSET", 0, False), ("rule_only", "BUDGET_EXHAUSTED", 0, False),
    ("rule_only", "DEADLINE", 0, False), ("rule_only", "LLM_UNAVAILABLE", 0, False),
])
def test_ran_semantics(monkeypatch, mode, reason, batches, expected):
    from app.contracts.contract_graph import PairResult
    monkeypatch.setattr(pair_builder, "build_pair_relations", lambda *a, **k:
                        PairResult(mode=mode, rule_only_reason=reason, prompt_version="pairs-v1", batches_completed=batches))
    rec, _ = run()
    assert rec.pair_relations_ran is expected


def test_pairs_flag_read_once_per_run(monkeypatch):
    original = pair_builder.build_pair_relations
    def flip(*a, **k):
        monkeypatch.setenv("AI2_CONTRACT_GRAPH_PAIRS_ENABLED", "0")
        return original(*a, **k)
    monkeypatch.setattr(pair_builder, "build_pair_relations", flip)
    rec, res = run(consent=False)
    assert rec.pair_relations_ran
    assert res.contribution.coverage["contract_graph"]["pairs"]["mode"] == "rule_only"


def test_injection_clause_counted_and_cannot_fabricate():
    llm = FakePairLLM(malicious=True)
    rec, res = run(llm=llm)
    assert res.contribution.coverage["contract_graph"]["pairs"]["injection_signals"] >= 1
    assert "Ignore previous" in "".join(llm.prompts)
    assert res.contribution.coverage["contract_graph"]["pairs"]["rejected"]["unknown_pair"] >= 1
    assert not any("fabricated" in r.relation_id for r in rec.pair_relations)


def test_external_law_reference_not_a_candidate():
    llm = FakePairLLM()
    _, res = run(llm=llm)
    assert res.contribution.coverage["contract_graph"]["pairs"]["excluded_external_ref"] >= 1


@pytest.mark.parametrize("llm,egress,reason", [(None, True, "LLM_UNAVAILABLE"), (FakePairLLM(), False, "EGRESS_DENIED")])
def test_rule_only_reasons_in_coverage(llm, egress, reason):
    _, res = run(llm=llm, egress=egress)
    assert res.contribution.coverage["contract_graph"]["pairs"]["rule_only_reason"] == reason


@pytest.mark.parametrize("reason", ["MODEL_UNSET", "BUDGET_EXHAUSTED", "DEADLINE"])
def test_rule_only_model_budget_deadline_without_provider_call(monkeypatch, reason):
    from app.pipeline.runtime import ProcessingRuntime

    if reason == "MODEL_UNSET":
        monkeypatch.setenv("AI2_CONTRACT_GRAPH_PAIRS_MODEL", "")
    runtime = ProcessingRuntime(egress_allowed=True, max_llm_calls=0 if reason == "BUDGET_EXHAUSTED" else 20,
                                max_processing_seconds=20 if reason == "DEADLINE" else 300)
    llm = FakePairLLM()
    rec, res = run(llm=llm, runtime=runtime)
    assert res.contribution.coverage["contract_graph"]["pairs"]["rule_only_reason"] == reason
    assert llm.calls == 0 and not rec.pair_relations_ran


def test_actual_provider_fallback_keeps_ran_false():
    class BrokenLLM(FakePairLLM):
        def complete_json(self, *a, **k):
            raise ValueError("provider unavailable")

    rec, res = run(llm=BrokenLLM())
    assert not rec.pair_relations_ran and not rec.pair_relations
    cov = res.contribution.coverage["contract_graph"]["pairs"]
    assert cov["batches_completed"] == 0 and cov["stopped_reason"] == "LLM_FALLBACK"


def test_kafka_and_http_share_adapter_consent():
    import inspect

    from app.api import main
    from app.transport import kafka_idp_worker as kafka
    assert "adapt_be_ai2_processing_request" in inspect.getsource(main)
    assert "adapt_be_ai2_processing_request" in inspect.getsource(kafka)
