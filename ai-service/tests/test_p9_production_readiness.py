from __future__ import annotations

import pytest

from app.ops.readiness import (
    Finding,
    OperationalCase,
    ReadinessConfig,
    RollbackReadiness,
    evaluate_readiness,
)


def safe_config() -> ReadinessConfig:
    return ReadinessConfig(
        rto_target_seconds=900,
        rto_denominator="successful_restart_drills",
        rpo_target_seconds=300,
        rpo_denominator="durable_checkpoint_samples",
        retention_days=30,
        recovery_window_days=30,
        observability_required=frozenset({"correlation_id", "audit_events", "queue_lag"}),
        observability_configured=frozenset({"correlation_id", "audit_events", "queue_lag"}),
        runbook_refs=("runbooks/incident-recovery.md",),
        dashboard_refs=("dashboards/long-running-readiness.json",),
        alert_refs=("alerts/critical-readiness.yaml",),
        rollback=RollbackReadiness(
            legacy_path_available=True,
            canary_feature_flag=True,
            rollback_drill_passed=True,
            owner="platform-oncall",
        ),
    )


def safe_cases() -> tuple[OperationalCase, ...]:
    return tuple(
        OperationalCase(case_id=case_id, category=category, passed=True, denominator=10)
        for case_id, category in (
            ("chaos-restart", "chaos_restart"),
            ("queue-duplicate-outage", "queue_duplicate_outage"),
            ("stream-saturation", "stream_saturation"),
            ("retention-gap", "retention_gap"),
            ("incident-audit", "incident_audit"),
            ("security-regression", "security_regression"),
        )
    )


def test_critical_auth_finding_fails_gate() -> None:
    result = evaluate_readiness(
        safe_config(),
        findings=(
            Finding(
                finding_id="AUTH-001",
                category="auth",
                severity="critical",
                status="open",
                summary="cross-tenant read is possible",
            ),
        ),
        cases=safe_cases(),
    )

    assert not result.passed
    assert "AUTH-001" in result.critical_findings
    assert any("critical finding" in reason for reason in result.reasons)


def test_safe_state_passes_and_result_is_deterministic() -> None:
    first = evaluate_readiness(safe_config(), cases=safe_cases())
    second = evaluate_readiness(safe_config(), cases=safe_cases())

    assert first.passed
    assert first.status == "PASS"
    assert first.to_dict() == second.to_dict()
    assert first.to_dict()["config"]["rto"]["denominator"] == "successful_restart_drills"
    assert first.to_dict()["config"]["rpo"]["denominator"] == "durable_checkpoint_samples"


def test_production_readiness_fails_when_required_operational_cases_are_empty() -> None:
    result = evaluate_readiness(safe_config())

    assert not result.passed
    assert any(check["check_id"] == "required_operational_cases" for check in result.failed_checks)
    required = next(check for check in result.failed_checks if check["check_id"] == "required_operational_cases")
    assert "chaos-restart" in required["details"]


def test_production_readiness_fails_when_one_required_case_is_missing() -> None:
    cases = tuple(case for case in safe_cases() if case.case_id != "security-regression")

    result = evaluate_readiness(safe_config(), cases=cases)

    assert not result.passed
    required = next(check for check in result.failed_checks if check["check_id"] == "required_operational_cases")
    assert "security-regression" in required["details"]


def test_rto_rpo_without_target_or_denominator_fail_closed() -> None:
    config = ReadinessConfig(
        rto_target_seconds=900,
        rto_denominator="",
        rpo_target_seconds=None,
        rpo_denominator="",
    )

    result = evaluate_readiness(config)

    assert not result.passed
    assert {check["check_id"] for check in result.failed_checks} >= {
        "rto_configured",
        "rpo_configured",
    }


def test_retention_must_cover_recovery_window() -> None:
    covers_recovery = ReadinessConfig(
        **{
            **safe_config().__dict__,
            "retention_days": 30,
            "recovery_window_days": 7,
        }
    )
    retention_too_short = ReadinessConfig(
        **{
            **safe_config().__dict__,
            "retention_days": 7,
            "recovery_window_days": 30,
        }
    )

    covers_result = evaluate_readiness(covers_recovery, cases=safe_cases())
    short_result = evaluate_readiness(retention_too_short, cases=safe_cases())

    assert covers_result.passed
    assert not short_result.passed
    assert any(check["check_id"] == "retention_configured" for check in short_result.failed_checks)


def test_duplicate_side_effect_and_retention_gap_fail_gate() -> None:
    cases = (
        OperationalCase(
            case_id="queue-duplicate-outage",
            category="duplicate_side_effect",
            passed=False,
            denominator=20,
            summary="duplicate publish was observed",
        ),
        OperationalCase(
            case_id="retention-gap",
            category="retention_gap",
            passed=False,
            denominator=20,
            summary="event gap had no snapshot fallback",
        ),
    )

    result = evaluate_readiness(safe_config(), cases=cases)

    assert not result.passed
    assert {check["check_id"] for check in result.failed_checks} >= {
        "case:queue-duplicate-outage",
        "case:retention-gap",
    }


def test_audit_and_security_regressions_fail_gate() -> None:
    cases = (
        OperationalCase(
            case_id="incident-audit",
            category="incident_audit",
            passed=False,
            denominator=5,
            summary="actor and correlation fields missing",
        ),
        OperationalCase(
            case_id="security-regression",
            category="security_regression",
            passed=False,
            denominator=12,
            summary="redaction regression",
        ),
    )

    result = evaluate_readiness(safe_config(), cases=cases)

    assert not result.passed
    assert {check["check_id"] for check in result.failed_checks} >= {
        "case:incident-audit",
        "case:security-regression",
    }


def test_rollback_requires_legacy_canary_and_successful_drill() -> None:
    config = safe_config()
    config = ReadinessConfig(
        **{
            **config.__dict__,
            "rollback": RollbackReadiness(
                legacy_path_available=True,
                canary_feature_flag=False,
                rollback_drill_passed=True,
                owner="platform-oncall",
            ),
        }
    )

    result = evaluate_readiness(config, cases=safe_cases())

    assert not result.passed
    assert any(check["check_id"] == "rollback_ready" for check in result.failed_checks)


def test_missing_observability_artifact_is_not_claimed_ready() -> None:
    config = safe_config()
    config = ReadinessConfig(
        **{
            **config.__dict__,
            "observability_configured": frozenset({"correlation_id"}),
            "dashboard_refs": (),
            "alert_refs": (),
        }
    )

    result = evaluate_readiness(config, cases=safe_cases())

    assert not result.passed
    assert {check["check_id"] for check in result.failed_checks} >= {
        "observability_configured",
        "dashboard_configured",
        "alerts_configured",
    }


def test_blank_artifact_references_are_not_configured() -> None:
    config = ReadinessConfig(
        **{
            **safe_config().__dict__,
            "runbook_refs": ("",),
            "dashboard_refs": ("  ",),
            "alert_refs": ("alerts/critical-readiness.yaml", None),
        }
    )

    result = evaluate_readiness(config, cases=safe_cases())

    assert not result.passed
    assert {check["check_id"] for check in result.failed_checks} >= {
        "runbook_configured",
        "dashboard_configured",
        "alerts_configured",
    }


def test_duplicate_case_ids_and_conflicting_categories_fail_closed() -> None:
    cases = list(safe_cases())
    cases.extend(
        [
            OperationalCase("chaos-restart", "wrong_category", True, 10),
            OperationalCase("chaos-restart", "chaos_restart", True, 10),
        ]
    )

    result = evaluate_readiness(safe_config(), cases=cases)

    assert not result.passed
    assert any(check["check_id"] == "duplicate_operational_case_ids" for check in result.failed_checks)
    assert any("chaos-restart" in reason for reason in result.reasons)


def test_every_case_category_and_boolean_denominator_are_validated() -> None:
    cases = list(safe_cases())
    cases[0] = OperationalCase("chaos-restart", "not_a_case_category", True, 10)
    cases[1] = OperationalCase("queue-duplicate-outage", "queue_duplicate_outage", True, True)

    result = evaluate_readiness(safe_config(), cases=cases)

    assert not result.passed
    failed_ids = {check["check_id"] for check in result.failed_checks}
    assert "case_category_validation" in failed_ids
    assert "case:queue-duplicate-outage" in failed_ids


@pytest.mark.parametrize("field", ["passed", "required"])
@pytest.mark.parametrize("value", ["false", 0, 1])
def test_operational_case_boolean_fields_are_strict(field: str, value: object) -> None:
    cases = list(safe_cases())
    original = cases[0]
    values = {
        "case_id": original.case_id,
        "category": original.category,
        "passed": original.passed,
        "denominator": original.denominator,
        "required": original.required,
        "summary": original.summary,
    }
    values[field] = value
    cases[0] = OperationalCase(**values)

    result = evaluate_readiness(safe_config(), cases=cases)

    assert not result.passed
    case_check = next(check for check in result.checks if check["check_id"] == "case:chaos-restart")
    assert not case_check["passed"]


@pytest.mark.parametrize("field", ["legacy_path_available", "canary_feature_flag", "rollback_drill_passed"])
@pytest.mark.parametrize("value", ["false", 0, 1])
def test_rollback_boolean_fields_are_strict(field: str, value: object) -> None:
    rollback_values = {
        "legacy_path_available": True,
        "canary_feature_flag": True,
        "rollback_drill_passed": True,
        "owner": "platform-oncall",
    }
    rollback_values[field] = value
    config = ReadinessConfig(
        **{
            **safe_config().__dict__,
            "rollback": RollbackReadiness(**rollback_values),
        }
    )

    result = evaluate_readiness(config, cases=safe_cases())

    assert not result.passed
    rollback_check = next(check for check in result.checks if check["check_id"] == "rollback_ready")
    assert not rollback_check["passed"]


@pytest.mark.parametrize(
    "field",
    ["rto_target_seconds", "rpo_target_seconds", "retention_days", "recovery_window_days"],
)
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_readiness_rejects_non_finite_numeric_slo_and_retention_values(field: str, value: float) -> None:
    config = ReadinessConfig(**{**safe_config().__dict__, field: value})

    result = evaluate_readiness(config, cases=safe_cases())

    assert not result.passed
    check_id = "retention_configured" if "retention" in field or "recovery" in field else (
        "rto_configured" if field.startswith("rto") else "rpo_configured"
    )
    check = next(check for check in result.checks if check["check_id"] == check_id)
    assert not check["passed"]


class ExplodingString(str):
    def strip(self, *args: object, **kwargs: object) -> str:
        raise AssertionError("caller-controlled string method must not run")


@pytest.mark.parametrize(
    "config_change",
    [
        {"rto_denominator": None},
        {"rollback": RollbackReadiness(owner=None)},
        {"rto_denominator": ExplodingString("successful_restart_drills")},
    ],
)
def test_readiness_malformed_config_fails_closed_without_exception(config_change: dict[str, object]) -> None:
    config = ReadinessConfig(**{**safe_config().__dict__, **config_change})

    result = evaluate_readiness(config, cases=safe_cases())

    assert result.status == "FAIL"
    assert not result.passed
    assert result.config == {"invalid": True}
    assert result.failed_checks == (
        {
            "check_id": "malformed_input",
            "kind": "input",
            "passed": False,
            "details": "readiness input is malformed",
        },
    )


@pytest.mark.parametrize(
    "cases, findings",
    [
        ([OperationalCase("chaos-restart", None, True, 10)], ()),
        ([OperationalCase("chaos-restart", "chaos_restart", True, None)], ()),
        ([object()], ()),
        ((), [object()]),
        (object(), ()),
    ],
)
def test_readiness_malformed_evidence_fails_closed_without_exception(cases: object, findings: object) -> None:
    result = evaluate_readiness(safe_config(), cases=cases, findings=findings)

    assert result.status == "FAIL"
    assert not result.passed
    assert result.config == safe_config().__dict__ or result.config
    assert result.failed_checks
