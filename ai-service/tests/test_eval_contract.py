from fixtures.catalog import all_cases
from fixtures.eval_suite import all_eval_cases, synthetic_cases


def test_eval_corpus_has_65_existing_and_30_synthetic_cases():
    existing = all_eval_cases()
    synthetic = synthetic_cases()
    assert len(synthetic) == 30
    assert len(existing) == 95
    assert set(all_cases()).isdisjoint(set(synthetic))
    assert all(item.tags and "synthetic" in item.tags for item in synthetic.values())


def test_eval_corpus_has_no_pdf_bytes_and_unique_snapshot_digests():
    cases = all_eval_cases()
    assert all(not hasattr(pack.record, "pdf_bytes") for pack in cases.values())
    synthetic_digests = [pack.record.pins.source_snapshot_digest for pack in synthetic_cases().values()]
    assert len(synthetic_digests) == len(set(synthetic_digests))


def test_policy_synthetic_case_is_blocked_by_pipeline():
    from app.pipeline.idp import run_idp

    pack = synthetic_cases()["SYN-030"]
    result = run_idp(pack.record, pack.envelope, llm=None)
    assert result.review_state.value == "BLOCKED"
    assert any(issue.code in {"BUDGET_EXCEEDED", "INDEX_LEASED"} for issue in result.handoff_issues)
