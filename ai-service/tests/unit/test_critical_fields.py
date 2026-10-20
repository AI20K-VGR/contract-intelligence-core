from contract_ocr.domain.critical_fields import amount_words_mismatch, critical_tokens

CORRECT = (
    "3.1. Tổng giá trị hợp đồng tạm tính là 1.286.400.000 đồng (Bằng chữ: Một tỷ hai trăm "
    "tám mươi sáu triệu bốn trăm nghìn đồng), đã bao gồm các chi phí."
)
# mistral-ocr-4's actual reading of the same line: accents lost, digits intact.
OCR4 = (
    "3.1. Tóng giá tri hop dong tam tinh la 1.286.400.000 dong (Bang chu: Môt tý hai tram "
    "tám mươi sáu trièu bón tram nghin dong), dā bao gôm cac chi phi."
)


def test_money_token_survives_lost_accents_so_readers_can_be_compared():
    assert critical_tokens(CORRECT) == critical_tokens(OCR4)
    assert critical_tokens(CORRECT)["money:1286400000"] == 1


def test_one_wrong_digit_is_a_different_token():
    assert critical_tokens(CORRECT) != critical_tokens(CORRECT.replace("286", "236"))


def test_other_critical_kinds():
    tokens = critical_tokens(
        "Bên A thanh toán 30% trong vòng 07 ngày kể từ ngày 15 tháng 3 năm 2026, "
        "hạn chót 01/04/2026. MST: 0101234567-001. Số: 25/2026/HĐDV-MH-TT"
    )
    assert tokens["percent:30"] == 1
    assert tokens["date:15/03/2026"] == 1
    assert tokens["date:01/04/2026"] == 1
    assert tokens["id:0101234567-001"] == 1
    assert tokens["contract:25/2026/hddv-mh-tt"] == 1


def test_plain_prose_has_no_critical_tokens():
    assert not critical_tokens("4.1. Kết quả bàn giao phải đảm bảo khả năng truy vết.")


def test_amount_in_words_agreeing_with_digits_is_consistent():
    assert not amount_words_mismatch(CORRECT)


def test_amount_in_words_disagreeing_with_digits_is_flagged():
    assert amount_words_mismatch(CORRECT.replace("1.286.400.000", "1.236.400.000"))


def test_unparseable_words_are_not_treated_as_a_mismatch():
    assert not amount_words_mismatch(OCR4)
