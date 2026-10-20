"""Deterministic evaluation gates for business cases and workflow events.

The module deliberately treats provenance and approval as part of the score
contract.  Candidate labels without an approved ground-truth record are not
business-accuracy evidence.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
import json
from typing import Any


@dataclass(frozen=True)
class GroundTruthRecord:
    """A labelled case and the provenance/approval status of those labels."""

    case_id: str
    source: str
    approved: bool
    labels: Mapping[str, Any] = field(default_factory=dict)


def _value(record: GroundTruthRecord | Mapping[str, Any], name: str, default: Any = None) -> Any:
    if isinstance(record, GroundTruthRecord):
        return getattr(record, name, default)
    if isinstance(record, Mapping):
        return record.get(name, default)
    return default


def _valid_non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_ground_truth(record: GroundTruthRecord | Mapping[str, Any]) -> bool:
    """Return ``True`` only for a complete, typed, provenance-bearing record."""

    return bool(
        isinstance(record, (GroundTruthRecord, Mapping))
        and _valid_non_empty_text(_value(record, "case_id"))
        and _valid_non_empty_text(_value(record, "source"))
        and isinstance(_value(record, "approved"), bool)
        and isinstance(_value(record, "labels"), Mapping)
    )


def _labels(record: GroundTruthRecord | Mapping[str, Any]) -> Mapping[str, Any]:
    labels = _value(record, "labels", {})
    return labels if isinstance(labels, Mapping) else {}


def score_case(
    expected: GroundTruthRecord | Mapping[str, Any],
    actual: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Score exact field equality, excluding unapproved business labels.

    ``covered`` counts expected fields present in ``actual``.  A missing field
    is therefore distinguishable from a covered but incorrect field.  An
    unapproved record returns no business score and a zero denominator.
    """

    valid = validate_ground_truth(expected)
    approved = _value(expected, "approved") if valid else False
    case_id = _value(expected, "case_id") if valid else None
    source = _value(expected, "source") if valid else None
    expected_labels = _labels(expected) if valid and approved else {}
    actual_labels = actual if isinstance(actual, Mapping) else {}

    field_scores: dict[str, dict[str, bool]] = {}
    covered = 0
    passed = 0
    for name, expected_value in expected_labels.items():
        is_covered = name in actual_labels
        is_passed = is_covered and actual_labels[name] == expected_value
        field_scores[str(name)] = {"covered": is_covered, "passed": is_passed}
        covered += int(is_covered)
        passed += int(is_passed)

    denominator = len(expected_labels)
    score = passed / denominator if denominator else None
    business_accuracy: float | str | None
    if not valid or not approved or denominator == 0:
        business_accuracy = "UNAVAILABLE"
        score = None
    else:
        business_accuracy = score

    return {
        "case_id": case_id,
        "source": source,
        "approved": bool(approved),
        "valid_ground_truth": valid,
        "denominator": denominator,
        "covered": covered,
        "passed": passed,
        "score": score,
        "business_accuracy": business_accuracy,
        "field_scores": field_scores,
    }


def _event_value(event: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in event:
            return event[name]
    return None


def _explicit_false(event: Mapping[str, Any], *names: str) -> bool:
    return any(event.get(name) is False for name in names)


def _stable_value(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=repr)
    except (TypeError, ValueError):
        return repr(value)


def _ordering_ok(events: Sequence[Mapping[str, Any]]) -> bool:
    if not events:
        return False
    per_run: dict[Any, list[int]] = {}
    for event in events:
        sequence = _event_value(event, "sequence", "seq", "order")
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
            return False
        run_id = _event_value(event, "run_id")
        per_run.setdefault(run_id, []).append(sequence)
    return all(values == list(range(1, len(values) + 1)) for values in per_run.values())


def _replay_ok(events: Sequence[Mapping[str, Any]]) -> bool:
    seen: dict[tuple[Any, Any], str] = {}
    for event in events:
        if _explicit_false(event, "replay_ok", "replay_consistent"):
            return False
        event_id = _event_value(event, "event_id", "id")
        if event_id is None:
            continue
        key = (_event_value(event, "run_id"), event_id)
        fingerprint = _stable_value({key: value for key, value in event.items() if key not in {"sequence", "seq", "order"}})
        prior = seen.get(key)
        if prior is not None and prior != fingerprint:
            return False
        seen[key] = fingerprint
    return True


def _idempotency_ok(events: Sequence[Mapping[str, Any]]) -> bool:
    seen: dict[tuple[Any, Any, Any], str] = {}
    for event in events:
        if _explicit_false(event, "idempotency_ok", "idempotent"):
            return False
        idempotency_key = _event_value(event, "idempotency_key", "idempotency")
        if idempotency_key is None:
            continue
        identity = _event_value(event, "tenant_id"), _event_value(event, "dossier_id"), idempotency_key
        fingerprint = _event_value(event, "command_digest", "command_id", "command", "payload", "result")
        if fingerprint is None:
            fingerprint = {key: value for key, value in event.items() if key not in {"event_id", "sequence", "seq", "order"}}
        fingerprint_text = _stable_value(fingerprint)
        prior = seen.get(identity)
        if prior is not None and prior != fingerprint_text:
            return False
        seen[identity] = fingerprint_text
    return True


def _recovery_ok(events: Sequence[Mapping[str, Any]]) -> bool:
    failure_states = {"failed", "error", "corrupt", "lost", "unrecoverable"}
    for event in events:
        if _explicit_false(event, "recovery_ok", "recovered", "resume_ok"):
            return False
        status = _event_value(event, "recovery", "recovery_status", "resume_status")
        if isinstance(status, str) and status.casefold() in failure_states:
            return False
        event_type = _event_value(event, "event_type", "type")
        if isinstance(event_type, str) and event_type.casefold() in {"recovery_failed", "recovery_error"}:
            return False
    return True


def _security_ok(events: Sequence[Mapping[str, Any]]) -> bool:
    scopes: dict[Any, set[tuple[Any, Any]]] = {}
    for event in events:
        if _explicit_false(event, "security_ok", "authorized", "scope_ok", "tenant_match", "dossier_match"):
            return False
        run_id = _event_value(event, "run_id")
        tenant_id = _event_value(event, "tenant_id")
        dossier_id = _event_value(event, "dossier_id")
        scopes.setdefault(run_id, set()).add((tenant_id, dossier_id))
    return all(len(scope) <= 1 for scope in scopes.values())


def score_workflow(events: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Score deterministic workflow invariants from an event sequence."""

    materialized = list(events) if not isinstance(events, list) else events[:]
    valid_events = all(isinstance(event, Mapping) for event in materialized)
    normalized = [event for event in materialized if isinstance(event, Mapping)]
    metrics = {
        "ordering_ok": valid_events and _ordering_ok(normalized),
        "replay_ok": valid_events and _replay_ok(normalized),
        "idempotency_ok": valid_events and _idempotency_ok(normalized),
        "recovery_ok": valid_events and bool(normalized) and _recovery_ok(normalized),
        "security_ok": valid_events and bool(normalized) and _security_ok(normalized),
    }
    passed = sum(int(value) for value in metrics.values())
    return {
        "denominator": len(materialized),
        **metrics,
        "passed": passed,
        "score": passed / len(metrics) if metrics else None,
    }


def _case_parts(case: Any) -> tuple[Any, Mapping[str, Any] | None]:
    if isinstance(case, Mapping) and "expected" in case:
        return case.get("expected"), case.get("actual")
    if isinstance(case, Sequence) and not isinstance(case, (str, bytes)) and len(case) == 2:
        return case[0], case[1]
    return None, None


def build_eval_report(cases: Iterable[Any], workflow_events: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Build an auditable report with business and workflow metrics."""

    case_scores = [score_case(*_case_parts(case)) for case in cases]
    approved_scores = [item for item in case_scores if item["valid_ground_truth"] and item["approved"]]
    denominator = sum(item["denominator"] for item in approved_scores)
    covered = sum(item["covered"] for item in approved_scores)
    passed = sum(item["passed"] for item in approved_scores)
    business_accuracy = passed / denominator if denominator else "UNAVAILABLE"
    workflow = score_workflow(workflow_events)
    claims: list[dict[str, Any]] = []
    if business_accuracy == "UNAVAILABLE":
        claims.append({
            "business_accuracy": "UNAVAILABLE",
            "reason": "không có approved ground truth có field để chấm",
        })
    else:
        claims.append({"business_accuracy": business_accuracy})

    metrics = {
        "case_denominator": len(case_scores),
        "approved_case_denominator": len(approved_scores),
        "denominator": denominator,
        "covered": covered,
        "passed": passed,
        "business_accuracy": business_accuracy,
        "workflow": workflow,
    }
    return {"metrics": metrics, "claims": claims, "cases": case_scores}


__all__ = [
    "GroundTruthRecord",
    "build_eval_report",
    "score_case",
    "score_workflow",
    "validate_ground_truth",
]
