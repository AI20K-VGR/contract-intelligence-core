"""Bounded semantic alignment independent from a clause's full identity key.

The full clause key intentionally contains modality and family details so it
can certify duplicates.  Candidate discovery needs a smaller operation key in
order to surface two grounded statements that may disagree.  This module owns
that smaller key and the conservative context checks used before comparison.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Literal

from app.contracts.clause_frames import ClauseFrame, Slot

if TYPE_CHECKING:
    from app.pipeline.tenant_aliases import ApprovedAliasSnapshot


ACTION_SYMBOLS = frozenset({
    "PAY", "DELIVER", "ACCEPT", "NOTIFY", "TERMINATE", "COMPENSATE",
    "PENALTY", "DISCLOSE", "KEEP_CONFIDENTIAL", "RETURN", "REPAIR", "PERFORM",
})
QUALIFIER_SYMBOLS = frozenset({"BREACH", "DELAY", "NONPAYMENT", "DAMAGE", "CONFIDENTIALITY"})


@dataclass(frozen=True, slots=True)
class AlignmentKey:
    key: tuple[str, ...] | None
    reason: str


@dataclass(frozen=True, slots=True)
class ContextAssessment:
    state: Literal["EXACT", "DISJOINT", "PARTIAL", "UNKNOWN"]
    reasons: tuple[str, ...]


def alignment_key(
    frame: ClauseFrame,
    *,
    aliases: ApprovedAliasSnapshot | None = None,
    tenant_id: str | None = None,
    alias_version: int | None = None,
) -> AlignmentKey:
    """Return an operation key that deliberately omits polarity and values."""
    if frame.family in {"PARAMETER", "DEFINITION"}:
        parameter = frame.get("parameter")
        if parameter is not None and parameter.state == "GROUNDED" and isinstance(parameter.value, str):
            return AlignmentKey((frame.family, parameter.value), "grounded_parameter")
        # Older producers used the parameter family for ordinary obligation
        # frames.  Keep that payload readable while the new producer migrates.
        if frame.family == "PARAMETER":
            values: list[str] = [frame.profile, frame.family]
            for name, allowed in (("actor", None), ("action", ACTION_SYMBOLS)):
                value = _canonical(frame.get(name), name, allowed, aliases, tenant_id, alias_version)
                if value is None:
                    return AlignmentKey(None, f"missing_or_uncertain:{name}")
                values.append(value)
            return AlignmentKey(tuple(values), "legacy_parameter_operation")
        return AlignmentKey(None, "missing_or_uncertain:parameter")

    # Polarity is represented by ``modality_negation``.  OBLIGATION, RIGHT,
    # and PROHIBITION therefore share one operation family for candidate
    # discovery; comparison still retains the original family and disposition.
    operation_family = (
        "ACTIONABLE"
        if frame.family in {"OBLIGATION", "RIGHT", "PROHIBITION"}
        else frame.family
    )
    values: list[str] = [frame.profile, operation_family]
    for name, allowed in (("actor", None), ("action", ACTION_SYMBOLS)):
        slot = frame.get(name)
        value = _canonical(slot, name, allowed, aliases, tenant_id, alias_version)
        if value is None:
            return AlignmentKey(None, f"missing_or_uncertain:{name}")
        if name == "actor" and value in {"ANY_PARTY", "?", "UNRESOLVED"}:
            return AlignmentKey(None, "unresolved:actor")
        values.append(value)
    if frame.family == "REMEDY":
        qualifier = _canonical(frame.get("qualifier"), "qualifier", QUALIFIER_SYMBOLS,
                               aliases, tenant_id, alias_version)
        if qualifier is None:
            return AlignmentKey(None, "missing_or_uncertain:qualifier")
        values.append(qualifier)
    return AlignmentKey(tuple(values), "grounded_operation")


def context_assessment(left: ClauseFrame, right: ClauseFrame) -> ContextAssessment:
    """Assess object/condition/event overlap without converting legal meaning."""
    scope = _scope_assessment(left.get("object_scope"), right.get("object_scope"))
    if scope.state != "EXACT":
        return scope
    reasons: list[str] = []
    partial = False
    for name in ("condition", "exception", "temporal_trigger"):
        result = _slot_overlap(left.get(name), right.get(name), name)
        if result.state == "DISJOINT":
            return result
        if result.state in {"PARTIAL", "UNKNOWN"}:
            partial = partial or result.state == "PARTIAL"
            reasons.extend(result.reasons)
    if not reasons:
        return ContextAssessment("EXACT", ())
    if partial and all(reason == "interval_overlap" for reason in reasons):
        return ContextAssessment("PARTIAL", tuple(reasons))
    return ContextAssessment("UNKNOWN", tuple(reasons))


def scope_assessment(left: ClauseFrame, right: ClauseFrame) -> ContextAssessment:
    return _scope_assessment(left.get("object_scope"), right.get("object_scope"))


def same_operation(
    left: ClauseFrame,
    right: ClauseFrame,
    *,
    aliases: ApprovedAliasSnapshot | None = None,
    tenant_id: str | None = None,
    alias_version: int | None = None,
) -> bool:
    first = alignment_key(left, aliases=aliases, tenant_id=tenant_id, alias_version=alias_version)
    second = alignment_key(right, aliases=aliases, tenant_id=tenant_id, alias_version=alias_version)
    return first.key is not None and first.key == second.key


def _canonical(
    slot: Slot | None,
    name: str,
    allowed: frozenset[str] | None,
    aliases: ApprovedAliasSnapshot | None,
    tenant_id: str | None,
    alias_version: int | None,
) -> str | None:
    if slot is None or slot.state != "GROUNDED" or not isinstance(slot.value, str):
        return None
    value = slot.value
    if allowed is None or value in allowed:
        return value
    if aliases is not None and tenant_id is not None and alias_version is not None:
        resolution = aliases.resolve(tenant_id, alias_version, value, name)
        if resolution is not None and resolution.symbol in allowed:
            return resolution.symbol
    return None


def _scope_assessment(left: Slot | None, right: Slot | None) -> ContextAssessment:
    if left is None or right is None:
        return ContextAssessment("UNKNOWN", ("scope_unassessed",))
    if left.state in {"UNKNOWN", "UNSUPPORTED"} or right.state in {"UNKNOWN", "UNSUPPORTED"}:
        return ContextAssessment("UNKNOWN", ("scope_uncertain",))
    if left.state == right.state == "ABSENT":
        return ContextAssessment("EXACT", ())
    if left.state != right.state:
        return ContextAssessment("PARTIAL", ("scope_general_vs_specific",))
    if not isinstance(left.value, str) or not isinstance(right.value, str):
        return ContextAssessment("UNKNOWN", ("scope_untyped",))
    a, b = _fold(left.value), _fold(right.value)
    if a == b:
        return ContextAssessment("EXACT", ())
    if a and b and (a in b or b in a):
        return ContextAssessment("PARTIAL", ("scope_nested",))
    return ContextAssessment("DISJOINT", ("scope_disjoint",))


def _slot_overlap(left: Slot | None, right: Slot | None, name: str) -> ContextAssessment:
    if left is None or right is None:
        return ContextAssessment("UNKNOWN", (f"{name}_unassessed",))
    # UNKNOWN means the source was not grounded.  It must never be converted
    # into absence merely because both sides have the same diagnostic reason;
    # doing so can turn two unparsed conditions into a false DUPLICATE.  The
    # extractor emits ABSENT only after it has actually assessed that grammar.
    if left.state in {"UNKNOWN", "UNSUPPORTED"} or right.state in {"UNKNOWN", "UNSUPPORTED"}:
        return ContextAssessment("UNKNOWN", (f"{name}_uncertain",))
    if left.state == right.state == "ABSENT":
        return ContextAssessment("EXACT", ())
    if left.state != right.state:
        return ContextAssessment("PARTIAL", (f"{name}_general_vs_specific",))
    if left.value == right.value:
        return ContextAssessment("EXACT", ())
    if name == "temporal_trigger":
        return ContextAssessment("DISJOINT", ("trigger_differs",))
    if name in {"condition", "exception"}:
        interval = _interval_overlap(str(left.value), str(right.value))
        if interval is not None:
            return interval
    return ContextAssessment("UNKNOWN", (f"{name}_differs",))


def _interval_overlap(left: str, right: str) -> ContextAssessment | None:
    """Recognize only simple same-base numeric bounds; otherwise abstain."""
    pattern = re.compile(r"^\s*(.+?)\s*(<=|>=|<|>|≤|≥)\s*(-?\d+(?:[.,]\d+)?)\s*$")
    first, second = pattern.match(left), pattern.match(right)
    if first is None or second is None:
        return None
    first_base, second_base = _fold(first.group(1)), _fold(second.group(1))
    if not first_base or first_base != second_base:
        return None
    try:
        first_value = Decimal(first.group(3).replace(",", "."))
        second_value = Decimal(second.group(3).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    first_lower, first_upper = _bound(first.group(2), first_value)
    second_lower, second_upper = _bound(second.group(2), second_value)
    lower = _max_lower(first_lower, second_lower)
    upper = _min_upper(first_upper, second_upper)
    if lower is not None and upper is not None:
        if lower[0] > upper[0] or (lower[0] == upper[0] and not (lower[1] and upper[1])):
            return ContextAssessment("DISJOINT", ("interval_disjoint",))
    return ContextAssessment("PARTIAL", ("interval_overlap",))


def _bound(operator: str, value: Decimal) -> tuple[tuple[Decimal, bool] | None, tuple[Decimal, bool] | None]:
    if operator in {">", ">=", "≥"}:
        return (value, operator in {">=", "≥"}), None
    return None, (value, operator in {"<=", "≤"})


def _max_lower(*bounds):
    present = [bound for bound in bounds if bound is not None]
    if not present:
        return None
    value = max(item[0] for item in present)
    return (value, all(item[1] for item in present if item[0] == value))


def _min_upper(*bounds):
    present = [bound for bound in bounds if bound is not None]
    if not present:
        return None
    value = min(item[0] for item in present)
    return (value, all(item[1] for item in present if item[0] == value))


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.casefold())
    normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", normalized).strip()
