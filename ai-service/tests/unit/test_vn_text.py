"""Real readings of the same page: mistral-ocr-4 (garbled) vs mistral-ocr-2512 (correct)."""

import pytest

from contract_ocr.domain.vn_text import (
    diacritic_density,
    is_vn_syllable,
    line_issues,
    missing_vowel_modifier,
    skeleton,
)

GARBLED = [
    "4.1. Két qua bàn giao phai dam bao khà nang truy vét t ur du lieu trich xuát vê trang, "
    "dong hoac vùng nguôn tuong ung trèn tai lieu.",
    "4.3. Nghiem thu can cu trén bô mau hai bèn thong nhát, biên bàn kiém tra và dans sách "
    "lói còn tón tãi tói thói diém nghiem thu.",
    "5.3. Khong yèu cαu Bên B thuc hiên cac hàngh vi trái phap luat hoac sù dung dū lièu "
    "ngoài muc dích cαu hop dong.",
    "4.1. Két qua bàn giao phai dam bao khà nang truy vét t ur du lièu trich xuát vê trang, "
    "dong hoac vùng nguón tuong uŋ trèn tαi lièu.",
]
CORRECT = [
    "4.1. Kết quả bàn giao phải đảm bảo khả năng truy vết từ dữ liệu trích xuất về trang, "
    "dòng hoặc vùng nguồn tương ứng trên tài liệu.",
    "4.3. Nghiệm thu căn cứ trên bộ mẫu hai bên thống nhất, biên bản kiểm tra và danh sách "
    "lỗi còn tồn tại tại thời điểm nghiệm thu.",
    "ĐIỀU 4. YÊU CẦU CHẤT LƯỢNG VÀ NGHIỆM THU",
    "3.1. Tổng giá trị hợp đồng tạm tính là 1.286.400.000 đồng (Bằng chữ: Một tỷ hai trăm "
    "tám mươi sáu triệu bốn trăm nghìn đồng).",
    "Bên A: Công ty TNHH ABC, MST: 0101234567-001, email: legal@abc.vn",
    "This Agreement shall be governed by the laws of Vietnam.",
    "25/2026/HĐDV-MH-TT",
]


@pytest.mark.parametrize("text", GARBLED)
def test_garbled_mistral_ocr4_readings_are_flagged(text):
    assert line_issues(text)


@pytest.mark.parametrize("text", CORRECT)
def test_correct_readings_are_not_flagged(text):
    assert line_issues(text) == []


def test_skeleton_ignores_accents_so_two_readings_can_be_compared():
    assert skeleton(CORRECT[0]) == skeleton(
        "4.1. Ket qua ban giao phai dam bao kha nang truy vet tu du lieu trich xuat ve trang, "
        "dong hoac vung nguon tuong ung tren tai lieu."
    )


def test_density_separates_garbled_from_correct():
    assert diacritic_density(GARBLED[0]) < 0.5 < diacritic_density(CORRECT[0])


def test_short_or_non_vietnamese_text_has_no_density_verdict():
    assert diacritic_density("Trang 3/12") is None
    assert diacritic_density(CORRECT[5]) is None


def test_diphthong_without_circumflex_or_horn_is_impossible_spelling():
    for word in ("kiém", "nghiem", "tuong", "lieu", "nguon", "thuoc"):
        assert missing_vowel_modifier(word), word
    for word in ("kiểm", "nghiệm", "tương", "liệu", "nguồn", "thuộc", "quốc", "chia", "người", "của"):
        assert not missing_vowel_modifier(word), word


def test_syllable_shapes():
    for word in ("nghiêng", "trường", "khuya", "quyết", "gì", "người", "đồng"):
        assert is_vn_syllable(word), word
    for word in ("dans", "ur", "watermark"):
        assert not is_vn_syllable(word), word
