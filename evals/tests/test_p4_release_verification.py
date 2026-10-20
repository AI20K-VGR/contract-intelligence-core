from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.release_verification import (
    MutationMappingError,
    compare_ground_truth,
    replay_production,
    run_large_dossier_benchmark,
    run_mutation_matrix,
    score_citations,
    validate_corpus_separation,
    validate_mutation_mapping,
)


ROOT = Path(__file__).resolve().parents[1]


def _card(domain: str) -> dict:
    path = ROOT / "eval_config.json" if domain == "ai2_contract_package" else ROOT / "cards" / f"{domain}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_candidate_is_not_accuracy_ground_truth_without_review():
    candidate = {"cases": [{"case_id": "C-1", "validation_status": "UNVERIFIED"}]}
    result = validate_corpus_separation(candidate, {"cases": []})
    assert result["candidate_status"] == "UNVERIFIED"
    assert result["accuracy_claim_eligible"] is False


def test_empty_ground_truth_and_marker_citation_do_not_pass():
    assert compare_ground_truth({}, {})["status"] == "BLOCKED"
    assert score_citations("valid")["status"] == "UNVERIFIED"
    assert score_citations([{"citation_id": "c1"}])["status"] == "FAIL"


def test_mutation_mapping_is_explicit_and_kills_each_rule():
    card = _card("ai2_grounded_query")
    mapping = json.loads((ROOT / "mutation_mapping.json").read_text(encoding="utf-8"))["domains"]["ai2_grounded_query"]
    assert validate_mutation_mapping(card, mapping)["status"] == "PASS"
    from evals.eval_types.ai2_grounded_query.scorer import check_p0_gates
    from evals.mutation_fixtures import apply_named_mutation, build_scorer_fixture, score_scorer_fixture

    result = run_mutation_matrix(
        card,
        mapping,
        check_p0_gates,
        fixture_factory=build_scorer_fixture,
        mutation_applier=apply_named_mutation,
        result_scorer=score_scorer_fixture,
    )
    assert result["status"] == "BLOCKED", result
    assert all(item["scorer_killed"] for item in result["scorer_fixture_observations"])


def test_mutation_mapping_rejects_absent_control_field():
    card = _card("ai2_grounded_query")
    bad = {"rules": [{"rule_id": "x", "control_field": "does_not_exist", "negative_fixture": "x", "mutation": "x"}] * 8}
    with pytest.raises(MutationMappingError):
        validate_mutation_mapping(card, bad)


def test_mutation_noop_is_not_counted_as_killed():
    card = _card("ai2_grounded_query")
    mapping = json.loads((ROOT / "mutation_mapping.json").read_text(encoding="utf-8"))["domains"]["ai2_grounded_query"]
    mapping = {"rules": [dict(item) for item in mapping["rules"]]}
    mapping["rules"][0]["mutation"] = "noop"
    from evals.eval_types.ai2_grounded_query.scorer import check_p0_gates

    result = run_mutation_matrix(card, mapping, check_p0_gates)
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "mutation execution requires a production/scorer executor"


def test_production_replay_and_large_dossier_fixture_are_real():
    fixture = ROOT.parent / "ai-service" / "fixtures" / "eval_inputs" / "snapshots" / "ai1.full.v1.json"
    replay = replay_production(fixture)
    assert replay["parity_executed"] is True
    assert replay["status"] == "PASS", replay
    performance = run_large_dossier_benchmark(fixture, runs=2, limits={"pages": 2_000, "members": 2_000})
    assert performance["status"] == "UNVERIFIED", performance
    assert set(performance["metrics"]) >= {"seconds", "rss_mb", "tokens", "provider_calls", "quota"}
