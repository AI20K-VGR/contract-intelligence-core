from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from evals.clause_frame_baseline import (
    _historical_plan_a_hash,
    _split_hash,
    baseline,
    main,
    readiness,
)


def manifest(tmp_path):
    source = tmp_path / "source.json"
    source.write_text('{"schema_version":"ai1.snapshot.v1"}', encoding="utf-8")
    return {
        "schema": "ai2.clause-frame.gold.v1", "split": "dev",
        "producer": "drafter", "approved": True,
        "reviewer": "expert", "adjudicator": "adjudicator",
        "approval_ref": "review-receipt", "consent_ref": "consent",
        "holdout_receipt": {"approved": True, "evaluator": "external",
                            "isolation_ref": "acl-evidence", "split_hash": "abc"},
        "dossiers": [{"id": "d1", "split": "dev", "profile": "SALES",
                      "source_kind": "real", "amendment_chain_verified": True,
                      "path": str(source),
                      "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}],
        "units": [{"metric": "ordinary_slot.actor", "item_id": "d1/frame1",
                   "unit_id": "actor", "dossier_id": "d1", "profile": "SALES",
                   "path": ["semantic_extension", "rows", 0, "actor"],
                   "identity_path": ["semantic_extension", "rows", 0, "source_ref"],
                   "identity_expected": "p1/s1",
                   "expected": "SELLER", "predicate": "exact", "evidence_ref": "p1/s1"}],
    }


@pytest.mark.parametrize("field,value", [("approved", False), ("reviewer", "drafter"),
                                        ("approval_ref", ""), ("consent_ref", "")])
def test_draft_or_self_review_never_ready(tmp_path, field, value):
    gold = manifest(tmp_path)
    gold[field] = value
    assert readiness(gold)["status"] == "BLOCKED"


def test_source_hash_drift_and_fake_amendment_block(tmp_path):
    gold = manifest(tmp_path)
    gold["dossiers"][0]["sha256"] = "wrong"
    gold["dossiers"][0]["amendment_chain_verified"] = False
    assert readiness(gold)["status"] == "BLOCKED"


def test_missing_holdout_isolation_receipt_blocks(tmp_path):
    gold = manifest(tmp_path)
    gold["holdout_receipt"] = {}
    assert readiness(gold)["status"] == "BLOCKED"


@pytest.mark.parametrize("metric", ["pair_precision.INVENTED", "pair_precision."])
def test_unknown_pair_disposition_blocks_readiness(tmp_path, metric):
    gold = manifest(tmp_path)
    gold["units"][0]["metric"] = metric
    assert "UNSUPPORTED_METRIC" in readiness(gold)["reasons"]


def test_known_pair_disposition_is_allowed_for_calibration(tmp_path):
    gold = manifest(tmp_path)
    gold["units"][0]["metric"] = "pair_precision.DUPLICATE"
    assert readiness(gold)["status"] == "READY_FOR_CALIBRATION"


def test_invalid_policy_is_rejected_before_production_replay(tmp_path, monkeypatch):
    import evals.clause_frame_baseline as runner

    path = tmp_path / "gold.json"
    path.write_text(json.dumps(manifest(tmp_path)), encoding="utf-8")
    policy = tmp_path / "policy.json"
    policy.write_text("{}", encoding="utf-8")
    calls = []

    def replay(_):
        calls.append(True)
        return {"status": "CALIBRATION_ONLY", "units": []}

    monkeypatch.setattr(runner, "baseline", replay)
    output = tmp_path / "result.json"
    assert main(["baseline", "--manifest", str(path), "--split", "dev",
                 "--policy", str(policy), "--out", str(output)]) == 2
    assert calls == []
    assert "HUMAN_FREEZE_REQUIRED" in json.loads(output.read_text())["reasons"]


def test_mixed_manifest_refused_without_replay_or_holdout_disclosure(tmp_path):
    gold = manifest(tmp_path)
    gold["dossiers"].append({"id": "PRIVATE_HOLDOUT", "split": "heldout"})
    calls = []
    report = baseline(gold, replay=lambda x: calls.append(x))
    assert report["status"] == "BLOCKED"
    assert calls == []
    assert "PRIVATE_HOLDOUT" not in json.dumps(report)


def test_actual_output_missing_is_fail_not_zero_error(tmp_path):
    gold = manifest(tmp_path)
    before = copy.deepcopy(gold)
    report = baseline(gold, replay=lambda x: {"status": "PASS", "output": {}})
    assert report["units"][0]["passed"] is False
    assert report["coverage"]["missing"] == 1
    assert report["status"] == "CALIBRATION_ONLY"
    assert gold == before


def test_provider_failure_is_blocked_not_accuracy(tmp_path):
    report = baseline(manifest(tmp_path), replay=lambda x: {"status": "BLOCKED"})
    assert report["status"] == "BLOCKED"
    assert not report.get("units")


def test_cli_requires_dev_split_and_missing_file_emits_blocked(tmp_path):
    output = tmp_path / "result.json"
    args = ["readiness", "--manifest", str(tmp_path / "absent.json"),
            "--out", str(output)]
    with pytest.raises(SystemExit):
        main(args)
    assert main(args + ["--split", "dev"]) == 2
    assert json.loads(output.read_text())["status"] == "BLOCKED"


def test_malformed_existing_manifest_is_blocked_without_traceback(tmp_path):
    source = tmp_path / "bad.json"
    source.write_text("{broken", encoding="utf-8")
    out = tmp_path / "report.json"
    assert main(["readiness", "--manifest", str(source), "--split", "dev",
                 "--out", str(out)]) == 2
    assert json.loads(out.read_text())["status"] == "BLOCKED"


@pytest.mark.parametrize("target", ["manifest", "source"])
def test_cli_never_overwrites_gold_or_source(tmp_path, target):
    gold = manifest(tmp_path)
    path = tmp_path / "gold.json"
    path.write_text(json.dumps(gold), encoding="utf-8")
    output = path if target == "manifest" else tmp_path / "source.json"
    before = output.read_bytes()
    assert main(["readiness", "--manifest", str(path), "--split", "dev",
                 "--out", str(output)]) == 2
    assert output.read_bytes() == before


def test_nested_boolean_does_not_equal_number(tmp_path):
    gold = manifest(tmp_path)
    gold["units"][0]["expected"] = {"value": 1}
    report = baseline(gold, replay=lambda _: {"status": "PASS", "output": {
        "semantic_extension": {"rows": [{"actor": {"value": True}, "source_ref": "p1/s1"}]}}})
    assert report["units"][0]["passed"] is False


def test_wrong_frame_with_same_actor_cannot_pass(tmp_path):
    report = baseline(manifest(tmp_path), replay=lambda _: {"status": "PASS", "output": {
        "semantic_extension": {"rows": [{"actor": "SELLER", "source_ref": "p2/s2"}]}}})
    assert report["units"][0]["passed"] is False


def test_gold_string_path_is_invalid(tmp_path):
    gold = manifest(tmp_path)
    gold["units"][0]["path"] = "actor"
    assert readiness(gold)["status"] == "BLOCKED"


def test_readiness_rejects_unknown_metric_before_replay(tmp_path):
    gold = manifest(tmp_path)
    gold["units"][0]["metric"] = "made_up_metric"
    report = readiness(gold)
    assert "UNSUPPORTED_METRIC" in report["reasons"]


def test_readiness_rejects_unit_profile_mismatch(tmp_path):
    gold = manifest(tmp_path)
    gold["units"][0]["profile"] = "FINANCE"
    report = readiness(gold)
    assert "GOLD_UNIT_PROFILE_MISMATCH" in report["reasons"]


def test_readiness_rejects_malformed_source_hash(tmp_path):
    gold = manifest(tmp_path)
    gold["dossiers"][0]["sha256"] = "not-a-sha256"
    report = readiness(gold)
    assert "SOURCE_HASH_INVALID" in report["reasons"]


def test_source_mutated_during_replay_blocks_receipt(tmp_path):
    gold = manifest(tmp_path)
    def replay(_):
        (tmp_path / "source.json").write_text("changed", encoding="utf-8")
        return {"status": "PASS", "output": {}}
    assert baseline(gold, replay=replay)["status"] == "BLOCKED"


def test_manifest_changed_during_baseline_cannot_get_new_hash(tmp_path, monkeypatch):
    import evals.clause_frame_baseline as runner
    path = tmp_path / "gold.json"
    path.write_text(json.dumps(manifest(tmp_path)), encoding="utf-8")
    def mutate(_):
        path.write_text("{}", encoding="utf-8")
        return {"status": "CALIBRATION_ONLY", "units": [{"passed": True}]}
    monkeypatch.setattr(runner, "baseline", mutate)
    out = tmp_path / "out.json"
    assert main(["baseline", "--manifest", str(path), "--split", "dev",
                 "--out", str(out)]) == 2
    report = json.loads(out.read_text())
    assert report["status"] == "BLOCKED"
    assert not report.get("units")


def test_cli_policy_scores_diagnostics_without_promoting_quality(tmp_path, monkeypatch):
    import evals.clause_frame_baseline as runner
    from evals.clause_frame_scoring import REQUIRED_METRICS
    path = tmp_path / "gold.json"
    gold = manifest(tmp_path)
    path.write_text(json.dumps(gold), encoding="utf-8")
    scorer_hash = runner._digest(
        Path(runner.__file__).with_name("clause_frame_scoring.py")
    )
    policy = {"approved_by": "user", "approval_ref": "synthetic-test-only",
              "frozen_at": "2026-10-03T10:00:00Z",
              "dev_baseline_hash": "a" * 64,
              "dev_gold_hash": hashlib.sha256(path.read_bytes()).hexdigest(),
              "scorer_hash": scorer_hash,
              "split_hash": _split_hash(gold),
              "historical_plan_a_card_hash": _historical_plan_a_hash(),
              "metrics": [{"metric": metric, "unit": "slot", "eligibility": "gold",
                           "predicate": "exact", "strata": ["test"], "threshold_source": "test",
                           "minimum_units": 1, "threshold": 1, "direction": "min"}
                          for metric in sorted(REQUIRED_METRICS | {"pair_precision.DUPLICATE"})]}
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    monkeypatch.setattr(runner, "baseline", lambda _: {
        "status": "CALIBRATION_ONLY", "quality_ready": False, "units": [{
            "metric": "ordinary_slot.actor", "item_id": "d1/frame1", "unit_id": "actor",
            "passed": True, "cluster": "d1", "split": "dev"}]})
    output = tmp_path / "result.json"
    assert main(["baseline", "--manifest", str(path), "--split", "dev", "--policy",
                 str(policy_path), "--out", str(output)]) == 0
    report = json.loads(output.read_text())
    assert report["status"] == "CALIBRATION_ONLY"
    assert report["quality_ready"] is False
    assert report["diagnostic_metrics"]["status"] == "NOT_MEASURED"


@pytest.mark.parametrize("changed", ["scorer", "runner", "policy"])
def test_cli_runtime_input_drift_discards_units(tmp_path, monkeypatch, changed):
    import evals.clause_frame_baseline as runner
    path = tmp_path / "gold.json"
    path.write_text(json.dumps(manifest(tmp_path)), encoding="utf-8")
    policy_path = tmp_path / "policy.json"
    policy_path.write_text("{}", encoding="utf-8")
    mutated = False
    original_digest = runner._digest

    def digest(target):
        if mutated and target.name == {
            "scorer": "clause_frame_scoring.py", "runner": "clause_frame_baseline.py",
            "policy": "policy.json",
        }[changed]:
            return "changed-during-run"
        return original_digest(target)

    def replay(_):
        nonlocal mutated
        mutated = True
        return {"status": "CALIBRATION_ONLY", "quality_ready": False, "units": []}

    monkeypatch.setattr(runner, "_digest", digest)
    monkeypatch.setattr(runner, "baseline", replay)
    monkeypatch.setattr(runner, "validate_policy", lambda _, **__: {"status": "POLICY_VALIDATED"})
    monkeypatch.setattr(runner, "score_units", lambda *_: {"status": "NOT_MEASURED"})
    policy_path.write_text('{"metrics": []}', encoding="utf-8")
    output = tmp_path / "result.json"
    assert main(["baseline", "--manifest", str(path), "--split", "dev", "--policy",
                 str(policy_path), "--out", str(output)]) == 2
    report = json.loads(output.read_text())
    assert report["reasons"] == ["RUNTIME_INPUT_DRIFT"]
    assert "units" not in report
    assert "diagnostic_metrics" not in report


def test_policy_deleted_during_replay_is_blocked_with_original_pin(tmp_path, monkeypatch):
    import evals.clause_frame_baseline as runner
    path = tmp_path / "gold.json"
    path.write_text(json.dumps(manifest(tmp_path)), encoding="utf-8")
    policy_path = tmp_path / "policy.json"
    policy_path.write_text('{"metrics": []}', encoding="utf-8")
    original_hash = hashlib.sha256(policy_path.read_bytes()).hexdigest()

    def replay(_):
        policy_path.unlink()
        return {"status": "CALIBRATION_ONLY", "units": []}

    monkeypatch.setattr(runner, "baseline", replay)
    monkeypatch.setattr(runner, "validate_policy", lambda _, **__: {"status": "POLICY_VALIDATED"})
    monkeypatch.setattr(runner, "score_units", lambda *_: {"status": "NOT_MEASURED"})
    output = tmp_path / "result.json"
    assert main(["baseline", "--manifest", str(path), "--split", "dev", "--policy",
                 str(policy_path), "--out", str(output)]) == 2
    report = json.loads(output.read_text())
    assert report["reasons"] == ["RUNTIME_INPUT_DRIFT"]
    assert report["pins"]["policy_sha256"] == original_hash
    assert "units" not in report


def test_policy_hash_and_threshold_use_same_bytes(tmp_path, monkeypatch):
    import evals.clause_frame_baseline as runner
    path = tmp_path / "gold.json"
    path.write_text(json.dumps(manifest(tmp_path)), encoding="utf-8")
    policy_path = tmp_path / "policy.json"
    policy = {"metrics": [{"metric": "ordinary_slot.actor", "threshold": 1,
                           "direction": "min", "minimum_units": 1}]}
    original = json.dumps(policy)
    policy_path.write_text(original, encoding="utf-8")
    original_read_bytes = Path.read_bytes

    def swap_after_policy_read(target):
        value = original_read_bytes(target)
        if target == policy_path:
            changed = copy.deepcopy(policy)
            changed["metrics"][0]["threshold"] = 0
            policy_path.write_text(json.dumps(changed), encoding="utf-8")
        return value

    def replay(_):
        policy_path.write_text(original, encoding="utf-8")
        return {"status": "CALIBRATION_ONLY", "units": [{
            "metric": "ordinary_slot.actor", "item_id": "frame1", "unit_id": "actor",
            "passed": False, "cluster": "d1", "split": "dev"}]}

    monkeypatch.setattr(Path, "read_bytes", swap_after_policy_read)
    monkeypatch.setattr(runner, "baseline", replay)
    monkeypatch.setattr(runner, "validate_policy", lambda _, **__: {"status": "POLICY_VALIDATED"})
    output = tmp_path / "result.json"
    assert main(["baseline", "--manifest", str(path), "--split", "dev", "--policy",
                 str(policy_path), "--out", str(output)]) == 0
    report = json.loads(output.read_text())
    assert report["diagnostic_metrics"]["status"] == "FAIL"
    assert report["pins"]["policy_sha256"] == hashlib.sha256(original.encode()).hexdigest()
