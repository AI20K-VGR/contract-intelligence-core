"""Mutation tests cho gate; fixture tổng hợp không thay nhãn thật."""

from __future__ import annotations

from copy import deepcopy

import pytest

from evals.clause_frame_release import evaluate_release, measure, release_specs
from evals.clause_frame_scoring import PAIR_DISPOSITIONS, REQUIRED_METRICS
from evals.unit_metrics import UnitRecord

PROFILES = ("SALES", "SUPPLY_SERVICE", "LEASE", "CONSTRUCTION_WORK", "EMPLOYMENT", "NDA")
BADNESS = {"key_wrong_definite", "pair_false_duplicate", "citation_extra", "value_fabricated"}


def policy():
    return {
        "approved_by": "user", "approval_ref": "synthetic-test-only",
        "frozen_at": "2026-10-03T01:00:00Z",
        **dict.fromkeys(("dev_baseline_hash", "dev_gold_hash", "scorer_hash", "split_hash",
                         "historical_plan_a_card_hash"), "a" * 64),
        "metrics": [
            {"metric": name, "unit": "clause", "eligibility": "frozen-gold",
             "predicate": "exact", "strata": list(PROFILES), "minimum_units": 60,
             "stratum_minimum_units": 60,
             "threshold_source": "synthetic-test-only", "threshold": (
                 0 if name in BADNESS else 1 if name in {"citation_valid", "certainty_safety"} else .95),
             "direction": "max" if name in BADNESS else "min"}
            for name in sorted(REQUIRED_METRICS | {f"pair_precision.{d}" for d in PAIR_DISPOSITIONS})
        ],
    }


def records():
    return [UnitRecord(spec["metric"], f"item-{profile}-{i}", f"unit-{i}", True,
                       f"dossier-{profile}", split="heldout")
            for spec in policy()["metrics"] for profile in PROFILES for i in range(120)]


def evaluate(current=None, **kwargs):
    baseline = records()
    return evaluate_release(
        baseline, baseline if current is None else current, policy(),
        profiles={f"dossier-{profile}": profile for profile in PROFILES}, **kwargs,
    )


def test_missing_human_release_anchors_never_becomes_release_pass():
    result = evaluate()
    assert result["quality_status"] == "PASS(point)"
    assert result["release_status"] == "BLOCKED"
    assert "MANUAL_RELEASE_EVIDENCE_REQUIRED" in result["reasons"]


@pytest.mark.parametrize("metric", ["ordinary_slot.actor", "ordinary_slot.exception",
                                    "parameter_slot.base", "parameter_slot.period",
                                    "timeline_target", "timeline_date_role"])
@pytest.mark.parametrize("mutation", ["fail", "missing"])
def test_one_exact_unit_regression_blocks_despite_healthy_aggregate(metric, mutation):
    from dataclasses import replace
    current = records()
    index = next(i for i, unit in enumerate(current) if unit.metric == metric)
    if mutation == "missing":
        current.pop(index)
    else:
        current[index] = replace(current[index], passed=False)
    result = evaluate(current)
    assert result["quality_status"] == "FAIL"
    assert result["regression_count"] == 1
    assert "item-" not in str(result) and "dossier-" not in str(result)


@pytest.mark.parametrize("metric", ["pair_false_duplicate", "citation_extra", "value_fabricated"])
def test_new_failing_tripwire_blocks(metric):
    current = records() + [UnitRecord(metric, "new", "new", False, "dossier-SALES", split="heldout")]
    result = evaluate(current)
    assert result["quality_status"] == "FAIL"


def test_max_badness_threshold_is_converted_to_success_threshold():
    frozen = policy()
    next(spec for spec in frozen["metrics"] if spec["metric"] == "key_wrong_definite")["threshold"] = .03
    specs = release_specs(frozen)
    assert next(spec for spec in specs if spec.metric == "key_wrong_definite").threshold == .97


@pytest.mark.parametrize("metric", sorted(BADNESS))
def test_reversed_badness_direction_is_rejected(metric):
    frozen = policy()
    next(spec for spec in frozen["metrics"] if spec["metric"] == metric)["direction"] = "min"
    with pytest.raises(ValueError, match="direction"):
        release_specs(frozen)


def test_all_six_profiles_require_measurement_without_pooled_substitute():
    result = evaluate([unit for unit in records() if unit.cluster != "dossier-NDA"])
    assert result["quality_status"] == "FAIL"  # Previously PASS units disappeared.
    assert any(row["status"] == "NOT_MEASURED" for row in result["strata"])


def test_pair_sample_floor_is_120_even_if_policy_minimum_is_60():
    baseline = [unit for unit in records() if int(unit.unit_id.split("-")[1]) < 10]
    result = evaluate_release(baseline, baseline, policy(),
                              profiles={f"dossier-{p}": p for p in PROFILES})
    assert result["quality_status"] == "UNDERPOWERED"


def test_dec3_requires_120_total_not_120_in_each_dossier():
    frozen = policy()
    for spec in frozen["metrics"]:
        spec["stratum_minimum_units"] = 20
    baseline = [unit for unit in records() if int(unit.unit_id.split("-")[1]) < 20]
    result = evaluate_release(baseline, baseline, frozen,
                              profiles={f"dossier-{p}": p for p in PROFILES})
    assert result["quality_status"] == "PASS(point)"


def test_non_heldout_records_and_unmapped_dossier_are_rejected():
    from dataclasses import replace
    for changed in (replace(records()[0], split="dev"), replace(records()[0], cluster="unmapped")):
        with pytest.raises(ValueError):
            evaluate([changed])


def test_frozen_policy_is_not_mutated():
    frozen = policy()
    before = deepcopy(frozen)
    release_specs(frozen)
    assert frozen == before


def test_missing_one_disposition_precision_spec_is_not_complete_policy():
    frozen = policy()
    frozen["metrics"] = [spec for spec in frozen["metrics"] if spec["metric"] != "pair_precision.CUMULATIVE"]
    with pytest.raises(ValueError, match="disposition"):
        release_specs(frozen)


@pytest.mark.parametrize("metric", ["citation_valid", "certainty_safety"])
def test_hard_invariant_threshold_cannot_be_relaxed(metric):
    frozen = policy()
    next(spec for spec in frozen["metrics"] if spec["metric"] == metric)["threshold"] = .95
    with pytest.raises(ValueError, match="invariant"):
        release_specs(frozen)


def test_missing_isolation_blocks_before_loading_gold_or_calling_pipeline(tmp_path):
    called = []
    result = measure(tmp_path / "do-not-read-gold.json", tmp_path / "policy.json",
                     tmp_path / "baseline.json", tmp_path / "freeze.json", mode="local-only",
                     replay=lambda *args: called.append(args))
    assert result["quality_status"] == "BLOCKED"
    assert result["reasons"] == ["ISOLATION_OR_FREEZE_UNAVAILABLE"]
    assert not called and "do-not-read" not in str(result)


def test_json_role_claim_does_not_substitute_actual_access_denial(tmp_path):
    import json
    from getpass import getuser
    freeze = tmp_path / "freeze.json"
    freeze.write_text(json.dumps({"evaluator": getuser(), "tuner": getuser(),
                                 "isolation": {"approved": True, "denied": True}}))
    result = measure(tmp_path / "gold.json", tmp_path / "policy.json",
                     tmp_path / "baseline.json", freeze, mode="local-only")
    assert result["quality_status"] == "BLOCKED"
    assert "ISOLATION_NOT_PROVEN" in result["reasons"]


def synthetic_request():
    import json
    from pathlib import Path

    from evals.clause_frame_release import _canonical
    root = Path(__file__).resolve().parents[2]
    body = json.loads((root / "docs/contracts/examples/ai1.snapshot.v1.body.example.json").read_text(encoding="utf-8"))
    body["pages"][0]["lines"] = [{"line_id": "synthetic-line",
                                    "raw_text": "Bên A phải thanh toán 9007199254740993 VND",
                                    "bbox_source": "absent", "geometry_status": "absent", "words": []}]
    profile = {
        "schema_version": "ai2.semantic-profile.v1", "capability": "ai2.semantic.v1",
        "tenant_id": "tenant-release-test", "version": 1, "contract_type": "SALES",
        "alias_version": 0, "alias_digest": None, "aliases": [], "activation_state": "DRAFT_ONLY",
        "alias_proposal_minimum_length": None,
        "context_bounds": {"max_hops": 2, "max_nodes": 10, "max_context_tokens": 4000,
                           "max_output_tokens": 500, "max_llm_calls": 0, "max_seconds": 5},
    }
    profile["digest"] = _canonical(profile)
    return {
        "schema_version": "be.ai2.processing.request.v1", "request_id": "synthetic-eval",
        "idempotency_key": "synthetic-eval", "attempt": 1, "task_id": "synthetic-eval",
        "dossier_id": body["dossier_id"], "snapshots": [body],
        "snapshot_identities": [{"snapshot_id": body["snapshot_id"], "snapshot_version": "ai1.snapshot.v1",
                                 "source_digest": body["source_digest"], "snapshot_digest": _canonical(body)}],
        "dossier_members": [{"member_id": "body", "document_id": body["document_id"],
                             "snapshot_id": body["snapshot_id"], "role": "body", "source_digest": body["source_digest"]}],
        "role_relation_map": [], "semantic_profile": profile,
        "policy_flags": {"egress_allowed": False, "use_vector": False,
                         "budget_limits": {"max_processing_seconds": 30, "max_llm_calls": 0, "max_embedding_tokens": 0}},
        "service_envelope": {"schema_version": "ai2.service-envelope.v1", "issuer": "backend-service",
                             "audience": "vsf-ai2", "tenant_id": "tenant-release-test", "actor_id": "test",
                             "dossier_id": body["dossier_id"], "scopes": ["ai2.jobs.submit"], "key_id": "default",
                             "issued_at": 1, "expires_at": 2, "nonce": "synthetic-test-nonce", "payload_sha256": "a" * 64,
                             "signature": "a" * 64},
    }


def test_local_release_replay_executes_actual_adapter_idp_and_wire(monkeypatch):
    import hashlib
    import json
    from pathlib import Path

    from evals.clause_frame_release import production_replay
    source = synthetic_request()
    monkeypatch.setenv("AI2_PROCESSING_EGRESS_ALLOWED", "false")
    monkeypatch.setenv("AI2_SEMANTIC_ENABLED", "true")
    monkeypatch.setenv("AI2_SEMANTIC_CONTEXT_CAPS", json.dumps(source["semantic_profile"]["context_bounds"]))
    root = Path(__file__).resolve().parents[2]
    pins = {"prompt_hash": hashlib.sha256((root / "ai-service/app/pipeline/frame_context.py").read_bytes()).hexdigest()}
    observed = production_replay(source, "local-only", pins, {"profile": "SALES"})
    output = observed.output
    assert observed.usage["llm_calls_used"] == 0
    assert observed.usage["elapsed_seconds"] >= 0
    assert output["result"]["semantic_extension"]["frames"]
    assert any(frame["slots"]["amount"]["value"] == "9007199254740993"
               for frame in output["result"]["semantic_extension"]["frames"])


def test_enriched_replay_refuses_unverified_source_before_provider_call(monkeypatch):
    import hashlib
    import json
    from pathlib import Path

    from evals.clause_frame_release import production_replay
    source = synthetic_request()
    monkeypatch.setenv("AI2_SEMANTIC_ENABLED", "true")
    monkeypatch.setenv("AI2_SEMANTIC_CONTEXT_CAPS", json.dumps(source["semantic_profile"]["context_bounds"]))
    root = Path(__file__).resolve().parents[2]
    pins = {"prompt_hash": hashlib.sha256((root / "ai-service/app/pipeline/frame_context.py").read_bytes()).hexdigest(),
            "provider": "http://localhost:20128/v1"}
    with pytest.raises(ValueError, match="anonymized"):
        production_replay(source, "enriched", pins, {"profile": "SALES"})


def test_enriched_replay_cannot_override_signed_egress_denial(monkeypatch):
    import hashlib
    import json
    from pathlib import Path

    from evals.clause_frame_release import production_replay
    source = synthetic_request()
    monkeypatch.setenv("AI2_SEMANTIC_ENABLED", "true")
    monkeypatch.setenv("AI2_SEMANTIC_CONTEXT_CAPS", json.dumps(source["semantic_profile"]["context_bounds"]))
    root = Path(__file__).resolve().parents[2]
    pins = {"prompt_hash": hashlib.sha256((root / "ai-service/app/pipeline/frame_context.py").read_bytes()).hexdigest(),
            "provider": "http://localhost:20128/v1", "model": "synthetic-test-model"}
    with pytest.raises(ValueError, match="signed egress"):
        production_replay(source, "enriched", pins,
                          {"profile": "SALES", "verified_anonymized": True, "anonymization_ref": "synthetic-only"})


def measurement_fixture(tmp_path, monkeypatch):
    """Synthetic guard fixture; injected OS denial is not an isolation receipt."""
    import hashlib
    import json
    from dataclasses import asdict
    from pathlib import Path

    from evals import clause_frame_release as runner

    def write(name, value):
        path = tmp_path / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path, hashlib.sha256(path.read_bytes()).hexdigest()

    source = synthetic_request()
    source_path, source_hash = write("synthetic-source.json", source)
    frozen_policy = policy()
    frozen_policy["scorer_hash"] = hashlib.sha256(
        (Path(runner.__file__).parent / "clause_frame_scoring.py").read_bytes()).hexdigest()
    policy_path, policy_hash = write("synthetic-policy.json", frozen_policy)
    unit = {"metric": "ordinary_slot.actor", "item_id": "private-item", "unit_id": "private-unit",
            "dossier_id": "private-dossier", "profile": "SALES", "predicate": "exact",
            "evidence_ref": "synthetic-review", "path": ["value"], "identity_path": ["id"],
            "identity_expected": "private-identity", "expected": "B"}
    gold = {"schema": "ai2.clause-frame.gold.v1", "split": "heldout", "approved": True,
            "approval_ref": "synthetic-only", "consent_ref": "synthetic-only",
            "producer": "synthetic-producer", "reviewer": runner._principal(), "adjudicator": "synthetic-adjudicator",
            "dossiers": [{"id": "private-dossier", "profile": "SALES", "split": "heldout",
                          "source_kind": "real", "path": str(source_path), "sha256": source_hash,
                          "amendment_chain_verified": True, "amendment_review_ref": "synthetic-only"}],
            "units": [unit]}
    manifest_path, gold_hash = write("synthetic-gold.json", gold)
    runtime = {"provider": "http://localhost:20128/v1", "model": "synthetic-test-model",
               "prompt_hash": "a" * 64,
               "profile_hash": runner._canonical({"private-dossier": source["semantic_profile"]["digest"]}),
               "budget_hash": runner._canonical({"private-dossier": {
                   "context": source["semantic_profile"]["context_bounds"], "job": source["policy_flags"]["budget_limits"]}})}
    previous = UnitRecord(unit["metric"], unit["item_id"], unit["unit_id"], True, "private-dossier", split="heldout")
    old = {"schema": "ai2.clause-frame.matched-baseline.v1", "split": "heldout", "gold_hash": gold_hash,
           "policy_hash": policy_hash, "runtime_pins": runtime, "baseline_code_hash": "a" * 64,
           "units": [asdict(previous)]}
    baseline_path, baseline_hash = write("synthetic-baseline.json", old)
    receipt = {"schema": "ai2.clause-frame.candidate-freeze.v1", "approved_by": "user",
               "approval_ref": "synthetic-only", "evaluator": runner._principal(), "tuner": "synthetic-tuner",
               "retired": False, "deblinded": False, "gold_hash": gold_hash, "policy_hash": policy_hash,
               "baseline_hash": baseline_hash, "candidate_code_hash": runner.code_digest(),
               "frozen_at": "2026-10-03T03:00:00Z", "tuning_started_at": "2026-10-03T02:00:00Z",
               "holdout_first_visible_at": "2026-10-03T04:00:00Z",
               "measurement_started_at": "2026-10-03T05:00:00Z", "runtime_pins": runtime,
               **{name: frozen_policy[name] for name in ("dev_baseline_hash", "dev_gold_hash", "split_hash",
                                                         "historical_plan_a_card_hash")}}
    private_out = tmp_path / "private-output.json"
    private_out.write_bytes(b"{}")
    receipt["private_outputs"] = {"local-only": str(private_out)}
    freeze_path, _ = write("synthetic-freeze.json", receipt)
    monkeypatch.setattr(runner, "_denied_as_tuner", lambda *args: True)
    return (manifest_path, policy_path, baseline_path, freeze_path), receipt


def test_guarded_replay_reports_missing_metrics_without_leaking_private_units(tmp_path, monkeypatch):
    import json
    from pathlib import Path
    paths, receipt = measurement_fixture(tmp_path, monkeypatch)
    private_out = Path(receipt["private_outputs"]["local-only"])
    result = measure(*paths, mode="local-only", private_out=private_out,
                     replay=lambda *args: {"id": "private-identity", "value": "B"})
    assert result["quality_status"] == "NOT_MEASURED"
    assert result["release_status"] == "BLOCKED"
    assert "private-" not in str(result)
    private = json.loads(private_out.read_bytes())
    assert private["outputs"]["private-dossier"]["id"] == "private-identity"
    again = measure(*paths, mode="local-only", private_out=private_out)
    assert again["reasons"] == ["PRIVATE_OUTPUT_RESERVATION_FAILED"]


def test_private_results_storage_required_before_gold_or_replay(tmp_path, monkeypatch):
    paths, _ = measurement_fixture(tmp_path, monkeypatch)
    called = []
    result = measure(*paths, mode="local-only", replay=lambda *args: called.append(args))
    assert result["quality_status"] == "BLOCKED"
    assert result["reasons"] == ["PRIVATE_OUTPUT_ISOLATION_REQUIRED"]
    assert not called


@pytest.mark.parametrize("field,value", [("retired", True), ("deblinded", True),
                                         ("candidate_code_hash", "b" * 64),
                                         ("policy_hash", "b" * 64),
                                         ("frozen_at", "2026-10-03T06:00:00Z")])
def test_freeze_mutation_blocks_before_replay(tmp_path, monkeypatch, field, value):
    import json
    from pathlib import Path
    paths, receipt = measurement_fixture(tmp_path, monkeypatch)
    receipt[field] = value
    paths[3].write_text(json.dumps(receipt))
    called = []
    result = measure(*paths, mode="local-only", replay=lambda *args: called.append(args),
                     private_out=Path(receipt["private_outputs"]["local-only"]))
    assert result["quality_status"] == "BLOCKED"
    assert not called


def test_policy_drift_during_replay_blocks_and_keeps_errors_sanitized(tmp_path, monkeypatch):
    from pathlib import Path
    paths, receipt = measurement_fixture(tmp_path, monkeypatch)

    def replay(*args):
        paths[1].write_text("tampered")
        return {"id": "private-identity", "value": "B"}

    result = measure(*paths, mode="local-only", replay=replay,
                     private_out=Path(receipt["private_outputs"]["local-only"]))
    assert result["quality_status"] == "BLOCKED"
    assert result["reasons"] == ["INPUT_OR_CANDIDATE_DRIFT"]
    assert "private-" not in str(result)


def ablation_fixture():
    from dataclasses import asdict
    local = {"schema": "ai2.clause-frame.private-result.v1", "pins": {"gold_hash": "a" * 64},
             "mode": "local-only", "units": [asdict(UnitRecord("ordinary_slot.actor", "private-item", "private-unit", True, "private-dossier", split="heldout"))],
             "usage": []}
    import copy
    enriched = copy.deepcopy(local)
    enriched["mode"] = "enriched"
    return local, enriched


def test_paired_ablation_preserves_exact_identity_and_sanitizes_regression():
    from evals.clause_frame_release import paired_ablation
    local, enriched = ablation_fixture()
    enriched["units"][0]["passed"] = False
    result = paired_ablation(local, enriched)
    assert result["regressions"] == 1
    assert result["improvements"] == 0
    assert result["recommendation"] == "RETAIN_LOCAL_ONLY"
    assert "private-" not in str(result)


@pytest.mark.parametrize("mutation", ["pins", "missing", "cluster", "duplicate"])
def test_paired_ablation_rejects_unmatched_experiment(mutation):
    from evals.clause_frame_release import paired_ablation
    local, enriched = ablation_fixture()
    if mutation == "pins":
        enriched["pins"]["gold_hash"] = "b" * 64
    elif mutation == "missing":
        enriched["units"] = []
    elif mutation == "cluster":
        enriched["units"][0]["cluster"] = "other"
    else:
        enriched["units"] *= 2
    with pytest.raises(ValueError):
        paired_ablation(local, enriched)
