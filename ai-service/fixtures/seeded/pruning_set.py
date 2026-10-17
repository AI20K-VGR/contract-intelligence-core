"""Fictional dossiers for measuring same-article pair pruning (no LLM needed).

Each dossier lists ``RELATED`` clause pairs (by text prefix) that a pair classifier must still
see, written before any pruning rule was tuned: lead → its points, a heading → its body, a cap
→ the penalty it caps, an intra-article "khoản X.Y" reference, an annex heading → its change.
Sibling clauses on different subjects are deliberately many: they are what pruning may drop.
``SPLIT`` keeps two dossiers held out from tuning. Every name, number and term is invented.
"""

from __future__ import annotations

from dataclasses import dataclass

from fixtures.seeded.common import DISCLAIMER, build_request


@dataclass(frozen=True)
class Dossier:
    DOSSIER_ID: str
    SPLIT: str
    BODY_PAGES: list[list[str]]
    ANNEX_PAGES: list[list[str]]
    RELATED: list[tuple[str, str]]

    def request(self, *, egress_allowed: bool = False) -> dict:
        return build_request(dossier_id=self.DOSSIER_ID, body_pages=self.BODY_PAGES,
                             annex_pages=self.ANNEX_PAGES, egress_allowed=egress_allowed)


SOFTWARE = Dossier(
    "dossier-pruning-005", "dev",
    [[
        "HỢP ĐỒNG CUNG CẤP PHẦN MỀM QUẢN LÝ KHO",
        *DISCLAIMER,
        "Điều 1. Phạm vi cung cấp",
        "1.1. Bên B cung cấp bản quyền phần mềm quản lý kho cho 50 người dùng trong thời hạn 24 tháng.",
        "1.2. Bên B cài đặt phần mềm trên máy chủ do Bên A chuẩn bị tại trụ sở của Bên A.",
        "1.3. Bên B đào tạo 10 cán bộ của Bên A về vận hành phần mềm trong 03 buổi.",
        "1.4. Các hạng mục tại khoản 1.1 và khoản 1.2 được nghiệm thu chung trong một biên bản.",
        "Điều 2. Thanh toán",
        "2.1. Bên A thanh toán cho Bên B theo các đợt sau:",
        "a) 50% giá trị hợp đồng trong vòng 10 ngày kể từ ngày ký Hợp đồng;",
        "b) 50% giá trị hợp đồng còn lại trong vòng 15 ngày kể từ ngày nghiệm thu.",
        "2.2. Hình thức thanh toán là chuyển khoản vào tài khoản ngân hàng của Bên B.",
        "2.3. Bên B xuất hóa đơn giá trị gia tăng trước mỗi lần Bên A thanh toán.",
        "Trang 1",
    ], [
        "Điều 3. Bảo mật dữ liệu",
        "3.1. Bên B không được sao chép dữ liệu kho của Bên A ra ngoài hệ thống khi chưa có văn bản đồng ý.",
        "3.2. Bên B lưu nhật ký truy cập hệ thống trong tối thiểu 12 tháng.",
        "3.3. Nghĩa vụ tại khoản 3.1 tiếp tục có hiệu lực 05 năm sau khi Hợp đồng chấm dứt.",
        "Điều 4. Phạt vi phạm",
        "4.1. Bên B chậm bàn giao phần mềm thì chịu phạt 0,5% giá trị hợp đồng cho mỗi ngày chậm.",
        "4.2. Tổng mức phạt vi phạm theo Điều này không vượt quá 8% giá trị hợp đồng.",
        "4.3. Bên vi phạm phải bồi thường thiệt hại thực tế phát sinh cho bên bị vi phạm.",
        "Trang 2",
    ]],
    [[
        "PHỤ LỤC 01 - ĐIỀU CHỈNH ĐÀO TẠO",
        "Kèm theo Hợp đồng số HD-PR-005",
        *DISCLAIMER,
        "1. Bổ sung nội dung đào tạo",
        "Bên B đào tạo thêm 05 cán bộ quản trị hệ thống của Bên A trong 02 buổi.",
        "2. Thời gian áp dụng",
        "Phụ lục này có hiệu lực kể từ ngày ký và là bộ phận không tách rời của Hợp đồng.",
        "Trang 1",
    ]],
    [
        ("2.1. Bên A thanh toán cho Bên B theo các đợt sau:", "a) 50% giá trị hợp đồng trong vòng 10"),
        ("2.1. Bên A thanh toán cho Bên B theo các đợt sau:", "b) 50% giá trị hợp đồng còn lại"),
        ("1.1. Bên B cung cấp bản quyền", "1.4. Các hạng mục tại khoản 1.1"),
        ("3.1. Bên B không được sao chép", "3.3. Nghĩa vụ tại khoản 3.1"),
        ("4.1. Bên B chậm bàn giao", "4.2. Tổng mức phạt vi phạm"),
        ("1. Bổ sung nội dung đào tạo", "Bên B đào tạo thêm 05 cán bộ"),
    ],
)

CONSTRUCTION = Dossier(
    "dossier-pruning-006", "dev",
    [[
        "HỢP ĐỒNG THI CÔNG CẢI TẠO NHÀ XƯỞNG",
        *DISCLAIMER,
        "Điều 1. Nội dung công việc",
        "1.1. Bên B thi công cải tạo mái tôn nhà xưởng diện tích 1.200 m2 theo bản vẽ đã phê duyệt.",
        "1.2. Bên B tự chuẩn bị máy móc, giàn giáo và nhân lực phục vụ thi công.",
        "1.3. Bên A bàn giao mặt bằng thi công cho Bên B trong vòng 03 ngày kể từ ngày ký Hợp đồng.",
        "Điều 2. Tiến độ",
        "2.1. Bên B hoàn thành toàn bộ công việc trong vòng 45 ngày kể từ ngày nhận mặt bằng.",
        "2.2. Thời hạn tại khoản 2.1 được gia hạn tương ứng với số ngày mưa lớn không thể thi công.",
        "2.3. Bên B báo cáo tiến độ thi công cho Bên A vào thứ Hai hằng tuần.",
        "Điều 3. An toàn lao động",
        "3.1. Bên B trang bị đủ dây an toàn và mũ bảo hộ cho công nhân làm việc trên cao.",
        "3.2. Bên B chịu trách nhiệm đối với mọi tai nạn lao động xảy ra trong phạm vi công trường.",
        "3.3. Bên A có quyền tạm dừng thi công khi phát hiện vi phạm quy định an toàn lao động.",
        "Trang 1",
    ], [
        "Điều 4. Thanh toán",
        "4.1. Giá trị hợp đồng được thanh toán thành hai đợt như sau:",
        "a) Tạm ứng 30% giá trị hợp đồng trong vòng 05 ngày kể từ ngày ký;",
        "b) Thanh toán 70% còn lại trong vòng 20 ngày kể từ ngày nghiệm thu hoàn thành.",
        "4.2. Bên A giữ lại 5% giá trị quyết toán làm tiền bảo hành công trình trong 12 tháng.",
        "Điều 5. Bảo hành",
        "5.1. Bên B bảo hành phần mái cải tạo trong thời hạn 24 tháng kể từ ngày nghiệm thu.",
        "5.2. Bên B khắc phục hư hỏng thuộc phạm vi bảo hành trong vòng 07 ngày kể từ ngày nhận thông báo.",
        "5.3. Tiền bảo hành tại khoản 4.2 được hoàn trả sau khi hết thời hạn bảo hành mà không có khiếu nại.",
        "Trang 2",
    ]],
    [[
        "PHỤ LỤC 01 - ĐIỀU CHỈNH TIẾN ĐỘ",
        "Kèm theo Hợp đồng số HD-PR-006",
        *DISCLAIMER,
        "1. Điều chỉnh thời hạn hoàn thành",
        "Sửa đổi khoản 1 Điều 2 của Hợp đồng như sau: Bên B hoàn thành toàn bộ công việc trong vòng 60 ngày kể từ ngày nhận mặt bằng.",
        "2. Các nội dung khác",
        "Các nội dung khác của Hợp đồng giữ nguyên hiệu lực.",
        "Trang 1",
    ]],
    [
        ("2.1. Bên B hoàn thành toàn bộ", "2.2. Thời hạn tại khoản 2.1"),
        ("4.1. Giá trị hợp đồng được thanh toán", "a) Tạm ứng 30%"),
        ("4.1. Giá trị hợp đồng được thanh toán", "b) Thanh toán 70%"),
        ("5.1. Bên B bảo hành phần mái", "5.2. Bên B khắc phục hư hỏng"),
        ("1. Điều chỉnh thời hạn hoàn thành", "Sửa đổi khoản 1 Điều 2"),
        ("2. Các nội dung khác", "Các nội dung khác của Hợp đồng giữ nguyên"),
    ],
)

LEASE = Dossier(
    "dossier-pruning-007", "dev",
    [[
        "HỢP ĐỒNG THUÊ VĂN PHÒNG",
        *DISCLAIMER,
        "Điều 1. Đối tượng thuê",
        "1.1. Bên A cho Bên B thuê diện tích văn phòng 250 m2 tại tầng 6 tòa nhà để làm trụ sở giao dịch.",
        "1.2. Bên B được sử dụng 04 chỗ đỗ xe ô tô tại tầng hầm của tòa nhà.",
        "1.3. Bên B không được cho bên thứ ba thuê lại diện tích nêu tại khoản 1.1.",
        "Điều 2. Giá thuê và thanh toán",
        "2.1. Giá thuê là 90.000.000 đồng mỗi tháng, chưa bao gồm phí dịch vụ.",
        "2.2. Phí dịch vụ quản lý tòa nhà là 12.000.000 đồng mỗi tháng.",
        "2.3. Bên B thanh toán tiền thuê theo quý, trước ngày 05 của tháng đầu mỗi quý.",
        "2.4. Bên B đặt cọc số tiền tương đương 03 tháng tiền thuê khi ký Hợp đồng.",
        "Trang 1",
    ], [
        "Điều 3. Sửa chữa và cải tạo",
        "3.1. Bên A chịu trách nhiệm sửa chữa kết cấu, hệ thống điện nước chung của tòa nhà.",
        "3.2. Bên B được cải tạo nội thất sau khi có văn bản chấp thuận của Bên A.",
        "3.3. Khi trả mặt bằng, Bên B khôi phục hiện trạng các hạng mục đã cải tạo theo khoản 3.2.",
        "Điều 4. Chấm dứt hợp đồng",
        "4.1. Mỗi bên có quyền đơn phương chấm dứt Hợp đồng khi báo trước cho bên kia ít nhất 90 ngày.",
        "4.2. Bên B đơn phương chấm dứt trái quy định tại khoản 4.1 thì mất toàn bộ tiền đặt cọc.",
        "4.3. Tranh chấp phát sinh được giải quyết tại Tòa án có thẩm quyền nơi có tòa nhà.",
        "Trang 2",
    ]],
    [[
        "PHỤ LỤC 01 - ĐIỀU CHỈNH GIÁ THUÊ",
        "Kèm theo Hợp đồng số HD-PR-007",
        *DISCLAIMER,
        "Các bên thống nhất điều chỉnh giá thuê như sau:",
        "1. Giá thuê từ năm thứ hai",
        "Giá thuê từ tháng thứ 13 là 95.000.000 đồng mỗi tháng, chưa bao gồm phí dịch vụ.",
        "Trang 1",
    ]],
    [
        ("1.1. Bên A cho Bên B thuê", "1.3. Bên B không được cho bên thứ ba"),
        ("2.1. Giá thuê là 90.000.000", "2.4. Bên B đặt cọc"),
        ("3.2. Bên B được cải tạo nội thất", "3.3. Khi trả mặt bằng"),
        ("4.1. Mỗi bên có quyền đơn phương", "4.2. Bên B đơn phương chấm dứt"),
        ("Các bên thống nhất điều chỉnh giá thuê", "1. Giá thuê từ năm thứ hai"),
        ("1. Giá thuê từ năm thứ hai", "Giá thuê từ tháng thứ 13"),
    ],
)

LOGISTICS = Dossier(
    "dossier-pruning-008", "dev",
    [[
        "HỢP ĐỒNG DỊCH VỤ VẬN CHUYỂN HÀNG HÓA",
        *DISCLAIMER,
        "Điều 1. Dịch vụ",
        "1.1. Bên B vận chuyển hàng hóa của Bên A từ kho Bình Dương đến các cửa hàng tại Hà Nội.",
        "1.2. Mỗi chuyến hàng có khối lượng không quá 10 tấn và được đóng gói theo tiêu chuẩn của Bên A.",
        "1.3. Bên B mua bảo hiểm hàng hóa cho từng chuyến với mức bảo hiểm bằng giá trị hàng.",
        "Điều 2. Thời gian giao nhận",
        "2.1. Bên B giao hàng trong vòng 72 giờ kể từ khi nhận hàng tại kho.",
        "2.2. Bên A ký xác nhận phiếu giao hàng ngay khi nhận đủ hàng tại cửa hàng.",
        "2.3. Hàng hóa giao chậm quá thời hạn tại khoản 2.1 được coi là vi phạm nghĩa vụ giao hàng.",
        "Điều 3. Cước phí",
        "3.1. Cước vận chuyển được tính theo bảng giá sau:",
        "a) 4.500.000 đồng cho mỗi chuyến dưới 05 tấn;",
        "b) 7.800.000 đồng cho mỗi chuyến từ 05 tấn đến 10 tấn.",
        "3.2. Bên A thanh toán cước của mỗi tháng trong vòng 10 ngày kể từ ngày nhận bảng kê.",
        "Trang 1",
    ], [
        "Điều 4. Trách nhiệm",
        "4.1. Bên B bồi thường toàn bộ giá trị hàng hóa bị mất mát, hư hỏng trong quá trình vận chuyển.",
        "4.2. Bên B giao chậm thì chịu phạt 2.000.000 đồng cho mỗi chuyến giao chậm.",
        "4.3. Mức phạt tại khoản 4.2 không áp dụng trong trường hợp bất khả kháng.",
        "4.4. Bên A cung cấp đầy đủ chứng từ hàng hóa trước khi Bên B nhận hàng.",
        "Trang 2",
    ]],
    [[
        "PHỤ LỤC 01 - BỔ SUNG TUYẾN",
        "Kèm theo Hợp đồng số HD-PR-008",
        *DISCLAIMER,
        "1. Bổ sung tuyến vận chuyển",
        "Bên B vận chuyển thêm tuyến từ kho Bình Dương đến các cửa hàng tại Hải Phòng.",
        "2. Cước tuyến bổ sung",
        "Cước tuyến Hải Phòng là 8.200.000 đồng cho mỗi chuyến từ 05 tấn đến 10 tấn.",
        "Trang 1",
    ]],
    [
        ("2.1. Bên B giao hàng trong vòng 72", "2.3. Hàng hóa giao chậm"),
        ("3.1. Cước vận chuyển được tính", "a) 4.500.000 đồng"),
        ("3.1. Cước vận chuyển được tính", "b) 7.800.000 đồng"),
        ("4.2. Bên B giao chậm thì chịu phạt", "4.3. Mức phạt tại khoản 4.2"),
        ("1. Bổ sung tuyến vận chuyển", "Bên B vận chuyển thêm tuyến"),
        ("2. Cước tuyến bổ sung", "Cước tuyến Hải Phòng"),
    ],
)

CONSULTING = Dossier(
    "dossier-pruning-009", "heldout",
    [[
        "HỢP ĐỒNG DỊCH VỤ TƯ VẤN THUẾ",
        *DISCLAIMER,
        "Điều 1. Nội dung tư vấn",
        "1.1. Bên B rà soát hồ sơ quyết toán thuế thu nhập doanh nghiệp năm 2025 của Bên A.",
        "1.2. Bên B lập báo cáo rủi ro thuế và đề xuất phương án xử lý.",
        "1.3. Báo cáo tại khoản 1.2 được bàn giao bằng văn bản và bản điện tử.",
        "1.4. Bên A cung cấp sổ sách kế toán và chứng từ trong vòng 05 ngày kể từ ngày ký.",
        "Điều 2. Phí dịch vụ",
        "2.1. Phí tư vấn trọn gói là 180.000.000 đồng, đã bao gồm thuế giá trị gia tăng.",
        "2.2. Phí tư vấn được thanh toán theo hai lần như sau:",
        "a) Lần 1: 40% phí tư vấn trong vòng 07 ngày kể từ ngày ký;",
        "b) Lần 2: 60% phí tư vấn trong vòng 07 ngày kể từ ngày bàn giao báo cáo.",
        "Trang 1",
    ], [
        "Điều 3. Bảo mật",
        "3.1. Bên B giữ bí mật mọi thông tin tài chính do Bên A cung cấp.",
        "3.2. Bên B chỉ sử dụng thông tin nêu tại khoản 3.1 cho mục đích thực hiện Hợp đồng.",
        "3.3. Bên A không công bố báo cáo của Bên B cho bên thứ ba khi chưa có đồng ý của Bên B.",
        "Điều 4. Trách nhiệm",
        "4.1. Bên B bồi thường thiệt hại do tư vấn sai quy định pháp luật thuế tại thời điểm tư vấn.",
        "4.2. Tổng mức bồi thường theo khoản 4.1 không vượt quá phí tư vấn đã nhận.",
        "4.3. Hợp đồng có hiệu lực từ ngày ký đến khi các bên hoàn thành nghĩa vụ.",
        "Trang 2",
    ]],
    [[
        "PHỤ LỤC 01 - MỞ RỘNG PHẠM VI",
        "Kèm theo Hợp đồng số HD-PR-009",
        *DISCLAIMER,
        "1. Bổ sung rà soát thuế nhà thầu",
        "Bên B rà soát thêm nghĩa vụ thuế nhà thầu nước ngoài năm 2025 của Bên A.",
        "2. Phí bổ sung",
        "Phí rà soát bổ sung là 40.000.000 đồng, thanh toán cùng lần 2.",
        "Trang 1",
    ]],
    [
        ("1.2. Bên B lập báo cáo rủi ro", "1.3. Báo cáo tại khoản 1.2"),
        ("2.2. Phí tư vấn được thanh toán", "a) Lần 1: 40%"),
        ("2.2. Phí tư vấn được thanh toán", "b) Lần 2: 60%"),
        ("3.1. Bên B giữ bí mật", "3.2. Bên B chỉ sử dụng thông tin"),
        ("4.1. Bên B bồi thường thiệt hại", "4.2. Tổng mức bồi thường"),
        ("1. Bổ sung rà soát thuế nhà thầu", "Bên B rà soát thêm nghĩa vụ"),
        ("2. Phí bổ sung", "Phí rà soát bổ sung"),
    ],
)

CATERING = Dossier(
    "dossier-pruning-010", "heldout",
    [[
        "HỢP ĐỒNG CUNG CẤP SUẤT ĂN CÔNG NGHIỆP",
        *DISCLAIMER,
        "Điều 1. Cung cấp suất ăn",
        "1.1. Bên B cung cấp suất ăn trưa cho khoảng 800 công nhân của Bên A vào các ngày làm việc.",
        "1.2. Thực đơn được xây dựng theo tuần và gửi Bên A trước thứ Sáu của tuần trước đó.",
        "1.3. Bên A thông báo số lượng suất ăn chính xác trước 09 giờ sáng hằng ngày.",
        "1.4. Số suất vượt quá thông báo tại khoản 1.3 được Bên B phục vụ trong khả năng của bếp.",
        "Điều 2. Vệ sinh an toàn thực phẩm",
        "2.1. Bên B lưu mẫu thức ăn của mỗi bữa trong 24 giờ theo quy định.",
        "2.2. Bên B định kỳ khám sức khỏe cho nhân viên nhà bếp 06 tháng một lần.",
        "2.3. Bên A có quyền kiểm tra bếp ăn bất kỳ lúc nào trong giờ hoạt động.",
        "Trang 1",
    ], [
        "Điều 3. Giá và thanh toán",
        "3.1. Đơn giá mỗi suất ăn là 32.000 đồng, đã bao gồm thuế giá trị gia tăng.",
        "3.2. Bên A thanh toán theo tháng như sau:",
        "a) Bên B gửi bảng tổng hợp số suất của tháng trước ngày 03 tháng kế tiếp;",
        "b) Bên A thanh toán trong vòng 10 ngày kể từ ngày nhận bảng tổng hợp và hóa đơn.",
        "Điều 4. Vi phạm",
        "4.1. Bên B để xảy ra ngộ độc thực phẩm thì chịu phạt 50.000.000 đồng cho mỗi vụ việc.",
        "4.2. Ngoài khoản phạt tại khoản 4.1, Bên B chi trả toàn bộ chi phí điều trị cho người bị ngộ độc.",
        "4.3. Mọi tranh chấp được giải quyết bằng thương lượng trước khi khởi kiện.",
        "Trang 2",
    ]],
    [[
        "PHỤ LỤC 01 - ĐIỀU CHỈNH ĐƠN GIÁ",
        "Kèm theo Hợp đồng số HD-PR-010",
        *DISCLAIMER,
        "1. Đơn giá áp dụng từ quý III",
        "Đơn giá mỗi suất ăn từ ngày 01 tháng 07 là 34.000 đồng, đã bao gồm thuế giá trị gia tăng.",
        "2. Hiệu lực",
        "Các nội dung khác của Hợp đồng không thay đổi.",
        "Trang 1",
    ]],
    [
        ("1.3. Bên A thông báo số lượng", "1.4. Số suất vượt quá thông báo"),
        ("3.2. Bên A thanh toán theo tháng", "a) Bên B gửi bảng tổng hợp"),
        ("3.2. Bên A thanh toán theo tháng", "b) Bên A thanh toán trong vòng 10"),
        ("4.1. Bên B để xảy ra ngộ độc", "4.2. Ngoài khoản phạt tại khoản 4.1"),
        ("1. Đơn giá áp dụng từ quý III", "Đơn giá mỗi suất ăn từ ngày 01"),
        ("2. Hiệu lực", "Các nội dung khác của Hợp đồng không thay đổi"),
    ],
)

DOSSIERS = (SOFTWARE, CONSTRUCTION, LEASE, LOGISTICS, CONSULTING, CATERING)
