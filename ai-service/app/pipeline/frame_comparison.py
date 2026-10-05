"""Scope-first semantic comparison over evidence-backed slots."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from app.contracts.clause_frames import ClauseFrame, FramePair
from app.pipeline.clause_keys import normalize_key
from app.pipeline.semantic_alignment import (
    alignment_key,
    context_assessment,
    scope_assessment,
)

if TYPE_CHECKING:
    from app.pipeline.tenant_aliases import ApprovedAliasSnapshot


def compare_frames(
    left: ClauseFrame,
    right: ClauseFrame,
    *,
    aliases: ApprovedAliasSnapshot | None = None,
    tenant_id: str | None = None,
    alias_version: int | None = None,
) -> FramePair:
    if left.dossier_id != right.dossier_id:
        raise ValueError("cross-dossier comparison")

    def result(disposition: str, reason: str) -> FramePair:
        return FramePair(left.frame_id, right.frame_id, disposition, reason,
                         left.evidence, right.evidence)

    if left.profile != right.profile:
        return result("NOT_COMPARABLE", "different_contract_profile")

    scope = scope_assessment(left, right)
    if scope.state == "UNKNOWN":
        return result("NEEDS_REVIEW_UNPARSED", ";".join(scope.reasons))
    if scope.state == "DISJOINT":
        return result("SCOPE_DIFFERS", ";".join(scope.reasons))
    if scope.state == "PARTIAL":
        return result("GENERAL_VS_SPECIFIC", ";".join(scope.reasons) or "one_scope_absent")

    left_key = normalize_key(left, aliases=aliases, tenant_id=tenant_id, alias_version=alias_version)
    right_key = normalize_key(right, aliases=aliases, tenant_id=tenant_id, alias_version=alias_version)
    if left_key.certainty != "DEFINITE" or right_key.certainty != "DEFINITE":
        return result("NEEDS_REVIEW_BACKOFF", ";".join((left_key.reason, right_key.reason)))

    left_alignment = alignment_key(
        left, aliases=aliases, tenant_id=tenant_id, alias_version=alias_version
    )
    right_alignment = alignment_key(
        right, aliases=aliases, tenant_id=tenant_id, alias_version=alias_version
    )
    if left_alignment.key is None or right_alignment.key is None:
        return result("NEEDS_REVIEW_BACKOFF", ";".join((left_alignment.reason, right_alignment.reason)))
    polarity_families = {"OBLIGATION", "RIGHT", "PROHIBITION"}
    same_operation_family = left.family == right.family or (
        left.family in polarity_families and right.family in polarity_families
    )
    if left_alignment.key != right_alignment.key or not same_operation_family:
        return result("NOT_COMPARABLE", "different_semantic_key")

    context = context_assessment(left, right)
    if context.state == "DISJOINT":
        if "interval_disjoint" in context.reasons:
            return result("CONFLICT_CANDIDATE", "incompatible_intervals_same_operation")
        return result("NOT_COMPARABLE", ";".join(context.reasons))
    if context.state == "UNKNOWN":
        return result("NEEDS_REVIEW_UNPARSED", ";".join(context.reasons))
    if context.state == "PARTIAL" and not any(
        reason == "interval_overlap" for reason in context.reasons
    ):
        return result("NEEDS_REVIEW_UNPARSED", ";".join(context.reasons))

    required = {
        "actor", "action", "modality_negation", "object_scope", "beneficiary",
        "condition", "exception", "temporal_trigger", "deadline",
    }
    if left.family == "PARAMETER" and left.get("parameter") is not None:
        required.difference_update({"actor", "action", "modality_negation", "beneficiary"})
        required.add("parameter")
    elif left.family == "DEFINITION":
        required = {"parameter", "definition", "object_scope", "condition", "exception", "temporal_trigger"}
    if left.family == "REMEDY":
        required.add("qualifier")
    quantitative = left.family in {"REMEDY", "PARAMETER"} or any(
        frame.get("action") and frame.get("action").value in {"PAY", "COMPENSATE", "PENALTY"}
        or frame.get("amount") and frame.get("amount").value is not None
        for frame in (left, right)
    )
    if quantitative:
        required.update({"amount", "unit", "currency", "base", "period"})
    for name in sorted(required):
        if any(frame.get(name) is None for frame in (left, right)):
            return result("NEEDS_REVIEW_UNPARSED", f"unassessed_slot:{name}")
        if name in {"currency", "base", "period"} and all(
            frame.get(name).state == "UNKNOWN"
            and frame.get(name).reason == "not_assessed"
            for frame in (left, right)
        ):
            # These quantity context fields are optional when neither source
            # states one.  A difference is still retained if either side is
            # grounded; only an unsupported one-sided value needs review.
            continue

    if quantitative:
        for name in ("amount", "unit"):
            if any(frame.get(name) is None or frame.get(name).state != "GROUNDED"
                   for frame in (left, right)):
                return result("NEEDS_REVIEW_UNPARSED", f"missing_quantity:{name}")
        if any(not isinstance(frame.get("amount").value, Decimal) for frame in (left, right)):
            return result("NEEDS_REVIEW_UNPARSED", "untyped_quantity:amount")

    quantity_context_differences = []
    quantity_context_unknown = []
    for name in ("currency", "unit", "base", "period"):
        a, b = left.get(name), right.get(name)
        if a is not None and b is not None and (a.state, a.value) != (b.state, b.value):
            quantity_context_differences.append(name)
        if a is not None and b is not None and all(
            slot.state == "UNKNOWN" and slot.reason == "not_assessed"
            for slot in (a, b)
        ):
            quantity_context_unknown.append(name)
    if quantity_context_differences:
        return result(
            "NOT_COMPARABLE",
            "quantity_context_differs:" + ",".join(quantity_context_differences),
        )

    names = required | {
        name for name, slot in (*left.slots, *right.slots)
        if slot.state in {"GROUNDED", "ABSENT"}
    }
    optional_absent = {
        "beneficiary",
        "condition",
        "exception",
        "temporal_trigger",
        "deadline",
        "deadline_unit",
        "currency",
        "base",
        "period",
    }
    for name in optional_absent:
        if name in names and all(
            frame.get(name) is not None and frame.get(name).state == "ABSENT"
            for frame in (left, right)
        ):
            names.remove(name)
    for name in {"currency", "base", "period"}:
        if name in names and all(
            frame.get(name) is not None
            and frame.get(name).state == "UNKNOWN"
            and frame.get(name).reason == "not_assessed"
            for frame in (left, right)
        ):
            # Quantity context can be unavailable on both sides without
            # proving that a condition or scope is absent. Keep this narrow
            # exception so unknown semantic constraints remain review-only.
            names.remove(name)
    key_fields = {"qualifier"} if left.family == "REMEDY" else set()
    if left.family != "DEFINITION" and not (
        left.family == "PARAMETER" and left.get("parameter") is not None
    ):
        key_fields.add("action")
    differing = []
    for name in sorted(names):
        a, b = left.get(name), right.get(name)
        if (a is None or b is None or a.state in {"UNKNOWN", "UNSUPPORTED"}
                or b.state in {"UNKNOWN", "UNSUPPORTED"}):
            return result("NEEDS_REVIEW_UNPARSED", f"uncertain_slot:{name}")
        if name in key_fields and a.state == b.state == "GROUNDED":
            continue
        if (a.state, a.value) != (b.state, b.value):
            differing.append(name)

    left_modality = left.get("modality_negation")
    right_modality = right.get("modality_negation")
    if left_modality is None or right_modality is None:
        if left.family == "PARAMETER" and left.get("parameter") is not None:
            if differing:
                return result("COMPARABLE_DIFFERENCE", "slots_differ:" + ",".join(differing))
            if quantity_context_unknown:
                return result("NEEDS_REVIEW_UNPARSED", "uncertain_quantity_context:" + ",".join(quantity_context_unknown))
            return result("DUPLICATE", "all_represented_slots_grounded_and_equal")
        return result("NEEDS_REVIEW_UNPARSED", "unassessed_slot:modality_negation")
    if left_modality.state != "GROUNDED" or right_modality.state != "GROUNDED":
        if left.family == "PARAMETER" and left.get("parameter") is not None:
            if differing:
                return result("COMPARABLE_DIFFERENCE", "slots_differ:" + ",".join(differing))
            if quantity_context_unknown:
                return result("NEEDS_REVIEW_UNPARSED", "uncertain_quantity_context:" + ",".join(quantity_context_unknown))
            return result("DUPLICATE", "all_represented_slots_grounded_and_equal")
        return result("NEEDS_REVIEW_UNPARSED", "uncertain_slot:modality_negation")
    polarities = {left_modality.value, right_modality.value}
    if polarities == {"REQUIRED", "PROHIBITED"}:
        return result("CONFLICT_CANDIDATE", "opposite_grounded_polarity_same_context")
    if left_modality.value != right_modality.value:
        return result("COMPARABLE_DIFFERENCE", "polarity_differs")
    if differing:
        return result("COMPARABLE_DIFFERENCE", "slots_differ:" + ",".join(differing))
    if quantity_context_unknown:
        return result("NEEDS_REVIEW_UNPARSED", "uncertain_quantity_context:" + ",".join(quantity_context_unknown))
    return result("DUPLICATE", "all_represented_slots_grounded_and_equal")
