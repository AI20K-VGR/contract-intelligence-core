import pytest

from app.pipeline.relation_markers import defined_term, has_amend_marker


@pytest.mark.parametrize(
    "text",
    [
        "Sửa đổi khoản 1 Điều 4 như sau",
        "Sửa đổi, bổ sung Điều 5 của Hợp đồng",
        "Bãi bỏ khoản 3 Điều 7",
        "Bổ sung điểm d vào khoản 1 Điều 6",
        "Thay thế Phụ lục 01 bằng Phụ lục này",
        "Đơn giá tại Điều 4 được điều chỉnh thành 16.200.000 đồng/tấn",
        "Phụ lục 1: sửa A thành 110000 VND từ 01/07.",
        "Thay đổi đơn giá thép D10 thành 16.200.000 đồng/tấn",
        "Điều 9 không còn hiệu lực kể từ ngày ký Phụ lục này",
        "sua doi khoan 2 dieu 3",
        "This Annex amends Article 4",
    ],
)
def test_amend_marker_detects_explicit_operations(text):
    assert has_amend_marker(text)


@pytest.mark.parametrize(
    "text",
    [
        "Bên Bán có trách nhiệm sửa chữa hàng lỗi.",
        "Đơn giá được điều chỉnh theo CPI hằng năm.",
        "Bên B hoàn thành công trình đúng tiến độ.",
        "Bên B bổ sung hồ sơ thanh toán trong 05 ngày.",
        "Hai bên thống nhất thay đổi người đại diện liên hệ.",
    ],
)
def test_amend_marker_ignores_ordinary_wording(text):
    assert not has_amend_marker(text)


@pytest.mark.parametrize(
    ("text", "term"),
    [
        ('"Hàng hóa" có nghĩa là thép D10 theo Phụ lục 01.', "Hàng hóa"),
        ("“Bên Mua” được hiểu là Công ty A.", "Bên Mua"),
        ("Trong Hợp đồng này, Ngày làm việc có nghĩa là các ngày trừ thứ Bảy, Chủ nhật.", "Ngày làm việc"),
        ('"Goods" shall mean steel products.', "Goods"),
    ],
)
def test_defined_term_captures_the_term_not_the_definition(text, term):
    assert defined_term(text) == term


def test_defined_term_none_without_definition():
    assert defined_term("Bên Bán giao hàng tại kho Bên Mua.") is None
