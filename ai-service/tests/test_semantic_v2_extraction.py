from decimal import Decimal

import pytest

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


def _only_frame(text, source_ref="node-1"):
    frames = extract_frames(
        Evidence("doc-1", "snap-1", source_ref, text), profile="SALES", dossier_id="dos-1"
    )
    assert len(frames) == 1
    return frames[0]


def test_trong_vong_deadline_is_grounded():
    frame = _only_frame(
        "5.2. Bên A thanh toán mỗi khoản trong vòng 07 ngày kể từ ngày nhận hóa đơn."
    )
    assert (frame.get("deadline").value, frame.get("deadline_unit").value) == ("07", "day")


def test_declarative_party_action_is_a_required_obligation():
    # Vietnamese drafting states duties without "phải"; UNKNOWN modality sent every such
    # pair (incl. a planted 07 -> 10 day amendment) to NEEDS_REVIEW_BACKOFF.
    modality = _only_frame("Bên A thanh toán mỗi khoản trong vòng 07 ngày.").get(
        "modality_negation"
    )
    assert (modality.value, modality.state, modality.reason) == (
        "REQUIRED",
        "GROUNDED",
        "declarative_obligation",
    )


def test_hedged_declaratives_keep_modality_unknown():
    for text in (
        "Bên A có quyền thanh toán sớm.",
        "Bên A chưa thanh toán khoản đợt 2.",
        "Bên A có thể thanh toán bằng tiền mặt.",
    ):
        assert _only_frame(text).get("modality_negation").state == "UNKNOWN", text


def test_declarative_amendment_pair_compares_on_deadline():
    left = _only_frame(
        "5.2. Bên A thanh toán mỗi khoản trong vòng 07 ngày kể từ ngày nhận được hóa đơn."
    )
    right = _only_frame(
        "Điều chỉnh khoản 2 Điều 5 của Hợp đồng như sau: Bên A thanh toán mỗi khoản trong vòng 10 ngày"
        " kể từ ngày nhận được hóa đơn hợp lệ của Bên B.",
        "node-2",
    )
    assert left.get("temporal_trigger").value == right.get("temporal_trigger").value == "INVOICE"
    pair = compare_frames(left, right)
    assert pair.disposition in {"COMPARABLE_DIFFERENCE", "CONFLICT_CANDIDATE"}, pair.reason
    assert "deadline" in pair.reason


def test_payment_timing_clause_states_no_amount():
    frame = _only_frame(
        "5.2. Bên A thanh toán mỗi khoản trong vòng 07 ngày kể từ ngày nhận hóa đơn theo khoản 2 Điều 5."
    )
    assert (frame.get("amount").state, frame.get("unit").state) == ("ABSENT", "ABSENT")


def test_unparsed_number_keeps_amount_unknown():
    # A leftover number may be an amount the extractor could not type; never claim ABSENT.
    frame = _only_frame("Bên A thanh toán đợt 2 là 500.000.000 trong vòng 07 ngày.")
    assert frame.get("amount").state == "UNKNOWN"


def test_two_unparsed_payments_are_not_duplicates():
    left = _only_frame("Bên A thanh toán đợt 1 là 500.000.000 trong vòng 07 ngày.")
    right = _only_frame("Bên A thanh toán đợt 2 là 300.000.000 trong vòng 07 ngày.", "node-2")
    assert compare_frames(left, right).disposition != "DUPLICATE"


def test_copula_is_not_an_object_scope():
    # "giao hàng là trong vòng 30 ngày": the word after the verb is the copula, not the goods.
    frame = _only_frame("3.1. Thời gian giao hàng là trong vòng 30 ngày kể từ ngày ký Hợp đồng.")
    assert frame.get("object_scope").state != "GROUNDED", frame.get("object_scope")


@pytest.mark.parametrize(
    ("text", "value", "unit"),
    [
        ("Bên B phải khắc phục sự cố trong vòng 04 giờ kể từ khi nhận thông báo.", "04", "hour"),
        ("Bên B giao hàng trong vòng 2 tuần kể từ ngày ký.", "2", "week"),
        ("Bên B bảo hành trong 1 năm kể từ ngày nghiệm thu.", "1", "year"),
    ],
)
def test_deadline_units_beyond_days(text, value, unit):
    frame = _only_frame(text)
    assert (frame.get("deadline").value, frame.get("deadline_unit").value) == (value, unit)


def test_same_deadline_written_with_leading_zero_is_not_a_difference():
    left = _only_frame("Bên A thanh toán mỗi đợt trong vòng 05 ngày kể từ ngày nhận được hóa đơn.")
    right = _only_frame(
        "Bên A thanh toán mỗi đợt trong vòng 5 ngày kể từ ngày nhận được hóa đơn.", "node-2"
    )
    assert compare_frames(left, right).disposition not in {
        "COMPARABLE_DIFFERENCE",
        "CONFLICT_CANDIDATE",
    }


def test_both_parties_accepting_is_a_grounded_obligation():
    frame = _only_frame(
        "Hai bên nghiệm thu kết quả bảo trì trong vòng 05 ngày làm việc kể từ ngày kết thúc tháng."
    )
    assert (frame.get("actor").value, frame.get("action").value) == ("BOTH", "ACCEPT")
    assert frame.get("temporal_trigger").state == "GROUNDED"


def test_acceptance_deadline_change_by_substitution_compares():
    left = _only_frame(
        "6.1. Hai bên nghiệm thu kết quả bảo trì hằng tháng trong vòng 05 ngày làm việc kể từ ngày kết thúc tháng."
    )
    right = _only_frame(
        "Thay thế khoản 1 Điều 6 của Hợp đồng bằng nội dung sau: Hai bên nghiệm thu kết quả bảo trì hằng tháng\n"
        "trong vòng 03 ngày làm việc kể từ ngày kết thúc tháng.",
        "node-2",
    )
    pair = compare_frames(left, right)
    assert pair.disposition == "COMPARABLE_DIFFERENCE" and "deadline" in pair.reason, pair.reason


def test_deadline_stated_by_reference_stays_unknown_not_absent():
    frame = _only_frame("Bên A thanh toán đợt 2 theo thời hạn quy định tại khoản 2 Điều 5.")
    deadline = frame.get("deadline")
    assert (deadline.state, deadline.reason) == ("UNKNOWN", "deferred_by_reference")


def test_clause_without_any_deadline_is_still_absent():
    assert _only_frame("Bên B giao hàng tại kho của Bên A.").get("deadline").state == "ABSENT"


# PR #125 review round 2 (Chuongpham2004): an amount stated by clause reference lives in the
# referenced clause; ABSENT would forbid context enrichment from filling it.
def test_amount_stated_by_reference_stays_unknown_not_absent():
    frame = _only_frame("Bên A thanh toán tiền hàng theo khoản 2 Điều 5.")
    for name in ("amount", "unit"):
        slot = frame.get(name)
        assert (slot.state, slot.reason) == ("UNKNOWN", "deferred_by_reference"), name


# PR #125 review round 2: a conditional lead-in is the trigger, not a duty.
def test_conditional_clause_is_not_a_declarative_obligation():
    frames = extract_frames(
        Evidence(
            "doc-1",
            "snap-1",
            "node-1",
            "Nếu Bên A thanh toán chậm, Bên A phải chịu phạt 0,1%/ngày.",
        ),
        profile="SALES",
        dossier_id="dos-1",
    )
    for frame in frames:
        modality = frame.get("modality_negation")
        assert modality.reason != "declarative_obligation", frame
        assert not (frame.get("action").value == "PAY" and modality.value == "REQUIRED"), frame


def test_conditional_lead_ins_keep_modality_unknown():
    for text in (
        "Khi Bên A thanh toán đợt 1, Bên B giao hàng.",
        "Trường hợp Bên A thanh toán chậm thì chịu lãi.",
    ):
        for frame in extract_frames(
            Evidence("doc-1", "snap-1", "node-1", text), profile="SALES", dossier_id="dos-1"
        ):
            assert frame.get("modality_negation").reason != "declarative_obligation", text
