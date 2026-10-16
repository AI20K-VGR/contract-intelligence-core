"""HD-TEST-2026-001: fictional service/supply contract + three annexes with planted relations.

Lines are the AI1 OCR lines of the sample PDF, kept verbatim (mid-sentence wraps and page
footers included) because those are what broke AI2. Every name, number and term is invented.

``EXPECTED`` is the review gold: what a correct AI2 run must find and must not emit. Clauses are
addressed by a text prefix of their node, so the gold survives node-id changes.
"""

from __future__ import annotations

from fixtures.seeded.common import DISCLAIMER as _DISCLAIMER
from fixtures.seeded.common import TENANT_ID, build_request, context_caps_env, semantic_profile

DOSSIER_ID = "dossier-seeded-hd-test"
__all__ = ["ANNEX_PAGES", "BODY_PAGES", "DOSSIER_ID", "EXPECTED", "TENANT_ID", "context_caps_env",
           "request", "semantic_profile"]

BODY_PAGES = [
    [
        "HỢP ĐỒNG DỊCH VỤ VÀ CUNG CẤP THIẾT BỊ",
        "Số: HD-TEST-2026-001 | Phiên bản mẫu phục vụ kiểm thử AI2",
        *_DISCLAIMER,
        "Hôm nay, ngày 10 tháng 10 năm 2026, tại Thành phố Hồ Chí Minh, các bên gồm:",
        "BÊN A - BÊN THUÊ DỊCH VỤ: CÔNG TY TNHH MINH AN. Địa chỉ: 18 Đường Số 4, Thành phố Hồ Chí",
        "Minh. Đại diện: Nguyễn An, Giám đốc.",
        "BÊN B - BÊN CUNG CẤP: CÔNG TY CỔ PHẦN BÌNH MINH. Địa chỉ: 25 Đường Số 8, Thành phố Hồ",
        "Chí Minh. Đại diện: Trần Bình, Tổng Giám đốc.",
        "Điều 1. Phạm vi công việc",
        "1.1. Bên B cung cấp 20 máy quét mã vạch, cài đặt phần mềm quản lý kho và hướng dẫn sử dụng cho",
        "Bên A.",
        "1.2. Công việc tại khoản 1.1 bao gồm giao thiết bị, cài đặt phần mềm, cấu hình hệ thống và đào tạo",
        "người sử dụng.",
        "1.3. Bên B cung cấp 20 máy quét mã vạch, cài đặt phần mềm quản lý kho và hướng dẫn sử dụng cho",
        "Bên A.",
        "Điều 2. Giải thích từ ngữ",
        "2.1. Ngày làm việc là ngày từ thứ Hai đến thứ Sáu, không bao gồm ngày nghỉ lễ theo quy định pháp luật",
        "Việt Nam.",
        "2.2. Nghiệm thu là việc đại diện hai bên kiểm tra và ký biên bản xác nhận kết quả bàn giao.",
        "Điều 3. Tài liệu và dẫn chiếu",
        "3.1. Lịch thanh toán được quy định tại khoản 1 Điều 5 của Hợp đồng này.",
        "3.2. Thời hạn thanh toán sau khi nhận hóa đơn được quy định tại khoản 2 Điều 5 của Hợp đồng này.",
        "3.3. Việc kiểm tra hàng hóa và ký biên bản nghiệm thu thực hiện theo khoản 1 Điều 6 của Hợp đồng",
        "này.",
        "Điều 4. Giá trị hợp đồng",
        "4.1. Tổng giá trị hợp đồng là 1.200.000.000 đồng (Bằng chữ: Một tỷ hai trăm triệu đồng), đã bao gồm",
        "thuế giá trị gia tăng.",
        "4.2. Giá trị tại khoản 4.1 là giá trọn gói cho phạm vi công việc tại Điều 1.",
        "Điều 5. Thanh toán",
        "5.1. Bên A thanh toán cho Bên B theo ba đợt: 30% khi ký hợp đồng, 40% khi giao đủ thiết bị và 30% sau",
        "khi nghiệm thu.",
        "5.2. Bên A thanh toán mỗi khoản trong vòng 07 ngày kể từ ngày nhận được hóa đơn hợp lệ của Bên B.",
        "5.3. Thanh toán được thực hiện bằng chuyển khoản vào tài khoản do Bên B thông báo bằng văn bản.",
        "TÀI LIỆU MẪU KIỂM THỬ AI2 - KHÔNG CÓ GIÁ TRỊ GIAO DỊCH",
        "Trang 1",
        "TÀI LIỆU MẪU AI2 - HƯ CẤU, KHÔNG CÓ GIÁ TRỊ GIAO DỊCH",
        "Trang 1/5",
    ],
    [
        "Điều 6. Giao hàng và nghiệm thu",
        "6.1. Bên A kiểm tra số lượng và tình trạng thiết bị trong vòng 03 ngày làm việc kể từ khi nhận hàng.",
        "6.2. Hai bên lập biên bản nghiệm thu sau khi hoàn tất cài đặt và hướng dẫn sử dụng.",
        "Điều 7. Bảo hành",
        "7.1. Thiết bị được bảo hành trong 12 tháng kể từ ngày ký biên bản nghiệm thu.",
        "7.2. Bên B sửa chữa hoặc thay thế thiết bị bị lỗi do nhà sản xuất trong thời hạn bảo hành.",
        "Điều 8. Vi phạm và giải quyết tranh chấp",
        "8.1. Bên vi phạm nghĩa vụ phải khắc phục vi phạm và bồi thường thiệt hại trực tiếp, hợp lý cho bên còn",
        "lại.",
        "8.2. Mọi tranh chấp được ưu tiên giải quyết bằng thương lượng trong 30 ngày trước khi khởi kiện tại tòa",
        "án có thẩm quyền.",
        "8.3. Không bên nào được đơn phương miễn trừ nghĩa vụ thanh toán đã đến hạn.",
        "Điều 9. Hiệu lực",
        "9.1. Hợp đồng có hiệu lực từ ngày ký và được lập thành 02 bản có giá trị như nhau, mỗi bên giữ 01 bản.",
        "ĐẠI DIỆN BÊN A ĐẠI DIỆN BÊN B",
        "TÀI LIỆU MẪU KIỂM THỬ AI2 - KHÔNG CÓ GIÁ TRỊ GIAO DỊCH",
        "Trang 2",
        "TÀI LIỆU MẪU AI2 - HƯ CẤU, KHÔNG CÓ GIÁ TRỊ GIAO DỊCH",
        "Trang 2/5",
    ],
]

ANNEX_PAGES = [
    [
        "PHỤ LỤC 01 - BẢNG GIÁ VÀ GIÁ TRỊ ĐIỀU CHỈNH",
        "Kèm theo Hợp đồng số HD-TEST-2026-001",
        *_DISCLAIMER,
        "Phụ lục này là một phần của Hợp đồng số HD-TEST-2026-001 giữa Công ty TNHH Minh An và Công ty",
        "Cổ phần Bình Minh.",
        "1. Bảng giá hạng mục",
        "Hạng mục", "Mô tả", "Thành tiền (đồng)",
        "Thiết bị", "20 máy quét mã vạch", "600.000.000",
        "Phần mềm", "Cài đặt và bản quyền 01 năm", "450.000.000",
        "Triển khai", "Cấu hình, tích hợp và đào tạo", "300.000.000",
        "TỔNG CỘNG", "Đã bao gồm thuế giá trị gia tăng", "1.350.000.000",
        "2. Giá trị áp dụng",
        "2.1. Tổng giá trị hợp đồng sau khi đối chiếu bảng giá tại Phụ lục này là 1.350.000.000 đồng (Bằng chữ:",
        "Một tỷ ba trăm năm mươi triệu đồng).",
        "2.2. Các hạng mục được nghiệm thu theo tiêu chí tại Điều 6 của Hợp đồng.",
        "TÀI LIỆU MẪU KIỂM THỬ AI2 - KHÔNG CÓ GIÁ TRỊ GIAO DỊCH",
        "Trang 1",
        "TÀI LIỆU MẪU AI2 - HƯ CẤU, KHÔNG CÓ GIÁ TRỊ GIAO DỊCH",
        "Trang 3/5",
    ],
    [
        "PHỤ LỤC 02 - SỬA ĐỔI VÀ BỔ SUNG ĐIỀU KHOẢN",
        "Kèm theo Hợp đồng số HD-TEST-2026-001",
        *_DISCLAIMER,
        "Các bên thống nhất sửa đổi, bổ sung một số điều khoản của Hợp đồng số HD-TEST-2026-001 như sau:",
        "1. Sửa đổi thời hạn thanh toán",
        "Điều chỉnh khoản 2 Điều 5 của Hợp đồng như sau: Bên A thanh toán mỗi khoản trong vòng 10 ngày kể",
        "từ ngày nhận được hóa đơn hợp lệ của Bên B.",
        "2. Bổ sung điều kiện nghiệm thu",
        "Bổ sung điểm c) vào khoản 1 Điều 6 như sau: Nếu biên bản kiểm tra ghi nhận lỗi nghiêm trọng ảnh",
        "hưởng đến vận hành, Bên A có quyền chưa ký biên bản nghiệm thu cho đến khi Bên B khắc phục",
        "xong.",
        "3. Giới hạn phạm vi áp dụng",
        "Khoản 2 Điều 7 không áp dụng đối với trường hợp thiết bị hư hỏng do Bên A tự ý tháo lắp hoặc sử dụng",
        "sai hướng dẫn.",
        "4. Quyền từ chối",
        "Bên A có quyền từ chối nghiệm thu theo quy định tại khoản 1 Điều 6 của Hợp đồng nếu thiết bị không",
        "đạt thông số kỹ thuật đã thỏa thuận.",
        "5. Bãi bỏ điều khoản",
        "Bãi bỏ khoản 3 Điều 8 của Hợp đồng.",
        "6. Hiệu lực các nội dung còn lại",
        "Các nội dung khác của Hợp đồng không được sửa đổi tại Phụ lục này tiếp tục có hiệu lực.",
        "TÀI LIỆU MẪU KIỂM THỬ AI2 - KHÔNG CÓ GIÁ TRỊ GIAO DỊCH",
        "Trang 1",
        "TÀI LIỆU MẪU AI2 - HƯ CẤU, KHÔNG CÓ GIÁ TRỊ GIAO DỊCH",
        "Trang 4/5",
    ],
    [
        "PHỤ LỤC 03 - ĐIỀU CHỈNH GIÁ TRỊ HỢP ĐỒNG",
        "Kèm theo Hợp đồng số HD-TEST-2026-001",
        *_DISCLAIMER,
        "Các bên xác nhận nội dung điều chỉnh giá trị hợp đồng như sau:",
        "1. Giá trị sau điều chỉnh",
        "Tổng giá trị hợp đồng sau điều chỉnh là 1.280.000.000 đồng (Bằng chữ: Một tỷ hai trăm tám mươi triệu",
        "đồng).",
        "Giá trị này áp dụng kể từ ngày 15 tháng 10 năm 2026 và thay cho giá trị trước đây của hợp đồng.",
        "2. Xác nhận",
        "Các bên giữ nguyên các nội dung khác không được điều chỉnh tại Phụ lục này.",
        "TÀI LIỆU MẪU KIỂM THỬ AI2 - KHÔNG CÓ GIÁ TRỊ GIAO DỊCH",
        "Trang 1",
        "TÀI LIỆU MẪU AI2 - HƯ CẤU, KHÔNG CÓ GIÁ TRỊ GIAO DỊCH",
        "Trang 5/5",
    ],
]

# Review gold. Each clause is a node-text prefix; pairs are unordered unless the kind says so.
EXPECTED = {
    # Luồng 1: explicit operations from the annex onto the body (amending -> target).
    "luong1_must": [
        ("Điều chỉnh khoản 2 Điều 5", "5.2."),
        ("Bổ sung điểm c) vào khoản 1 Điều 6", "6.1."),
        ("Bãi bỏ khoản 3 Điều 8", "8.3."),
        ("Tổng giá trị hợp đồng sau điều chỉnh", "4.1."),
    ],
    # Semantic frames must carry the planted values, or no comparison can see them.
    "frame_slots": [
        ("5.2.", {"deadline": "07", "deadline_unit": "day"}),
        ("Điều chỉnh khoản 2 Điều 5", {"deadline": "10", "deadline_unit": "day"}),
        ("6.1.", {"deadline": "03", "deadline_unit": "business-day"}),
    ],
    # Planted payment-term change (07 -> 10 days) must reach review as a value difference.
    "semantic_difference": [("5.2.", "Điều chỉnh khoản 2 Điều 5", "deadline")],
    # A clause wrapped over two OCR lines must stay one node (prefix, words of the 2nd line).
    "clause_complete": [
        ("Điều chỉnh khoản 2 Điều 5", "hóa đơn hợp lệ"),
        ("4.1.", "thuế giá trị gia tăng"),
        ("1.1.", "cho Bên A"),
    ],
    # Luồng 2 candidates that must survive the top-K cap (sent to the classifier).
    "candidates_must_keep": [
        ("1.1.", "1.3."),  # verbatim duplicate scope clause
        ("4.1.", "2.1. Tổng giá trị hợp đồng sau khi đối chiếu"),  # body 1.2 bn vs annex 1.35 bn
    ],
    # Page furniture is never a clause: no candidate may touch it.
    "never_candidate": ["TÀI LIỆU MẪU", "Trang "],
    # Clause numbers and references ("khoản 1 Điều 6") are not values to mismatch on.
    "never_value_mismatch": [
        ("2.1. Ngày làm việc", "Bên A có quyền từ chối nghiệm thu"),
        ("3.3. Việc kiểm tra hàng hóa", "2.2. Các hạng mục được nghiệm thu"),
        ("5.2.", "9.1."),
    ],
}


def request(*, egress_allowed: bool = False, body_pages: list[list[str]] | None = None,
            annex_pages: list[list[str]] | None = None) -> dict:
    return build_request(
        dossier_id=DOSSIER_ID,
        body_pages=BODY_PAGES if body_pages is None else body_pages,
        annex_pages=ANNEX_PAGES if annex_pages is None else annex_pages,
        egress_allowed=egress_allowed,
    )

# Classifier (LLM) gold for fixtures.seeded.run_live: (label, a, b) unordered; forbidden labels on a prefix.
LIVE_EXPECTED = {
    "must": [
        ("CONFLICT", "4.1.", "2.1. Tổng giá trị hợp đồng sau khi đối chiếu"),
        ("DUPLICATE", "1.1.", "1.3."),
        ("REFERENCE", "3.2.", "5.2."),
        ("REFERENCE", "3.3.", "6.1."),
    ],
    "forbidden_label_on": [("DUPLICATE", "TÀI LIỆU MẪU")],
}
