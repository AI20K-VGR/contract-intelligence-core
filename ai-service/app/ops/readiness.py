"""Deterministic, dependency-free production-readiness checks for P9.

This module evaluates declared evidence and configuration only.  It does not
probe infrastructure, deploy traffic, or imply that HA/recovery is proven.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping


CRITICAL_FINDING_CATEGORIES = frozenset(
    {"auth", "data_loss", "duplicate_side_effect"}
)

REQUIRED_OPERATIONAL_CASES = {
    "chaos-restart": "chaos_restart",
    "queue-duplicate-outage": "queue_duplicate_outage",
    "stream-saturation": "stream_saturation",
    "retention-gap": "retention_gap",
    "incident-audit": "incident_audit",
    "security-regression": "security_regression",
}
VALID_OPERATIONAL_CATEGORIES = frozenset(REQUIRED_OPERATIONAL_CASES.values())


def _canonical(value: Any) -> str:
    if type(value) is not str:
        return ""
    return str.replace(str.replace(str.lower(str.strip(value)), "-", "_"), " ", "_")


def _positive(value: int | float | None) -> bool:
    if value is None or type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value) and value > 0
    except (OverflowError, ValueError):
        return False


def _refs_configured(refs: Iterable[Any]) -> bool:
    if type(refs) is not tuple:
        return False
    return bool(refs) and all(type(ref) is str and bool(str.strip(ref)) for ref in refs)


def _actual_bool(value: Any) -> bool:
    return type(value) is bool


def _valid_optional_number(value: Any) -> bool:
    if value is None:
        return True
    return type(value) in (int, float) and math.isfinite(value)


def _valid_numeric_shape(value: Any) -> bool:
    return value is None or type(value) in (bool, int, float)


def _valid_config(config: Any) -> bool:
    if type(config) is not ReadinessConfig or type(config.rollback) is not RollbackReadiness:
        return False
    if any(
        not _valid_numeric_shape(getattr(config, field_name))
        for field_name in (
            "rto_target_seconds", "rpo_target_seconds", "retention_days", "recovery_window_days"
        )
    ):
        return False
    if any(type(getattr(config, field_name)) is not str for field_name in ("rto_denominator", "rpo_denominator")):
        return False
    if type(config.rollback.owner) is not str:
        return False
    if type(config.observability_required) is not frozenset or type(config.observability_configured) is not frozenset:
        return False
    if any(type(value) is not str for value in (*config.observability_required, *config.observability_configured)):
        return False
    for field_name in ("runbook_refs", "dashboard_refs", "alert_refs"):
        refs = getattr(config, field_name)
        if type(refs) is not tuple or any(value is not None and type(value) is not str for value in refs):
            return False
    return True


def _valid_findings(findings: Any) -> tuple[Finding, ...] | None:
    try:
        values = tuple(findings)
    except Exception:
        return None
    if any(
        type(finding) is not Finding
        or any(type(getattr(finding, field_name)) is not str for field_name in (
            "finding_id", "category", "severity", "status", "summary"
        ))
        for finding in values
    ):
        return None
    return values


def _valid_cases(cases: Any) -> tuple[OperationalCase, ...] | None:
    try:
        values = tuple(cases)
    except Exception:
        return None
    if any(
        type(case) is not OperationalCase
        or any(type(getattr(case, field_name)) is not str for field_name in ("case_id", "category", "summary"))
        or not _valid_numeric_shape(case.denominator)
        for case in values
    ):
        return None
    return values


def _malformed_result() -> ReadinessResult:
    check = _check(
        "malformed_input",
        False,
        kind="input",
        details="readiness input is malformed",
    )
    return ReadinessResult(
        passed=False,
        status="FAIL",
        reasons=("readiness input is malformed",),
        critical_findings=(),
        failed_checks=(check,),
        checks=(check,),
        config={"invalid": True},
        limitations=(
            "bounded deterministic evaluation of supplied evidence/configuration only",
            "does not prove production deployment, HA, live traffic safety, or recovery success",
            "runbook, dashboard, alert, and rollback references are declared artifacts; external execution remains required",
        ),
    )


@dataclass(frozen=True)
class Finding:
    """A finding supplied by a security, data-loss, or side-effect review."""

    finding_id: str
    category: str
    severity: str
    status: str = "open"
    summary: str = ""

    @property
    def is_unresolved_critical(self) -> bool:
        status = _canonical(self.status)
        return status not in {"closed", "resolved", "accepted", "false_positive"} and (
            _canonical(self.severity) == "critical"
            or _canonical(self.category) in CRITICAL_FINDING_CATEGORIES
        )


@dataclass(frozen=True)
class OperationalCase:
    """A deterministic result for one P9 hardening scenario."""

    case_id: str
    category: str
    passed: bool
    denominator: int | float | None = None
    required: bool = True
    summary: str = ""


@dataclass(frozen=True)
class RollbackReadiness:
    legacy_path_available: bool = False
    canary_feature_flag: bool = False
    rollback_drill_passed: bool = False
    owner: str = ""


@dataclass(frozen=True)
class ReadinessConfig:
    """Declared SLO, retention, observability, and rollback configuration."""

    rto_target_seconds: int | float | None = None
    rto_denominator: str = ""
    rpo_target_seconds: int | float | None = None
    rpo_denominator: str = ""
    retention_days: int | float | None = None
    recovery_window_days: int | float | None = None
    observability_required: frozenset[str] = field(default_factory=frozenset)
    observability_configured: frozenset[str] = field(default_factory=frozenset)
    runbook_refs: tuple[str, ...] = ()
    dashboard_refs: tuple[str, ...] = ()
    alert_refs: tuple[str, ...] = ()
    rollback: RollbackReadiness = field(default_factory=RollbackReadiness)


@dataclass(frozen=True)
class ReadinessResult:
    passed: bool
    status: str
    reasons: tuple[str, ...]
    critical_findings: tuple[str, ...]
    failed_checks: tuple[dict[str, Any], ...]
    checks: tuple[dict[str, Any], ...]
    config: dict[str, Any]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return stable JSON-ready output with sorted check collections."""

        return {
            "passed": self.passed,
            "status": self.status,
            "reasons": list(self.reasons),
            "critical_findings": list(self.critical_findings),
            "failed_checks": list(self.failed_checks),
            "checks": list(self.checks),
            "config": self.config,
            "limitations": list(self.limitations),
        }

    as_dict = to_dict


def _check(
    check_id: str,
    passed: bool,
    *,
    kind: str,
    details: str,
    denominator: int | float | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "check_id": check_id,
        "kind": kind,
        "passed": bool(passed),
        "details": details,
    }
    if denominator is not None:
        result["denominator"] = denominator
    return result


def _config_dict(config: ReadinessConfig) -> dict[str, Any]:
    return {
        "rto": {
            "target_seconds": config.rto_target_seconds,
            "denominator": config.rto_denominator,
        },
        "rpo": {
            "target_seconds": config.rpo_target_seconds,
            "denominator": config.rpo_denominator,
        },
        "retention": {
            "days": config.retention_days,
            "recovery_window_days": config.recovery_window_days,
        },
        "observability": {
            "required": sorted(config.observability_required),
            "configured": sorted(config.observability_configured),
        },
        "artifacts": {
            "runbooks": sorted(config.runbook_refs, key=str),
            "dashboards": sorted(config.dashboard_refs, key=str),
            "alerts": sorted(config.alert_refs, key=str),
        },
        "rollback": asdict(config.rollback),
    }


def evaluate_readiness(
    config: ReadinessConfig,
    *,
    findings: Iterable[Finding] = (),
    cases: Iterable[OperationalCase] = (),
) -> ReadinessResult:
    """Evaluate P9 readiness fail-closed and return deterministic evidence.

    A readiness PASS means only that the supplied bounded checks and declared
    configuration are complete.  It is not evidence of deployment, HA, or a
    successful live recovery exercise.
    """

    if not _valid_config(config):
        return _malformed_result()
    supplied_cases = _valid_cases(cases)
    supplied_findings = _valid_findings(findings)
    if supplied_cases is None or supplied_findings is None:
        return _malformed_result()
    checks: list[dict[str, Any]] = []
    critical = sorted(
        finding.finding_id
        for finding in supplied_findings
        if finding.is_unresolved_critical
    )
    checks.append(
        _check(
            "critical_findings_clear",
            not critical,
            kind="finding",
            details="no unresolved critical auth/data-loss/duplicate-side-effect finding"
            if not critical
            else "unresolved critical finding present",
        )
    )

    rto_ok = _positive(config.rto_target_seconds) and bool(config.rto_denominator.strip())
    rpo_ok = _positive(config.rpo_target_seconds) and bool(config.rpo_denominator.strip())
    retention_ok = (
        _positive(config.retention_days)
        and _positive(config.recovery_window_days)
        and config.retention_days >= config.recovery_window_days
    )
    runbook_refs_ok = _refs_configured(config.runbook_refs)
    dashboard_refs_ok = _refs_configured(config.dashboard_refs)
    alert_refs_ok = _refs_configured(config.alert_refs)
    checks.extend(
        (
            _check(
                "rto_configured",
                rto_ok,
                kind="slo",
                details="RTO target and denominator configured"
                if rto_ok
                else "RTO target and non-empty denominator are required",
            ),
            _check(
                "rpo_configured",
                rpo_ok,
                kind="slo",
                details="RPO target and denominator configured"
                if rpo_ok
                else "RPO target and non-empty denominator are required",
            ),
            _check(
                "retention_configured",
                retention_ok,
                kind="retention",
                details="retention covers the declared recovery window"
                if retention_ok
                else "retention and recovery window are missing or inconsistent",
            ),
        )
    )

    missing_observability = sorted(
        config.observability_required - config.observability_configured
    )
    checks.extend(
        (
            _check(
                "observability_configured",
                not missing_observability,
                kind="observability",
                details="all required observability signals configured"
                if not missing_observability
                else f"missing signals: {', '.join(missing_observability)}",
            ),
            _check(
                "runbook_configured",
                runbook_refs_ok,
                kind="artifact",
                details="recovery runbook reference configured"
                if runbook_refs_ok
                else "recovery runbook reference missing",
            ),
            _check(
                "dashboard_configured",
                dashboard_refs_ok,
                kind="artifact",
                details="readiness dashboard reference configured"
                if dashboard_refs_ok
                else "readiness dashboard reference missing",
            ),
            _check(
                "alerts_configured",
                alert_refs_ok,
                kind="artifact",
                details="critical alert reference configured"
                if alert_refs_ok
                else "critical alert reference missing",
            ),
        )
    )

    rollback = config.rollback
    rollback_ok = all(
        (
            _actual_bool(rollback.legacy_path_available) and rollback.legacy_path_available,
            _actual_bool(rollback.canary_feature_flag) and rollback.canary_feature_flag,
            _actual_bool(rollback.rollback_drill_passed) and rollback.rollback_drill_passed,
            bool(rollback.owner.strip()),
        )
    )
    checks.append(
        _check(
            "rollback_ready",
            rollback_ok,
            kind="rollback",
            details="legacy path, canary flag, owner, and drill are present"
            if rollback_ok
            else "legacy path, canary flag, owner, and successful drill are required",
        )
    )

    case_ids = [case.case_id.strip() for case in supplied_cases if isinstance(case.case_id, str) and case.case_id.strip()]
    duplicate_ids = sorted({case_id for case_id in case_ids if case_ids.count(case_id) > 1})
    invalid_categories = sorted(
        {
            case.case_id.strip() if isinstance(case.case_id, str) else "<invalid-case-id>"
            for case in supplied_cases
            if not isinstance(case.category, str)
            or _canonical(case.category) not in VALID_OPERATIONAL_CATEGORIES
            or (
                isinstance(case.case_id, str)
                and case.case_id.strip() in REQUIRED_OPERATIONAL_CASES
                and _canonical(case.category) != REQUIRED_OPERATIONAL_CASES[case.case_id.strip()]
            )
        }
    )
    invalid_case_ids = sorted(
        {
            str(case.case_id)
            for case in supplied_cases
            if not isinstance(case.case_id, str) or not case.case_id.strip()
        }
    )
    supplied_by_id = {
        case.case_id.strip(): case
        for case in supplied_cases
        if isinstance(case.case_id, str) and case.case_id.strip()
    }
    missing_required = []
    if duplicate_ids:
        missing_required.append("duplicate case IDs: " + ", ".join(duplicate_ids))
    if invalid_case_ids:
        missing_required.append("invalid case IDs: " + ", ".join(invalid_case_ids))
    if invalid_categories:
        missing_required.append("invalid case categories: " + ", ".join(invalid_categories))
    for case_id, expected_category in REQUIRED_OPERATIONAL_CASES.items():
        case = supplied_by_id.get(case_id)
        if case is None:
            missing_required.append(f"{case_id} (missing)")
            continue
        if _canonical(case.category) != expected_category:
            missing_required.append(f"{case_id} (category must be {expected_category})")
            continue
        if not _actual_bool(case.passed) or not _actual_bool(case.required):
            missing_required.append(f"{case_id} (passed and required must be boolean)")
            continue
        if not case.passed:
            missing_required.append(f"{case_id} (failed)")
            continue
        if not _positive(case.denominator):
            missing_required.append(f"{case_id} (positive denominator required)")
    checks.append(
        _check(
            "required_operational_cases",
            not missing_required,
            kind="operational_evidence",
            details="all required operational cases have passing evidence"
            if not missing_required
            else "missing or failed required cases: " + ", ".join(missing_required),
        )
    )
    checks.append(
        _check(
            "duplicate_operational_case_ids",
            not duplicate_ids,
            kind="operational_evidence",
            details="case IDs are unique"
            if not duplicate_ids
            else "duplicate case IDs: " + ", ".join(duplicate_ids),
        )
    )
    checks.append(
        _check(
            "case_category_validation",
            not invalid_categories,
            kind="operational_evidence",
            details="all supplied case categories are recognized and match their case IDs"
            if not invalid_categories
            else "invalid case categories: " + ", ".join(invalid_categories),
        )
    )

    for index, case in enumerate(supplied_cases, start=1):
        case_id = case.case_id.strip() if isinstance(case.case_id, str) else "<invalid-case-id>"
        category = _canonical(case.category) if isinstance(case.category, str) else ""
        passed_type_ok = _actual_bool(case.passed)
        required_type_ok = _actual_bool(case.required)
        case_passed = case.passed if passed_type_ok else False
        case_required = case.required if required_type_ok else True
        category_ok = category in VALID_OPERATIONAL_CATEGORIES and (
            case_id not in REQUIRED_OPERATIONAL_CASES
            or category == REQUIRED_OPERATIONAL_CASES[case_id]
        )
        denominator_type_ok = case.denominator is None or type(case.denominator) in (int, float)
        denominator_ok = (not case_required or _positive(case.denominator)) and denominator_type_ok
        boolean_types_ok = passed_type_ok and required_type_ok
        passed = (
            boolean_types_ok
            and (not case_required or case_passed)
            and denominator_ok
            and category_ok
            and bool(case_id)
        )
        details = case.summary or (
            "case passed" if case_passed else "case failed"
        )
        if not category_ok:
            details = f"{details}; category is invalid for this case"
        if not boolean_types_ok:
            details = f"{details}; passed and required must be boolean"
        if not denominator_type_ok:
            details = f"{details}; denominator must be a non-boolean number"
        if case_required and not denominator_ok:
            details = f"{details}; positive denominator is required"
        checks.append(
            _check(
                f"case:{case_id}" if case_ids.count(case_id) == 1 else f"case:{case_id}#{index}",
                passed,
                kind=_canonical(case.category),
                details=details,
                denominator=case.denominator,
            )
        )

    checks.sort(key=lambda item: item["check_id"])
    failed = tuple(check for check in checks if not check["passed"])
    reasons = tuple(
        (
            f"critical finding gate failed: {', '.join(critical)}"
            if check["check_id"] == "critical_findings_clear"
            else f"readiness check failed: {check['check_id']} ({check['details']})"
        )
        for check in failed
    )
    passed = not failed
    return ReadinessResult(
        passed=passed,
        status="PASS" if passed else "FAIL",
        reasons=reasons,
        critical_findings=tuple(critical),
        failed_checks=failed,
        checks=tuple(checks),
        config=_config_dict(config),
        limitations=(
            "bounded deterministic evaluation of supplied evidence/configuration only",
            "does not prove production deployment, HA, live traffic safety, or recovery success",
            "runbook, dashboard, alert, and rollback references are declared artifacts; external execution remains required",
        ),
    )


__all__ = [
    "CRITICAL_FINDING_CATEGORIES",
    "Finding",
    "OperationalCase",
    "REQUIRED_OPERATIONAL_CASES",
    "ReadinessConfig",
    "ReadinessResult",
    "RollbackReadiness",
    "evaluate_readiness",
]
