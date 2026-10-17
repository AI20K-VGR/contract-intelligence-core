"""HD-TEST-2026-005 (dev): fictional supply contract with three payment installments + one annex.

Mirrors the staging E2E report of 16/10 (#121): the body pays installment 1 at 30% and
installment 2 at 40%, which are different terms, not a conflict; the annex states installment 1
at 25% without the wording of an amendment, which is the planted conflict with clause 5.1.
Every name, number and term is invented. ``EXPECTED`` was written before the first run.
"""

from __future__ import annotations

from fixtures.seeded.common import DISCLAIMER, build_request

DOSSIER_ID = "dossier-seeded-hd-test-005"

BODY_PAGES = [
    [
        "HỢP ĐỒNG MUA BÁN THIẾT BỊ PHÒNG THÍ NGHIỆM",
        "Số: HD-TEST-2026-005",
        *DISCLAIMER,
        "Điều 1. Hàng hóa",
        "1.1. Bên B cung cấp 06 tủ an toàn sinh học và 12 máy ly tâm theo danh mục đã được hai bên ký.",
        "Điều 2. Giá trị hợp đồng",
        "2.1. Tổng giá trị hợp đồng là 2.400.000.000 đồng, đã bao gồm thuế giá trị gia tăng.",
        "Điều 5. Thanh toán",
        "5.1. Đợt 1: Bên A thanh toán 30% giá trị hợp đồng trong vòng 10 ngày kể từ ngày ký Hợp đồng.",
        "5.2. Đợt 2: Bên A thanh toán 40% giá trị hợp đồng trong vòng 10 ngày kể từ ngày nhận hàng.",
        "5.3. Đợt 3: Bên A thanh toán 30% giá trị hợp đồng còn lại trong vòng 15 ngày kể từ ngày nghiệm thu.",
        "Trang 1",
    ],
    [
        "Điều 6. Bảo hành",
        "6.1. Bên B bảo hành thiết bị trong thời hạn 24 tháng kể từ ngày ký biên bản nghiệm thu.",
        "Điều 7. Hiệu lực",
        "7.1. Hợp đồng có hiệu lực từ ngày ký.",
        "Trang 2",
    ],
]

ANNEX_PAGES = [
    [
        "PHỤ LỤC 01 - TIẾN ĐỘ THANH TOÁN",
        "Kèm theo Hợp đồng số HD-TEST-2026-005",
        *DISCLAIMER,
        "1. Tiến độ thanh toán",
        "Đợt 1: Bên A thanh toán 25% giá trị hợp đồng trong vòng 10 ngày kể từ ngày ký Hợp đồng.",
        "Trang 1",
    ],
]

EXPECTED = {
    # Different installments of one schedule are different terms.
    "never_conflict": [
        ("5.1. Đợt 1", "5.2. Đợt 2"),
        ("5.2. Đợt 2", "5.3. Đợt 3"),
        ("5.1. Đợt 1", "5.3. Đợt 3"),
    ],
    # Annex restates installment 1 at another rate without amendment wording.
    "related_any": [("5.1. Đợt 1", "Đợt 1: Bên A thanh toán 25%")],
}

LIVE_EXPECTED = {
    "must": [("CONFLICT", "5.1. Đợt 1", "Đợt 1: Bên A thanh toán 25%")],
    "forbidden_label_on": [("CONFLICT", "5.2. Đợt 2")],
}


def request(*, egress_allowed: bool = False) -> dict:
    return build_request(
        dossier_id=DOSSIER_ID,
        body_pages=BODY_PAGES,
        annex_pages=ANNEX_PAGES,
        egress_allowed=egress_allowed,
    )
