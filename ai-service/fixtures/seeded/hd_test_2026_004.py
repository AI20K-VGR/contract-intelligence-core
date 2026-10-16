"""HD-TEST-2026-004 (dev): fictional office-furniture supply contract + one annex.

Planted traps for *false* findings as well as misses: the annex restates a payment term with
the same value written differently ("05 ngày" vs "5 ngày") and must not be reported as a
difference; the annex restates the warranty unchanged and must not be an operation edge; an
explicit amendment worded "Sửa đổi điểm a khoản 2 Điều 3" changes a percentage; a verbatim
duplicate across body pages; an all-caps running header at the top of page 2 followed by a
sentence. Every name, number and term is invented. ``EXPECTED`` was written before the first run.
"""

from __future__ import annotations

from fixtures.seeded.common import DISCLAIMER, build_request

DOSSIER_ID = "dossier-seeded-hd-test-004"
_HEADER = "HỢP ĐỒNG HD-TEST-2026-004 - TÀI LIỆU MẪU KIỂM THỬ AI2"

BODY_PAGES = [
    [
        _HEADER,
        "HỢP ĐỒNG CUNG CẤP NỘI THẤT VĂN PHÒNG",
        *DISCLAIMER,
        "Điều 1. Hàng hóa",
        "1.1. Bên B cung cấp 120 bộ bàn ghế làm việc và 15 tủ hồ sơ theo mẫu đã được Bên A phê duyệt.",
        "Điều 2. Giá trị",
        "2.1. Tổng giá trị hợp đồng là 480.000.000 đồng, đã bao gồm thuế giá trị gia tăng và chi phí vận chuyển.",
        "Điều 3. Thanh toán",
        "3.1. Bên A thanh toán cho Bên B theo hai đợt như sau:",
        "a) 40% giá trị hợp đồng trong vòng 05 ngày kể từ ngày ký Hợp đồng;",
        "b) 60% giá trị hợp đồng còn lại sau khi nghiệm thu toàn bộ hàng hóa.",
        "3.2. Bên A thanh toán mỗi đợt trong vòng 05 ngày kể từ ngày nhận được hóa đơn hợp lệ của Bên B.",
        "Trang 1",
    ],
    [
        _HEADER,
        "Điều 4. Bảo hành",
        "4.1. Bên B bảo hành hàng hóa trong thời hạn 18 tháng kể từ ngày ký biên bản nghiệm thu.",
        "4.2. Bên B thay thế linh kiện bị lỗi trong vòng 48 giờ kể từ khi nhận được yêu cầu của Bên A.",
        "Điều 5. Điều khoản chung",
        "5.1. Bên B thay thế linh kiện bị lỗi trong vòng 48 giờ kể từ khi nhận được yêu cầu của Bên A.",
        "5.2. Hợp đồng có hiệu lực từ ngày ký.",
        "Trang 2",
    ],
]

ANNEX_PAGES = [
    [
        "PHỤ LỤC 01 - SỬA ĐỔI ĐIỀU KHOẢN THANH TOÁN",
        "Kèm theo Hợp đồng số HD-TEST-2026-004",
        *DISCLAIMER,
        "1. Sửa đổi điểm a khoản 1 Điều 3 của Hợp đồng như sau: a) 30% giá trị hợp đồng trong vòng 05 ngày kể từ",
        "ngày ký Hợp đồng;",
        "2. Bên A thanh toán mỗi đợt trong vòng 5 ngày kể từ ngày nhận được hóa đơn hợp lệ của Bên B.",
        "3. Bên B bảo hành hàng hóa trong thời hạn 18 tháng kể từ ngày ký biên bản nghiệm thu.",
        "Trang 1",
    ],
]

EXPECTED = {
    "luong1_must": [("1. Sửa đổi điểm a khoản 1 Điều 3", "a) 40% giá trị hợp đồng")],
    # Restating the warranty unchanged is not an amendment of 4.1.
    "luong1_forbidden": [("3. Bên B bảo hành hàng hóa", "4.1.")],
    "frame_slots": [
        ("3.2.", {"deadline": "05", "deadline_unit": "day"}),
        ("2. Bên A thanh toán mỗi đợt", {"deadline": "5", "deadline_unit": "day"}),
    ],
    # Same value written "05" and "5": comparing them must not report a deadline difference.
    "semantic_same": [("3.2.", "2. Bên A thanh toán mỗi đợt", "deadline")],
    "clause_complete": [("1. Sửa đổi điểm a khoản 1 Điều 3", "ngày ký Hợp đồng;")],
    "candidates_must_keep": [("4.2.", "5.1.")],  # verbatim duplicate across articles/pages
    "never_candidate": ["HỢP ĐỒNG HD-TEST-2026-004 - TÀI LIỆU MẪU", "Trang "],
    # The running header at the top of page 2 never absorbs the heading/sentence under it.
    "clause_starts": ["Điều 4. Bảo hành"],
}

LIVE_EXPECTED = {
    "must": [("DUPLICATE", "4.2.", "5.1.")],
    "forbidden_label_on": [("CONFLICT", "3.2."), ("DUPLICATE", "HỢP ĐỒNG HD-TEST-2026-004 - TÀI LIỆU MẪU")],
}


def request(*, egress_allowed: bool = False) -> dict:
    return build_request(dossier_id=DOSSIER_ID, body_pages=BODY_PAGES, annex_pages=ANNEX_PAGES,
                         egress_allowed=egress_allowed)
