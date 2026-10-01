from evals.value_normalize import normalize_value


def test_value_formats() -> None:
    assert normalize_value("1.000.000 đồng") == normalize_value("1000000 VND")
    assert normalize_value("ngày 02 tháng 03 năm 2024") == normalize_value("02/03/2024")
    assert normalize_value("12,5%") == normalize_value("12.5 %")
    assert normalize_value("Số 08/2024/HĐ") == normalize_value("08/2024/HĐ")
    assert normalize_value("Công ty Ánh Dương") == normalize_value("Công ty Ánh Dương")
    assert normalize_value("mười hai triệu đồng") != normalize_value("12.000.000 đồng")

