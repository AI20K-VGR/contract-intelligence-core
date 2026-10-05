from decimal import Decimal

from app.contracts.clause_frames import Evidence
from app.pipeline.clause_keys import build_candidates
from app.pipeline.frame_comparison import compare_frames
from app.pipeline.frame_extraction import extract_frames


def test_percentage_and_deadline_keep_independent_units():
    frames = extract_frames(
        Evidence("doc-1", "snap-1", "node-1", "Bên B phải thanh toán 30% trong 07 ngày làm việc"),
        profile="SALES",
        dossier_id="dos-1",
    )

    frame = frames[0]
    assert frame.get("amount") is not None
    assert frame.get("amount").value == Decimal("30")
    assert frame.get("unit").value == "percent"
    assert frame.get("deadline").value == "07"
    assert frame.get("deadline_unit").value == "business-day"


def test_money_without_currency_remains_unknown():
    frames = extract_frames(
        Evidence("doc-1", "snap-1", "node-1", "Bên B phải thanh toán 1.000.000 trong 5 ngày"),
        profile="SALES",
        dossier_id="dos-1",
    )

    frame = frames[0]
    assert frame.get("amount").value is None
    assert frame.get("amount").state == "UNKNOWN"
    assert frame.get("currency").state == "UNKNOWN"


def test_scope_is_grounded_only_when_explicit_in_source():
    grounded = extract_frames(
        Evidence("doc-1", "snap-1", "node-1", "Bên B phải thanh toán phí vận chuyển"),
        profile="SALES",
        dossier_id="dos-1",
    )[0]
    assert grounded.get("object_scope").state == "GROUNDED"
    assert grounded.get("object_scope").value == "phí vận chuyển"

    ambiguous = extract_frames(
        Evidence("doc-1", "snap-1", "node-2", "Bên B phải thanh toán theo thỏa thuận"),
        profile="SALES",
        dossier_id="dos-1",
    )[0]
    assert ambiguous.get("object_scope").state == "UNKNOWN"


def test_grouped_contract_totals_become_comparable_parameter_frames():
    body = extract_frames(
        Evidence(
            "contract",
            "snap-body",
            "line:3",
            "4.1. Tổng giá trị hợp đồng tạm tính là 1.286.400.000 đồng.",
        ),
        profile="SALES",
        dossier_id="dos-1",
    )[0]
    annex = extract_frames(
        Evidence(
            "annex",
            "snap-annex",
            "line:16",
            "| Tổng cộng |  | 4.149.360.000 |",
        ),
        profile="SALES",
        dossier_id="dos-1",
    )[0]

    assert body.family == "PARAMETER"
    assert body.get("parameter").value == "total_price"
    assert body.get("amount").value == Decimal("1286400000")
    assert body.get("currency").value == "VND"
    assert annex.family == "PARAMETER"
    assert annex.get("parameter").value == "total_price"
    assert annex.get("amount").value == Decimal("4149360000")
    assert annex.get("unit").value == "money"
    assert annex.get("currency").state == "UNKNOWN"

    candidates = build_candidates((body, annex))
    assert len(candidates) == 1
    pair = compare_frames(body, annex)
    assert pair.disposition == "NEEDS_REVIEW_UNPARSED"
    assert pair.left_evidence and pair.right_evidence


def test_total_with_bang_chu_parenthetical_stays_a_parameter():
    source = Evidence(
        "doc-body",
        "snapshot-body",
        "line:body",
        (
            "4.1. Tổng giá trị hợp đồng tạm tính là 1.286.400.000 đồng "
            "(Bằng chữ: Một tỷ hai trăm tám mươi sáu triệu bốn trăm nghìn đồng), "
            "đã bao gồm các chi phí theo phạm vi công việc và chưa bao gồm phát sinh ngoài phạm vi."
        ),
    )

    frames = extract_frames(source, profile="SALES", dossier_id="dossier-1")

    assert len(frames) == 1
    assert frames[0].family == "PARAMETER"
    assert frames[0].get("parameter").value == "total_price"


def test_grouped_money_is_not_truncated_into_object_scope():
    source = Evidence(
        "doc-body",
        "snapshot-body",
        "line:payment",
        "Bên A phải thanh toán 30.000.000 đồng trong 30 ngày làm việc.",
    )

    frame = extract_frames(source, profile="SALES", dossier_id="dossier-1")[0]

    assert frame.get("amount").value == Decimal("30000000")
    assert frame.get("unit").value == "money"
    assert frame.get("object_scope").state == "UNKNOWN"
