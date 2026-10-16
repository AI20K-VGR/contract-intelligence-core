"""HD-TEST-2026-002 (held-out): fictional goods-supply contract + two annexes.

Planted defects differ in kind from HD-TEST-2026-001 so tuning on 001 cannot memorize them:
a body↔annex value conflict under *different* article numbers with no amendment wording, a
reference that is not an amendment, a scope-limitation clause, a clause cut by a page break, an
explicit amendment that changes a deadline, a verbatim duplicate clause, a pipe table and page
furniture. Lines wrap the way AI1 OCR wraps them. Every name, number and term is invented.

``EXPECTED`` was written before the first scoring run and is not tuned to results; a wrong
expectation is a gold defect for a human reviewer, never something an optimizer may edit.
"""

from __future__ import annotations

from fixtures.seeded.common import DISCLAIMER, build_request

DOSSIER_ID = "dossier-seeded-hd-test-002"
_FOOTER = "TÀI LIỆU MẪU KIỂM THỬ AI2 - KHÔNG CÓ GIÁ TRỊ GIAO DỊCH"

BODY_PAGES = [
    [
        "HỢP ĐỒNG MUA BÁN VẬT TƯ ĐIỆN",
        "Số: HD-TEST-2026-002 | Tài liệu hư cấu phục vụ kiểm thử AI2",
        *DISCLAIMER,
        "Điều 1. Hàng hóa",
        "1.1. Bên B bán cho Bên A 500 bộ đèn LED chiếu sáng công nghiệp công suất 150W theo danh mục tại Phụ lục",
        "01 kèm theo Hợp đồng này.",
        "1.2. Hàng hóa phải mới 100%, đúng chủng loại và có chứng nhận xuất xứ, chứng nhận chất lượng của nhà sản xuất.",
        "Điều 2. Giá trị hợp đồng",
        "2.1. Tổng giá trị hợp đồng là 900.000.000 đồng (Bằng chữ: Chín trăm triệu đồng), đã bao gồm thuế giá trị",
        "gia tăng.",
        "Điều 3. Giao hàng",
        "3.1. Thời gian giao hàng là trong vòng 30 ngày kể từ ngày ký Hợp đồng, tại kho của Bên A ở Bình Dương.",
        "3.2. Bên B thông báo cho Bên A bằng văn bản trước ít nhất 03 ngày làm việc trước mỗi đợt giao hàng.",
        "Điều 4. Thanh toán",
        "4.1. Bên A thanh toán 30% giá trị hợp đồng khi ký Hợp đồng và 70% còn lại sau khi nghiệm thu toàn bộ hàng",
        "hóa.",
        "4.2. Bên A thanh toán mỗi đợt trong vòng 10 ngày làm việc kể từ ngày nhận được hóa đơn hợp lệ của Bên B và",
        _FOOTER,
        "Trang 1",
    ],
    [
        _FOOTER,
        "biên bản nghiệm thu được hai bên ký.",
        "Điều 5. Bảo hành",
        "5.1. Bên B bảo hành hàng hóa trong thời hạn 24 tháng kể từ ngày ký biên bản nghiệm thu.",
        "5.2. Trong thời hạn bảo hành, Bên B sửa chữa hoặc thay thế hàng hóa bị lỗi trong vòng 07 ngày kể từ ngày",
        "nhận được thông báo của Bên A.",
        "Điều 6. Phạt vi phạm",
        "6.1. Bên B chậm giao hàng thì phải chịu phạt 0,5% giá trị phần hàng giao chậm cho mỗi ngày chậm.",
        "6.2. Tổng mức phạt vi phạm không vượt quá 8% giá trị phần nghĩa vụ hợp đồng bị vi phạm.",
        "6.3. Bên B chậm giao hàng thì phải chịu phạt 0,5% giá trị phần hàng giao chậm cho mỗi ngày chậm.",
        "Điều 7. Hiệu lực",
        "7.1. Hợp đồng có hiệu lực từ ngày ký và được lập thành 02 bản có giá trị pháp lý như nhau.",
        _FOOTER,
        "Trang 2",
    ],
]

ANNEX_PAGES = [
    [
        "PHỤ LỤC 01 - DANH MỤC HÀNG HÓA VÀ ĐIỀU KIỆN GIAO HÀNG",
        "Kèm theo Hợp đồng số HD-TEST-2026-002",
        *DISCLAIMER,
        "| STT | Hàng hóa | Đơn vị | Số lượng | Đơn giá (đồng) | Thành tiền (đồng) |",
        "| 1 | Đèn LED chiếu sáng công nghiệp 150W | bộ | 500 | 1.800.000 | 900.000.000 |",
        "Điều 2. Điều kiện giao hàng",
        "2.1. Thời gian giao hàng là trong vòng 45 ngày kể từ ngày ký Hợp đồng, tại kho của Bên A ở Bình Dương.",
        "2.2. Bên B bảo hành hàng hóa theo quy định tại khoản 1 Điều 5 của Hợp đồng.",
        _FOOTER,
        "Trang 1",
    ],
    [
        "PHỤ LỤC 02 - SỬA ĐỔI ĐIỀU KHOẢN THANH TOÁN VÀ PHẠT",
        "Kèm theo Hợp đồng số HD-TEST-2026-002",
        *DISCLAIMER,
        "1. Sửa đổi khoản 2 Điều 4 của Hợp đồng như sau: Bên A thanh toán mỗi đợt trong vòng 15 ngày làm việc kể",
        "từ ngày nhận được hóa đơn hợp lệ của Bên B.",
        "2. Khoản 2 Điều 6 không áp dụng đối với trường hợp chậm giao hàng do sự kiện bất khả kháng theo quy định",
        "của pháp luật.",
        _FOOTER,
        "Trang 2",
    ],
]

EXPECTED = {
    "luong1_must": [("1. Sửa đổi khoản 2 Điều 4", "4.2.")],
    # A clause citing "theo quy định tại khoản 1 Điều 5" refers to it; it does not amend it.
    "luong1_forbidden": [("2.2. Bên B bảo hành hàng hóa theo quy định", "5.1.")],
    "frame_slots": [
        ("3.1.", {"deadline": "30", "deadline_unit": "day"}),
        ("2.1. Thời gian giao hàng", {"deadline": "45", "deadline_unit": "day"}),
        ("4.2.", {"deadline": "10", "deadline_unit": "business-day"}),
        ("1. Sửa đổi khoản 2 Điều 4", {"deadline": "15", "deadline_unit": "business-day"}),
        ("5.2.", {"deadline": "07", "deadline_unit": "day"}),
    ],
    "semantic_difference": [
        ("3.1.", "2.1. Thời gian giao hàng", "deadline"),  # 30 vs 45 days, no amendment wording
        ("4.2.", "1. Sửa đổi khoản 2 Điều 4", "deadline"),  # explicit amendment 10 -> 15
    ],
    "clause_complete": [
        ("1.1.", "kèm theo Hợp đồng này"),
        ("2.1. Tổng giá trị", "gia tăng"),
        ("4.1.", "toàn bộ hàng hóa"),
        ("1. Sửa đổi khoản 2 Điều 4", "hóa đơn hợp lệ"),
        ("2. Khoản 2 Điều 6", "của pháp luật"),
    ],
    "candidates_must_keep": [
        ("6.1.", "6.3."),  # verbatim duplicate penalty clause
        ("3.1.", "2.1. Thời gian giao hàng"),  # body/annex delivery-time conflict
    ],
    # The limitation must reach review as some relation (operation edge or pair candidate).
    "related_any": [("2. Khoản 2 Điều 6", "6.2.")],
    "issues_must": [("CLAUSE_CONTINUES_ON_NEXT_PAGE", "4.2.", "biên bản nghiệm thu được hai bên ký")],
    "never_candidate": ["TÀI LIỆU MẪU", "Trang "],
    "never_value_mismatch": [("5.1.", "7.1.")],  # 24 months vs 2 copies: different units
}


def request(*, egress_allowed: bool = False) -> dict:
    return build_request(dossier_id=DOSSIER_ID, body_pages=BODY_PAGES, annex_pages=ANNEX_PAGES,
                         egress_allowed=egress_allowed)

# Classifier (LLM) gold, written before the first live run.
LIVE_EXPECTED = {
    "must": [
        ("CONFLICT", "3.1.", "2.1. Thời gian giao hàng"),  # 30 vs 45 days, no amendment wording
        ("DUPLICATE", "6.1.", "6.3."),
        ("REFERENCE", "2.2. Bên B bảo hành hàng hóa theo quy định", "5.1."),
    ],
    "forbidden_label_on": [("DUPLICATE", "TÀI LIỆU MẪU")],
}
