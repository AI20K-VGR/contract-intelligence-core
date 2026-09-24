from contract_ocr.infrastructure.metrics.ocr_metrics import OCRMetrics


def test_diacritic_stroke_d_and_denominator():
    metrics = OCRMetrics()
    result = metrics.text("ađ", "ád")
    assert result["diacritic_aligned_letters"] == 2
    assert result["diacritic_errors"] == 2
    assert metrics.text("đ", "d")["diacritic_error_rate"] == 1
    assert metrics.text("?", "d")["diacritic_error_rate"] is None
