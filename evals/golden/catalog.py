"""Synthetic question catalog; labels are derived only from ``spec`` rules."""

from __future__ import annotations

from dataclasses import dataclass

from evals.golden.spec import ExpectedState, MutationSpec, expected_state_for


@dataclass(frozen=True, slots=True)
class QuestionSpec:
    question_id: str
    text: str
    kind: str
    mutations: tuple[MutationSpec, ...] = ()

    @property
    def expected_state(self) -> ExpectedState:
        return expected_state_for(self.kind, self.mutations)

    @property
    def category(self) -> str | None:
        return {
            ExpectedState.ANSWERED: "answerable",
            ExpectedState.INSUFFICIENT_EVIDENCE: "not_in_document",
            ExpectedState.BLOCKED: "permission",
        }.get(self.expected_state)


@dataclass(frozen=True, slots=True)
class ContractSpec:
    contract_id: str
    title: str
    features: tuple[str, ...]
    page_count: int
    questions: tuple[QuestionSpec, ...]


_CONTRACTS = (
    ("G01", "Dịch vụ bảo trì", ("phụ lục sửa giá", "xung đột thân và phụ lục"), 8),
    ("G02", "Mua bán thiết bị", ("bảng hàng hóa", "đơn giá và số lượng"), 12),
    ("G03", "Thuê văn phòng", ("hai phụ lục", "thời hạn và tiền thuê"), 14),
    ("G04", "Dịch vụ SaaS", ("SLA phần trăm", "mức phạt phần trăm"), 9),
    ("G05", "Thi công công trình", ("khối lượng nhiều trang", "năm phụ lục", "điều khoản vắt trang"), 56),
    ("G06", "Vận chuyển", ("phụ lục được dẫn chiếu nhưng thiếu", "lịch giao hàng"), 7),
    ("G07", "Tư vấn", ("trùng tên khác mã số thuế", "định danh bên ký"), 6),
    ("G08", "Dịch vụ OCR", ("bản nhiều lỗi nhận dạng", "số tiền và xuống dòng"), 10),
)

_QUESTION_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("lookup", ()),
    ("clause_lookup", ()),
    ("lookup", ()),
    ("comparison", ("incomparable_quantities",)),
    ("lookup", ("body_annex_conflict",)),
    ("lookup", ("duplicate_name_different_tax_id",)),
    ("clause_lookup", ("overlapping_amendment",)),
    ("lookup", ("missing_annex",)),
    ("lookup", ("absent_information",)),
    ("broad", ()),
    ("comparison", ("non_conflicting_term",)),
    ("clause_lookup", ()),
)

_QUESTION_FORMS: dict[str, tuple[str, ...]] = {
    "G01": (
        "Biểu phí bảo trì quy định mức {feature} là bao nhiêu?",
        "Từ thời điểm nào điều khoản {feature} bắt đầu áp dụng?",
        "Bên nào phải thực hiện phần việc về {feature}?",
        "{feature} và {subject} được đo bằng hai đại lượng khác loại phải không?",
        "Khi thân hợp đồng khác phụ lục, mức {feature} nào đang được ghi nhận?",
        "Tên bên bảo trì xuất hiện hai lần; mã số thuế gắn với {feature} là mã nào?",
        "Các lần sửa điều khoản {feature} có chồng lấn thời gian hiệu lực không?",
        "Phụ lục được viện dẫn để xác định {feature} hiện ở đâu?",
        "Có ghi rõ {feature} khi đối chiếu với {subject} không?",
        "Tóm tắt mọi nghĩa vụ, ngoại lệ và mốc liên quan tới {feature}.",
        "Có thể đặt {feature} cạnh {subject} để so sánh trên cùng cơ sở không?",
        "Điều khoản nào xác lập {feature} trước khi phần sửa đổi có hiệu lực?",
    ),
    "G02": (
        "Bảng đặt hàng ghi đơn giá của {feature} ở mức nào?",
        "Điều khoản nào xác định ngày giao {feature}?",
        "Ai chịu trách nhiệm kiểm đếm {feature} khi bàn giao?",
        "Số lượng {feature} có cùng đơn vị đo với {subject} để so sánh không?",
        "Nếu phụ lục hàng hóa và phần chính lệch nhau, giá {feature} nào được nêu?",
        "Hai nhà cung cấp trùng tên; mã số thuế của bên giao {feature} là gì?",
        "Các lần điều chỉnh đơn hàng {feature} có hiệu lực trùng nhau không?",
        "Tài liệu được dẫn để xác nhận cấu hình {feature} có được đính kèm không?",
        "Hợp đồng có nói rõ {feature} trong tương quan với {subject} không?",
        "Tổng hợp toàn bộ điều kiện đặt hàng, giao nhận và ngoại lệ của {feature}.",
        "{feature} với {subject} có cùng cơ sở để lập bảng đối chiếu không?",
        "Căn cứ nào quyết định thông số {feature} ở đợt giao hàng này?",
    ),
    "G03": (
        "Tiền thuê ghi cho {feature} là bao nhiêu mỗi kỳ?",
        "Ngày bắt đầu tính {feature} được ghi tại điều khoản nào?",
        "Bên nào có nghĩa vụ duy trì {feature} trong thời hạn thuê?",
        "{feature} và {subject} có phải là hai loại đại lượng không thể quy đổi không?",
        "Nếu phụ lục và hợp đồng chính nêu giá khác nhau, giá {feature} hiện là bao nhiêu?",
        "Có hai đơn vị cùng tên; mã số thuế của chủ thể gắn với {feature} là gì?",
        "Các phụ lục sửa kỳ hạn {feature} có khoảng thời gian hiệu lực giao nhau không?",
        "Phụ lục được nhắc để mô tả {feature} có nằm trong bộ hồ sơ không?",
        "Nội dung về {feature} có được nêu khi xét cùng {subject} không?",
        "Khái quát các quyền, nghĩa vụ và trường hợp ngoại lệ liên quan đến {feature}.",
        "{feature} và {subject} có thể so sánh trực tiếp theo một thước đo không?",
        "Điều khoản nào ấn định {feature} cho kỳ thuê đang xét?",
    ),
    "G04": (
        "Mức cam kết ghi cho {feature} được tính là bao nhiêu phần trăm?",
        "Thời đoạn đo {feature} được quy định trong mục nào?",
        "Ai phải khắc phục khi chỉ số {feature} không đạt?",
        "Tỷ lệ {feature} có thể đối chiếu với {subject} nếu chúng đo hai loại đại lượng khác nhau không?",
        "Phần SLA và phụ lục có nêu hai mức khác nhau cho {feature}; mức nào cần được xem xét?",
        "Tên nhà cung cấp lặp lại; mã số thuế gắn với cam kết {feature} là mã nào?",
        "Các phiên bản sửa ngưỡng {feature} có thời gian áp dụng bị chồng nhau không?",
        "Phụ lục mô tả cách tính {feature} được dẫn chiếu nhưng có trong hồ sơ không?",
        "Có dữ liệu về {feature} để đối chiếu với {subject} không?",
        "Tóm lược các cam kết dịch vụ, cách đo và ngoại lệ áp dụng cho {feature}.",
        "{feature} và {subject} có cùng loại chỉ số để đem ra so sánh không?",
        "Mục nào xác định ngưỡng {feature} cho kỳ báo cáo này?",
    ),
    "G05": (
        "Bảng khối lượng phân trang ghi bao nhiêu cho {feature}?",
        "Điều khoản nối sang trang kế tiếp xác định {feature} từ mốc nào?",
        "Ai xác nhận khối lượng {feature} sau nghiệm thu?",
        "Khối lượng {feature} và {subject} có cùng đơn vị để so sánh trực tiếp không?",
        "Nếu bản chính và phụ lục khối lượng không thống nhất, con số {feature} nào cần rà soát?",
        "Tên nhà thầu bị lặp; mã số thuế của bên phụ trách {feature} là gì?",
        "Các phụ lục điều chỉnh hạng mục {feature} có hiệu lực đồng thời không?",
        "Phụ lục được dẫn để nghiệm thu {feature} có trong bộ hồ sơ nhiều phần không?",
        "Hợp đồng có nêu {feature} khi xét cùng {subject} không?",
        "Tóm lược các bước nghiệm thu, thanh toán và ngoại lệ của {feature}.",
        "{feature} có cùng cơ sở đo với {subject} để so sánh khối lượng không?",
        "Điều khoản nào điều chỉnh {feature} tại ranh giới giữa hai trang?",
    ),
    "G06": (
        "Lịch vận chuyển ghi thời lượng cho {feature} là bao lâu?",
        "Mốc nhận {feature} được xác định ở phần nào?",
        "Bên nào thu xếp việc bàn giao {feature}?",
        "{feature} và {subject} có phải hai đại lượng không cùng loại không?",
        "Nếu nội dung chính và phụ lục dẫn chiếu khác nhau, thời điểm {feature} nào được ghi?",
        "Có các chủ thể trùng tên; mã số thuế của bên nhận {feature} là gì?",
        "Những lần sửa lịch giao {feature} có khoảng hiệu lực trùng nhau không?",
        "Phụ lục được viện dẫn để xác định tuyến {feature} có được cung cấp không?",
        "Thông tin {feature} có xuất hiện bên cạnh điều kiện {subject} không?",
        "Tóm lược các cam kết giao nhận và trường hợp ngoại lệ áp dụng cho {feature}.",
        "Có cơ sở đo chung để đối chiếu {feature} với {subject} không?",
        "Điều khoản nào nêu mốc thực hiện {feature} của chuyến hàng này?",
    ),
    "G07": (
        "Phí tư vấn cho phần việc {feature} được ghi ở mức nào?",
        "Điều khoản nào đặt thời hạn hoàn thành {feature}?",
        "Ai là người chịu trách nhiệm cung cấp {feature}?",
        "{feature} với {subject} có thuộc hai nhóm đại lượng khác nhau không?",
        "Khi phần chính và phụ lục ghi khác, khoản phí {feature} nào cần xác minh?",
        "Hai bên có tên gần giống; mã số thuế của chủ thể thực hiện {feature} là gì?",
        "Các văn bản sửa phạm vi {feature} có thời gian áp dụng bị giao nhau không?",
        "Phụ lục được dẫn làm căn cứ cho {feature} có nằm trong hồ sơ ký không?",
        "Có nội dung về {feature} khi so cùng {subject} trong hợp đồng không?",
        "Nêu khái quát phạm vi, sản phẩm bàn giao và ngoại lệ của {feature}.",
        "{feature} và {subject} có cùng đơn vị để so sánh một cách trực tiếp không?",
        "Điều khoản nào quy định cách nghiệm thu {feature}?",
    ),
    "G08": (
        "Dòng OCR nhận dạng được mức {feature} là bao nhiêu?",
        "Mốc thời gian của {feature} nằm trong điều khoản nào?",
        "Bên nào thực hiện {feature} theo nội dung đã nhận dạng?",
        "Hai số liệu {feature} và {subject} có dùng các loại đơn vị khác nhau không?",
        "Bản nhận dạng phần chính và phụ lục lệch nhau về {feature}; giá trị nào cần rà soát?",
        "Tên đơn vị bị đọc lặp; mã số thuế gắn với {feature} là chuỗi nào?",
        "Các phiên bản nhận dạng điều khoản {feature} có thời gian sửa đổi chồng lấn không?",
        "Tài liệu được nhắc tới để xác nhận {feature} có được tải kèm không?",
        "Bản OCR có ghi {feature} khi đối chiếu với {subject} không?",
        "Tóm tắt các cam kết, mốc và trường hợp ngoại lệ liên quan tới {feature}.",
        "Có thể đối chiếu {feature} và {subject} theo cùng một đại lượng không?",
        "Đoạn nào quy định {feature} sau khi làm rõ chỗ xuống dòng?",
    ),
}


def _make_questions(contract_id: str, features: tuple[str, ...]) -> tuple[QuestionSpec, ...]:
    questions = []
    for index, ((kind, mutations), template) in enumerate(
        zip(_QUESTION_RULES, _QUESTION_FORMS[contract_id], strict=True), start=1
    ):
        feature = features[(index - 1) % len(features)]
        subject = features[index % len(features)]
        questions.append(
            QuestionSpec(
                question_id=f"{contract_id}-Q{index:02d}",
                text=template.format(feature=feature, subject=subject),
                kind=kind,
                mutations=tuple(MutationSpec(kind) for kind in mutations),
            )
        )
    return tuple(questions)


CONTRACTS = tuple(
    ContractSpec(
        contract_id=contract_id,
        title=title,
        features=features,
        page_count=page_count,
        questions=_make_questions(contract_id, features),
    )
    for contract_id, title, features, page_count in _CONTRACTS
)
