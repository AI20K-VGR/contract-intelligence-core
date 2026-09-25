from benchmark.metrics.fields import (
    evaluate_fields,
    normalize_contract_number,
    normalize_date,
    normalize_money,
    normalize_tax_code,
)
from benchmark.metrics.statistics import bootstrap_ci, describe
from benchmark.metrics.tables import evaluate_tables
from benchmark.metrics.text import evaluate_text
from benchmark.schemas import GroundTruthField, GroundTruthTable, OCRTable


def test_cer_wer_raw_and_normalized() -> None:
    metrics = evaluate_text("Hợp đồng  01", "hợp đồng 01")
    assert metrics["raw_cer"] > 0
    assert metrics["normalized_cer"] == 0
    assert metrics["normalized_wer"] == 0


def test_field_normalizers_cover_contract_values() -> None:
    assert normalize_money("1.000.000 VNĐ") == "1000000"
    assert normalize_date("25/09/2026") == "2026-09-25"
    assert normalize_contract_number(" HĐ - 01/2026 ") == "hđ-01/2026"
    assert normalize_tax_code("0101-234 567") == "0101234567"


def test_critical_fields_exact_and_normalized() -> None:
    fields = [
        GroundTruthField(
            field_type="total_amount", raw_value="1.000.000 VNĐ", normalized_value="1000000"
        ),
        GroundTruthField(
            field_type="contract_number", raw_value="HĐ-01/2026", normalized_value="hđ-01/2026"
        ),
    ]
    aggregate, rows = evaluate_fields(fields, "Số HĐ-01/2026; giá trị 1,000,000 VND")
    assert aggregate["critical_field_exact_accuracy"] == 0.5
    assert aggregate["critical_field_accuracy"] == 1
    assert all(row["normalized_match"] for row in rows)


def test_table_metrics_include_cells_and_continuation() -> None:
    expected = [
        GroundTruthTable(
            table_id="T1",
            pages=[1, 2],
            is_multi_page=True,
            rows=[["STT", "Tên"], ["1", "Bút"]],
        )
    ]
    predicted = [
        OCRTable(
            table_id="P1",
            pages=[1, 2],
            is_multi_page=True,
            rows=[["STT", "Tên"], ["1", "Bút"]],
        )
    ]
    result = evaluate_tables(expected, predicted)
    assert result["table_detection_f1"] == 1
    assert result["cell_text_accuracy"] == 1
    assert result["table_continuation_accuracy"] == 1


def test_statistics_and_document_bootstrap_are_deterministic() -> None:
    stats = describe([1, 2, 3])
    assert stats["mean"] == 2
    assert stats["p95"] >= stats["p90"]
    first = bootstrap_ci({"A": 0.1, "B": 0.2, "C": 0.3}, iterations=100, seed=42)
    second = bootstrap_ci({"A": 0.1, "B": 0.2, "C": 0.3}, iterations=100, seed=42)
    assert first == second
