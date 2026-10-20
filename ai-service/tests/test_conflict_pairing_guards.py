from __future__ import annotations

from decimal import Decimal

from app.contracts.clause_frames import ClauseFrame, Evidence, Slot
from app.contracts.models import (
    Citation,
    ComparisonScope,
    Disposition,
    Fact,
    FindingType,
    ReviewState,
)
from app.pipeline.clause_keys import build_candidates
from app.pipeline.compare import compare_facts
from app.pipeline.frame_comparison import compare_frames
from app.pipeline.frame_extraction import extract_frames
from app.reasoning.relations import _explicit_amend_reference


def _fact(identifier, value, *, source_file, role, text, tax_basis=None):
    return Fact(
        fact_id=identifier,
        raw_value=value,
        normalized_value=value,
        item_key="contract_value",
        source_role=role,
        currency="VND",
        unit="VND",
        tax_basis=tax_basis,
        citation=Citation(
            node_id=f"node-{identifier}", page_revision_id="page-1", source_file_id=source_file,
            text_span=text,
        ),
    )


def _frame(identifier, document, snapshot, *, trigger=None, amount=Decimal("10")):
    evidence = Evidence(document, snapshot, identifier, "Bên B phải thanh toán 10 VND")
    values = {
        "actor": "B", "action": "PAY", "modality_negation": "REQUIRED",
        "object_scope": "invoice", "amount": amount, "currency": "VND", "unit": "money",
        "temporal_trigger": trigger,
    }
    slots = tuple(
        (name, Slot(value, "GROUNDED" if value is not None else "UNKNOWN", (evidence,)))
        for name, value in values.items()
    )
    slots += tuple(
        (name, Slot(None, "ABSENT", (evidence,)))
        for name in ("beneficiary", "condition", "exception", "deadline", "base", "period")
    )
    return ClauseFrame(identifier, "OBLIGATION", "SALES", document, snapshot, (evidence,), slots, "dossier")


def test_same_item_without_relation_keeps_two_source_candidate_for_review():
    left = _fact("body", "100", source_file="body", role="body", text="Điều 4 giá hợp đồng")
    right = _fact("annex", "120", source_file="annex", role="annex", text="Phụ lục giá")

    candidates, issues = compare_facts([left, right])

    assert len(candidates) == 1
    assert candidates[0].finding_type == FindingType.COMPARABLE_DIFFERENCE
    assert candidates[0].review_state == ReviewState.NEEDS_REVIEW
    assert candidates[0].evidence_left and candidates[0].evidence_right
    assert "relation_unconfirmed" in candidates[0].reason
    assert any(issue.missing == "BODY_ANNEX_RELATION" for issue in issues)


def test_tax_basis_difference_is_not_a_value_conflict():
    left = _fact("body", "100", source_file="body", role="body", text="chưa VAT", tax_basis="ex_vat")
    right = _fact("annex", "110", source_file="annex", role="annex", text="đã gồm VAT", tax_basis="incl_vat")
    candidates, _ = compare_facts([left, right], relation_pairs={("node-body", "node-annex")})

    assert len(candidates) == 1
    assert candidates[0].disposition == Disposition.NOT_COMPARABLE
    assert candidates[0].scope == ComparisonScope.CONTRACT_ANNEX


def test_generic_become_word_does_not_turn_pair_into_amendment():
    left = _fact("body", "100", source_file="body", role="body", text="Điều 4 trở thành giá hợp đồng")
    right = _fact("annex", "120", source_file="annex", role="annex", text="Phụ lục giá")
    candidates, _ = compare_facts([left, right], relation_pairs={("node-body", "node-annex")})

    assert candidates[0].disposition == Disposition.COMPARABLE_DIFFERENCE


def test_same_key_does_not_pair_multiple_frames_inside_one_document():
    first = _frame("first", "body", "snapshot-body")
    second = _frame("second", "body", "snapshot-body", amount=Decimal("20"))

    assert build_candidates((first, second)) == ()


def test_same_key_across_body_and_annex_keeps_pair_and_source_lineage():
    body = _frame("body", "body", "snapshot-body")
    annex = _frame("annex", "annex", "snapshot-annex", amount=Decimal("20"))

    candidates = build_candidates((body, annex))

    assert len(candidates) == 1
    assert candidates[0].sources == ("SAME_KEY",)


def test_payment_trigger_is_extracted_and_different_triggers_cannot_duplicate():
    source = Evidence("body", "snapshot-body", "node-1", "Bên B phải thanh toán trong 07 ngày kể từ ngày ký")
    frames = extract_frames(source, profile="SALES", dossier_id="dossier")

    assert frames
    assert frames[0].get("temporal_trigger").value == "SIGNING"
    left = _frame("left", "body", "snapshot-body", trigger="SIGNING")
    right = _frame("right", "annex", "snapshot-annex", trigger="DOCUMENTS_COMPLETE", amount=Decimal("20"))
    assert compare_frames(left, right).disposition == "NOT_COMPARABLE"


def test_amends_relation_requires_an_explicit_marker_and_target_number():
    assert _explicit_amend_reference("Các bên đồng ý sửa đổi Điều 5", "5")
    assert not _explicit_amend_reference("Điều 1 đến Điều 18 là toàn bộ thỏa thuận", "5")
    assert not _explicit_amend_reference("Điều 5 trở thành căn cứ", "5")


def test_amendment_marker_in_clause_subject_is_grounded():
    left = _fact(
        "body-penalty",
        "0.2%",
        source_file="body",
        role="body",
        text="Điều 5. Phạt chậm tiến độ chung",
    )
    right = _fact(
        "annex-penalty",
        "0.1%",
        source_file="annex",
        role="annex",
        text="Phụ lục 1 Điều 5. Phạt chậm 0.1%",
    )
    right.subject = "Phụ lục 1 — Sửa Điều 5"

    candidates, _ = compare_facts(
        [left, right], relation_pairs={("node-body-penalty", "node-annex-penalty")}
    )

    assert len(candidates) == 1
    assert candidates[0].disposition == Disposition.CANDIDATE_AMENDMENT


def test_pairing_cap_keeps_a_review_issue_instead_of_silently_truncating():
    body = _fact("body", "100", source_file="body", role="body", text="Điều 4 giá hợp đồng")
    annexes = [
        _fact(f"annex-{index}", str(100 + index), source_file="annex", role="annex", text="Phụ lục giá")
        for index in range(501)
    ]
    for fact in annexes:
        fact.validity = "PL1"

    candidates, issues = compare_facts([body, *annexes])

    assert len(candidates) == 500
    assert any(issue.missing == "PAIRING_COVERAGE_CAPPED" for issue in issues)
