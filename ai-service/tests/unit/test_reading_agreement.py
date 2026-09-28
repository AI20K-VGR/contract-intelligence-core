"""Real readings of page 3: mistral-ocr-2512 vs mistral-ocr-4-1."""

from contract_ocr.domain.reading_agreement import disputes, implausible, tokens

TRUTH_43 = (
    "4.3. Nghiệm thu căn cứ trên bộ mẫu hai bên thống nhất, biên bản kiểm tra và danh sách "
    "lỗi còn tồn tại tại thời điểm nghiệm thu."
)
READ_2512_43 = (
    "4.3. Nghiệm thu căn cứ trên bộ mẫu hai bên thống nhất, biên bản kiểm tra và danh sách "
    "lỗi còn tồn tại thì điểm nghiệm thu."
)
READ_41_43 = (
    "4.3. Nghiem thu can cu trén bô mau hai bèn thong nhát, biên bàn kiém tra và dans sách "
    "lói còn tón tãi tói thói diém nghiem thu."
)
READ_2512_41 = (
    "4.1. Kết quả bàn giao phải đảm bảo khả năng truy vết từ dữ liệu trích xuất về trang, "
    "dòng hoặc vùng nguồn tương ứng trên tài liệu."
)
READ_41_41 = (
    "4.1. Két qua bàn giao phai dam bao khà nang truy vét t ur du lieu trich xuát vê trang, "
    "dong hoac vùng nguôn tuong ung trèn tai lieu."
)


def test_word_substitution_by_the_text_reader_is_exposed_by_the_second_reading():
    found = disputes(tokens(READ_2512_43, 7), tokens(READ_41_43))
    assert len(found) == 1
    assert found[0].owners == {7}
    assert found[0].first == ("thì",)


def test_garbage_from_the_noisy_second_reader_is_not_a_dispute():
    # "t ur" for "từ", accent loss everywhere: all explained by the verifier's own noise
    assert disputes(tokens(READ_2512_41), tokens(READ_41_41)) == []


def test_identical_content_has_no_dispute():
    assert disputes(tokens(TRUTH_43), tokens(TRUTH_43)) == []


def test_digit_difference_is_always_a_dispute():
    assert disputes(tokens("giá 1.286.400.000 đồng"), tokens("giá 1.236.400.000 dong"))


def test_implausible():
    for word in ("t", "ur", "dans", "hàngh", "cαu", "uŋ", "lieuu", "Vietc"):
        assert implausible(word), word
    for word in ("thời", "tói", "thì", "TNHH", "2026", "A"):
        assert not implausible(word), word
