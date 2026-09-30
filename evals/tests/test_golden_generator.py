from __future__ import annotations

import pytest

from evals.golden.spec import (
    ExpectedState,
    MutationSpec,
    expected_state_for,
)


@pytest.mark.parametrize(
    ("question_kind", "mutations", "expected"),
    [
        ("lookup", (), ExpectedState.ANSWERED),
        ("clause_lookup", (MutationSpec("non_conflicting_term"),), ExpectedState.ANSWERED),
        ("lookup", (MutationSpec("body_annex_conflict"),), ExpectedState.NEEDS_REVIEW),
        (
            "lookup",
            (MutationSpec("duplicate_name_different_tax_id"),),
            ExpectedState.NEEDS_REVIEW,
        ),
        ("lookup", (MutationSpec("overlapping_amendment"),), ExpectedState.NEEDS_REVIEW),
        ("lookup", (MutationSpec("missing_annex"),), ExpectedState.INSUFFICIENT_EVIDENCE),
        ("lookup", (MutationSpec("absent_information"),), ExpectedState.INSUFFICIENT_EVIDENCE),
        ("broad", (), ExpectedState.INSUFFICIENT_EVIDENCE),
        ("comparison", (MutationSpec("incomparable_quantities"),), ExpectedState.NOT_COMPARABLE),
        (
            "comparison",
            (MutationSpec("body_annex_conflict"), MutationSpec("missing_annex")),
            ExpectedState.NEEDS_REVIEW,
        ),
    ],
)
def test_expected_state_rules(
    question_kind: str,
    mutations: tuple[MutationSpec, ...],
    expected: ExpectedState,
) -> None:
    assert expected_state_for(question_kind, mutations) is expected


@pytest.mark.parametrize(
    ("question_kind", "mutations"),
    [
        ("unknown", ()),
        ("lookup", (MutationSpec("invented_mutation"),)),
    ],
)
def test_expected_state_rules_reject_unknown_inputs(
    question_kind: str,
    mutations: tuple[MutationSpec, ...],
) -> None:
    with pytest.raises(ValueError):
        expected_state_for(question_kind, mutations)


def test_catalog_states_come_from_rules() -> None:
    from evals.golden.catalog import CONTRACTS

    assert len(CONTRACTS) == 8
    assert {contract.contract_id for contract in CONTRACTS} == {
        f"G{number:02d}" for number in range(1, 9)
    }
    questions = [question for contract in CONTRACTS for question in contract.questions]
    assert len(questions) >= 84
    states = [question.expected_state for question in questions]
    assert states.count(ExpectedState.ANSWERED) >= 35
    assert states.count(ExpectedState.NEEDS_REVIEW) >= 15
    assert states.count(ExpectedState.INSUFFICIENT_EVIDENCE) >= 17
    assert states.count(ExpectedState.NOT_COMPARABLE) >= 4
    assert sum(question.kind == "comparison" for question in questions) >= 15
    assert sum(state is not ExpectedState.ANSWERED for state in states) / len(states) >= 0.2
    for question in questions:
        assert question.expected_state == expected_state_for(
            question.kind, question.mutations
        )


def test_contract_question_forms_are_distinct_after_term_normalization() -> None:
    from evals.golden.catalog import CONTRACTS

    signatures_by_contract: dict[str, set[str]] = {}
    for contract in CONTRACTS:
        signatures = set()
        terms = sorted(contract.features, key=len, reverse=True)
        for question in contract.questions:
            signature = question.text
            for term in terms:
                signature = signature.replace(term, "{term}")
            signatures.add(signature)
        signatures_by_contract[contract.contract_id] = signatures

    contract_ids = list(signatures_by_contract)
    for index, contract_id in enumerate(contract_ids):
        for other_id in contract_ids[index + 1 :]:
            assert signatures_by_contract[contract_id].isdisjoint(
                signatures_by_contract[other_id]
            ), f"{contract_id} and {other_id} reuse question forms"
