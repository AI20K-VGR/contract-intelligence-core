"""Human-authored rules for synthetic golden labels.

These rules define expected evidence states independently of reasoner output.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum


class ExpectedState(StrEnum):
    ANSWERED = "ANSWERED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NOT_COMPARABLE = "NOT_COMPARABLE"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class MutationSpec:
    """A controlled synthetic condition that can affect evidence sufficiency."""

    kind: str


QUESTION_CATEGORIES = frozenset({"answerable", "not_in_document", "permission"})
_QUESTION_KINDS = frozenset({"lookup", "clause_lookup", "broad", "comparison", "permission"})
_REVIEW_MUTATIONS = frozenset(
    {
        "body_annex_conflict",
        "duplicate_name_different_tax_id",
        "overlapping_amendment",
        "conflicting_value",
        "conflicting_date",
        "conflicting_percentage",
        "effective_date_change",
    }
)
_INSUFFICIENT_MUTATIONS = frozenset(
    {"missing_annex", "absent_information", "unreadable_evidence"}
)
_NOT_COMPARABLE_MUTATIONS = frozenset({"incomparable_quantities"})
_KNOWN_MUTATIONS = (
    _REVIEW_MUTATIONS
    | _INSUFFICIENT_MUTATIONS
    | _NOT_COMPARABLE_MUTATIONS
    | {"non_conflicting_term"}
)


def expected_state_for(
    question_kind: str,
    mutations: Iterable[MutationSpec] = (),
) -> ExpectedState:
    """Derive a question state from its declared kind and controlled mutations.

    Conflicting evidence takes precedence over other defects. In its absence,
    incomparable quantities remain unscorable; missing evidence and broad
    questions fail closed as insufficient.
    """

    if question_kind not in _QUESTION_KINDS:
        raise ValueError(f"unknown question kind: {question_kind!r}")
    if question_kind == "permission":
        return ExpectedState.BLOCKED

    mutation_list = tuple(mutations)
    if any(not isinstance(mutation, MutationSpec) for mutation in mutation_list):
        raise TypeError("mutations must contain MutationSpec values")
    unknown = {mutation.kind for mutation in mutation_list} - _KNOWN_MUTATIONS
    if unknown:
        raise ValueError(f"unknown mutation kind(s): {', '.join(sorted(unknown))}")

    kinds = {mutation.kind for mutation in mutation_list}
    if kinds & _REVIEW_MUTATIONS:
        return ExpectedState.NEEDS_REVIEW
    if kinds & _NOT_COMPARABLE_MUTATIONS:
        return ExpectedState.NOT_COMPARABLE
    if question_kind == "broad" or kinds & _INSUFFICIENT_MUTATIONS:
        return ExpectedState.INSUFFICIENT_EVIDENCE
    return ExpectedState.ANSWERED
