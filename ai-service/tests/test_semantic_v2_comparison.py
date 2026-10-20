from __future__ import annotations

from dataclasses import replace

from test_semantic_v2_alignment import make_frame

from app.contracts.clause_frames import Slot
from app.pipeline.frame_comparison import compare_frames


def test_required_and_prohibited_same_context_are_conflict_candidates():
    pair = compare_frames(
        make_frame("left", modality="REQUIRED"),
        make_frame("right", document="annex", modality="PROHIBITED"),
    )

    assert pair.disposition == "CONFLICT_CANDIDATE"
    assert pair.review_state == "NEEDS_REVIEW"
    assert pair.left_evidence and pair.right_evidence


def test_same_event_amount_delta_is_comparable_difference():
    pair = compare_frames(
        make_frame("left", amount="30"),
        make_frame("right", document="annex", amount="40"),
    )

    assert pair.disposition == "COMPARABLE_DIFFERENCE"
    assert "amount" in pair.reason


def test_different_payment_events_are_not_conflicts():
    pair = compare_frames(
        make_frame("left", trigger="SIGNING"),
        make_frame("right", document="annex", trigger="DELIVERY"),
    )

    assert pair.disposition == "NOT_COMPARABLE"
    assert "trigger" in pair.reason


def test_required_and_permitted_are_not_automatic_conflicts():
    pair = compare_frames(
        make_frame("left", modality="REQUIRED"),
        make_frame("right", document="annex", modality="PERMITTED"),
    )

    assert pair.disposition != "CONFLICT_CANDIDATE"
    assert pair.review_state == "NEEDS_REVIEW"


def test_unknown_scope_stays_review_only():
    pair = compare_frames(
        make_frame("left", scope=None),
        make_frame("right", document="annex"),
    )

    assert pair.disposition == "NEEDS_REVIEW_UNPARSED"


def test_different_scope_does_not_become_conflict():
    pair = compare_frames(
        make_frame("left", scope="invoice"),
        make_frame("right", document="annex", scope="delivery"),
    )

    assert pair.disposition == "SCOPE_DIFFERS"


def test_deadline_delta_is_retained_as_a_difference():
    pair = compare_frames(
        make_frame("left", deadline="7"),
        make_frame("right", document="annex", deadline="10"),
    )

    assert pair.disposition == "COMPARABLE_DIFFERENCE"
    assert "deadline" in pair.reason


def test_overlapping_numeric_conditions_are_a_bounded_difference():
    pair = compare_frames(
        make_frame("left", condition="days <= 7"),
        make_frame("right", document="annex", condition="days <= 10"),
    )

    assert pair.disposition == "COMPARABLE_DIFFERENCE"
    assert "condition" in pair.reason


def test_disjoint_numeric_conditions_are_bounded_conflict_candidates():
    pair = compare_frames(
        make_frame("left", condition="days >= 10"),
        make_frame("right", document="annex", condition="days <= 7"),
    )

    assert pair.disposition == "CONFLICT_CANDIDATE"
    assert "interval" in pair.reason


def test_equal_grounded_pair_remains_duplicate():
    pair = compare_frames(make_frame("left"), make_frame("right", document="annex"))

    assert pair.disposition == "DUPLICATE"


def test_unknown_condition_does_not_prove_duplicate():
    left = make_frame("left", condition=None)
    right = make_frame("right", document="annex")
    slots = dict(right.slots)
    slots["condition"] = Slot(None, "UNKNOWN", right.evidence, "unparsed_condition")
    right = replace(right, slots=tuple(slots.items()))

    assert compare_frames(left, right).disposition != "DUPLICATE"
