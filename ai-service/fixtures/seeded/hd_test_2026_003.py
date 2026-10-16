"""HD-TEST-2026-003 (dev): fictional equipment-maintenance service contract + one annex.

Planted: a penalty rate restated differently in the annex under the same article (0,1% vs
0,2%, no amendment wording); a substitution worded "Thay thế ... bằng nội dung sau"; a reference
worded "theo khoản 2 Điều 3" that must not become an operation edge; a fee whose amount sits on
the wrapped second line; a term cut by a page break with the number on the next page; a pipe
table and page furniture. Every name, number and term is invented. ``EXPECTED`` was written
before the first scoring run.
"""

from __future__ import annotations

from fixtures.seeded.common import DISCLAIMER, build_request

DOSSIER_ID = "dossier-seeded-hd-test-003"
_FOOTER = "TÀI LIỆU MẪU KIỂM THỬ AI2 - KHÔNG CÓ GIÁ TRỊ GIAO DỊCH"

BODY_PAGES = [
    [
        "HỢP ĐỒNG DỊCH VỤ BẢO TRÌ THIẾT BỊ",
        "Số: HD-TEST-2026-003 | Tài liệu hư cấu phục vụ kiểm thử AI2",
        *DISCLAIMER,
        "Điều 1. Phạm vi dịch vụ",
        "1.1. Bên B bảo trì định kỳ 40 máy điều hòa trung tâm tại tòa nhà văn phòng của Bên A ở Quận 7, Thành phố",
        "Hồ Chí Minh.",
        "Điều 2. Phí dịch vụ",
        "2.1. Phí bảo trì hằng tháng mà Bên A thanh toán cho Bên B theo Hợp đồng này, đã bao gồm thuế, là",
        "25.000.000 đồng.",
        "Điều 3. Nghĩa vụ của Bên B",
        "3.1. Bên B cử kỹ thuật viên có chứng chỉ phù hợp thực hiện bảo trì theo lịch đã thống nhất với Bên A.",
        "3.2. Bên B phải khắc phục sự cố trong vòng 04 giờ kể từ khi nhận được thông báo của Bên A.",
        "Điều 4. Phạt vi phạm",
        "4.1. Bên B chậm khắc phục sự cố thì phải chịu phạt 0,1% phí bảo trì hằng tháng cho mỗi giờ chậm.",
        "Điều 5. Thời hạn",
        "5.1. Hợp đồng có thời hạn bảo trì liên tục kể từ ngày ký và được gia hạn theo thỏa thuận bằng văn bản là 12",
        _FOOTER,
        "Trang 1",
    ],
    [
        _FOOTER,
        "tháng kể từ ngày ký Hợp đồng.",
        "Điều 6. Nghiệm thu",
        "6.1. Hai bên nghiệm thu kết quả bảo trì hằng tháng trong vòng 05 ngày làm việc kể từ ngày kết thúc tháng.",
        "Điều 7. Điều khoản chung",
        "7.1. Hợp đồng được lập thành 02 bản có giá trị pháp lý như nhau, mỗi bên giữ 01 bản.",
        _FOOTER,
        "Trang 2",
    ],
]

ANNEX_PAGES = [
    [
        "PHỤ LỤC 01 - DANH MỤC THIẾT BỊ VÀ ĐIỀU CHỈNH",
        "Kèm theo Hợp đồng số HD-TEST-2026-003",
        *DISCLAIMER,
        "| STT | Thiết bị | Số lượng | Vị trí |",
        "| 1 | Máy điều hòa trung tâm 5HP | 40 | Tầng 1 đến tầng 10 |",
        "Điều 4. Phạt vi phạm",
        "4.1. Bên B chậm khắc phục sự cố thì phải chịu phạt 0,2% phí bảo trì hằng tháng cho mỗi giờ chậm.",
        "Thay thế khoản 1 Điều 6 của Hợp đồng bằng nội dung sau: Hai bên nghiệm thu kết quả bảo trì hằng tháng",
        "trong vòng 03 ngày làm việc kể từ ngày kết thúc tháng.",
        "Bên B lập báo cáo sự cố theo khoản 2 Điều 3 của Hợp đồng trong vòng 24 giờ sau khi khắc phục xong.",
        _FOOTER,
        "Trang 1",
    ],
]

EXPECTED = {
    "luong1_must": [("Thay thế khoản 1 Điều 6", "6.1.")],
    "luong1_forbidden": [("Bên B lập báo cáo sự cố theo khoản 2 Điều 3", "3.2.")],
    "frame_slots": [
        ("3.2.", {"deadline": "04"}),
        ("6.1.", {"deadline": "05", "deadline_unit": "business-day"}),
        ("Thay thế khoản 1 Điều 6", {"deadline": "03", "deadline_unit": "business-day"}),
    ],
    "semantic_difference": [
        ("6.1.", "Thay thế khoản 1 Điều 6", "deadline"),  # 05 -> 03 working days by substitution
    ],
    "clause_complete": [
        ("1.1.", "Hồ Chí Minh"),
        ("2.1. Phí bảo trì", "25.000.000 đồng"),
        ("Thay thế khoản 1 Điều 6", "kết thúc tháng"),
    ],
    "candidates_must_keep": [
        # same article number in body and annex, rate 0,1% vs 0,2%
        ("4.1. Bên B chậm khắc phục sự cố thì phải chịu phạt 0,1%", "4.1. Bên B chậm khắc phục sự cố thì phải chịu phạt 0,2%"),
    ],
    "issues_must": [("CLAUSE_CONTINUES_ON_NEXT_PAGE", "5.1.", "tháng kể từ ngày ký Hợp đồng")],
    "never_candidate": ["TÀI LIỆU MẪU", "Trang "],
    "never_value_mismatch": [("3.2.", "7.1.")],  # 04 hours vs 02 copies
}

LIVE_EXPECTED = {
    "must": [
        ("CONFLICT", "4.1. Bên B chậm khắc phục sự cố thì phải chịu phạt 0,1%",
         "4.1. Bên B chậm khắc phục sự cố thì phải chịu phạt 0,2%"),
        ("REFERENCE", "Bên B lập báo cáo sự cố theo khoản 2 Điều 3", "3.2."),
    ],
    "forbidden_label_on": [("DUPLICATE", "TÀI LIỆU MẪU")],
}


def request(*, egress_allowed: bool = False) -> dict:
    return build_request(dossier_id=DOSSIER_ID, body_pages=BODY_PAGES, annex_pages=ANNEX_PAGES,
                         egress_allowed=egress_allowed)
