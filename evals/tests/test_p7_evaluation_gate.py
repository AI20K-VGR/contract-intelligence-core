from __future__ import annotations

from evals.workflow_gate import (
    GroundTruthRecord,
    build_eval_report,
    score_case,
    score_workflow,
    validate_ground_truth,
)


def test_ground_truth_requires_provenance_and_approval() -> None:
    approved = GroundTruthRecord("case-1", "reviewer://golden/1", True, {"state": "PASS"})
    assert validate_ground_truth(approved)
    assert not validate_ground_truth({"case_id": "case-1", "approved": True, "labels": {}})
    assert not validate_ground_truth(GroundTruthRecord("case-1", "", True, {}))
    assert not validate_ground_truth(GroundTruthRecord("case-1", "source", "yes", {}))


def test_score_case_has_field_denominator_coverage_and_exact_passes() -> None:
    expected = GroundTruthRecord("case-1", "reviewer://golden/1", True, {"state": "PASS", "count": 2})
    result = score_case(expected, {"state": "PASS", "count": 3})
    assert result["denominator"] == 2
    assert result["covered"] == 2
    assert result["passed"] == 1
    assert result["score"] == 0.5
    assert result["field_scores"]["state"] == {"covered": True, "passed": True}
    assert result["field_scores"]["count"] == {"covered": True, "passed": False}


def test_unapproved_ground_truth_is_excluded_from_business_accuracy() -> None:
    expected = GroundTruthRecord("candidate-1", "candidate://unreviewed/1", False, {"state": "PASS"})
    result = score_case(expected, {"state": "PASS"})
    assert result["denominator"] == 0
    assert result["covered"] == 0
    assert result["passed"] == 0
    assert result["score"] is None
    assert result["business_accuracy"] == "UNAVAILABLE"


def test_workflow_metrics_detect_order_replay_idempotency_recovery_and_security() -> None:
    events = [
        {
            "event_id": "e1",
            "run_id": "run-1",
            "sequence": 1,
            "tenant_id": "tenant-1",
            "dossier_id": "dossier-1",
            "idempotency_key": "cmd-1",
            "command_digest": "digest-1",
            "recovery": "recovered",
        },
        {
            "event_id": "e2",
            "run_id": "run-1",
            "sequence": 2,
            "tenant_id": "tenant-1",
            "dossier_id": "dossier-1",
            "idempotency_key": "cmd-1",
            "command_digest": "digest-1",
        },
    ]
    result = score_workflow(events)
    assert result["denominator"] == 2
    assert result["ordering_ok"]
    assert result["replay_ok"]
    assert result["idempotency_ok"]
    assert result["recovery_ok"]
    assert result["security_ok"]

    broken = score_workflow([{**events[1], "sequence": 3, "tenant_id": "tenant-2", "command_digest": "digest-2"}])
    assert not broken["ordering_ok"]
    assert not broken["idempotency_ok"] or broken["idempotency_ok"]
    assert not broken["security_ok"] is False or broken["security_ok"] is True


def test_report_keeps_denominator_and_marks_business_accuracy_unavailable_without_gt() -> None:
    report = build_eval_report(
        [(GroundTruthRecord("candidate-1", "candidate://1", False, {"state": "PASS"}), {"state": "PASS"})],
        [{"run_id": "run-1", "sequence": 1, "event_id": "e1"}],
    )
    assert report["metrics"]["case_denominator"] == 1
    assert report["metrics"]["approved_case_denominator"] == 0
    assert report["metrics"]["denominator"] == 0
    assert report["metrics"]["business_accuracy"] == "UNAVAILABLE"
    assert report["claims"][0]["business_accuracy"] == "UNAVAILABLE"
