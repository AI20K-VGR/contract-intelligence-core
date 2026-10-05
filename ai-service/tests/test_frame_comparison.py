from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from app.contracts.clause_frames import ClauseFrame, Evidence, Slot
from app.pipeline.frame_comparison import compare_frames


def make(identifier, **changes):
    ev = Evidence("doc", "s1", identifier, "Bên B phải thanh toán 5 VND")
    values = {"actor": "B", "action": "PAY", "modality_negation": "REQUIRED",
              "object_scope": "item1", "amount": Decimal("5"), "currency": "VND",
              "unit": "money"}
    values.update(changes)
    slots = tuple((name, Slot(value, "GROUNDED" if value is not None else "UNKNOWN",
                              (ev,))) for name, value in values.items())
    slots += tuple((name, Slot(None, "ABSENT", (ev,))) for name in (
        "beneficiary", "condition", "exception", "temporal_trigger", "deadline",
        "base", "period") if name not in values)
    return ClauseFrame(identifier, "PARAMETER", "SALES", "doc", "s1", (ev,), slots, "dossier")


def test_missing_values_never_duplicate():
    pair = compare_frames(make("a", amount=None), make("b", amount=None))
    assert pair.disposition == "NEEDS_REVIEW_UNPARSED"
    assert pair.left_evidence and pair.right_evidence


def test_scope_is_compared_before_amount():
    pair = compare_frames(make("a", amount=None), make("b", object_scope="item2", amount=None))
    assert pair.disposition == "SCOPE_DIFFERS"


def test_unknown_scope_never_duplicate():
    assert compare_frames(make("a", object_scope=None), make("b")).disposition != "DUPLICATE"


@pytest.mark.parametrize("field,value", [("unit", "business-day"), ("currency", "USD"),
                                         ("base", "invoice"), ("period", "month"),
                                         ("temporal_trigger", "acceptance")])
def test_quantity_context_change_never_duplicate(field, value):
    left = make("a", **{field: "day"})
    right = make("b", **{field: value})
    assert compare_frames(left, right).disposition != "DUPLICATE"


def test_exact_grounded_pair_can_duplicate_without_mutation():
    left, right = make("a"), make("b")
    before = left
    pair = compare_frames(left, right)
    assert pair.disposition == "DUPLICATE"
    assert left == before
    assert pair.review_state == "NEEDS_REVIEW"


def test_negation_change_is_visible():
    assert compare_frames(make("a"), make("b", modality_negation="PROHIBITED")).disposition != "DUPLICATE"


def test_different_dossiers_never_compare():
    right = replace(make("b"), dossier_id="other")
    with pytest.raises(ValueError, match="dossier"):
        compare_frames(make("a"), right)


def test_omitted_context_on_both_sides_is_not_proof_of_absence():
    left = make("a")
    left = replace(left, slots=tuple((name, value) for name, value in left.slots
                                    if name != "condition"))
    right = replace(left, frame_id="b")
    assert compare_frames(left, right).disposition == "NEEDS_REVIEW_UNPARSED"


def test_money_without_currency_never_duplicate():
    assert compare_frames(make("a", currency=None), make("b", currency=None)).disposition != "DUPLICATE"

def test_cross_profile_pair_never_duplicate():
    assert compare_frames(make("a"), replace(make("b"), profile="LEASE")).disposition == "NOT_COMPARABLE"

def test_untyped_amount_text_cannot_be_certified_duplicate():
    assert compare_frames(make("a", amount="5% total"), make("b", amount="5% total")).disposition == "NEEDS_REVIEW_UNPARSED"

def test_irrelevant_unknown_family_slots_do_not_poison_complete_comparison():
    from app.contracts.clause_frames import SLOT_NAMES
    left = replace(make("a"), family="OBLIGATION")
    missing = SLOT_NAMES - {name for name, _ in left.slots}
    left = replace(left, slots=(*left.slots, *((name, Slot(None, "UNKNOWN", left.evidence, "not_applicable")) for name in sorted(missing))))
    right = replace(left, frame_id="b")
    assert compare_frames(left, right).disposition == "DUPLICATE"


def test_explicit_parameter_does_not_need_an_invented_actor_or_action():
    left = make("a")
    slots = dict(left.slots)
    for name in ("actor", "action", "modality_negation"):
        slots[name] = Slot(None, "UNKNOWN", left.evidence, "not_applicable")
    slots["parameter"] = Slot("unit_price", "GROUNDED", left.evidence)
    left = replace(left, slots=tuple(slots.items()))
    assert compare_frames(left, replace(left, frame_id="b")).disposition == "DUPLICATE"

def test_approved_alias_compares_canonical_action_without_mutating_raw():
    from app.pipeline.tenant_aliases import ApprovedAlias, ApprovedAliasSnapshot
    aliases = ApprovedAliasSnapshot("tenant", 1, (ApprovedAlias("pay invoice", "PAY", "action", "p"),))
    left = make("a", action="pay invoice")
    pair = compare_frames(left, make("b"), aliases=aliases, tenant_id="tenant", alias_version=1)
    assert pair.disposition == "DUPLICATE"
    assert left.get("action").value == "pay invoice"

def test_parameter_key_does_not_hide_different_explicit_action_context():
    left = make("a")
    left = replace(left, slots=(*left.slots, ("parameter", Slot("unit_price", "GROUNDED", left.evidence))))
    right = make("b", action="DELIVER")
    right = replace(right, slots=(*right.slots, ("parameter", Slot("unit_price", "GROUNDED", right.evidence))))
    assert compare_frames(left, right).disposition == "COMPARABLE_DIFFERENCE"
