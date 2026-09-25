from pathlib import Path

from benchmark.reporting import generate_report
from benchmark.schemas import write_json


def test_generates_all_csvs_and_markdown_from_paired_sample(tmp_path: Path) -> None:
    data, artifacts, reports = tmp_path / "data", tmp_path / "artifacts", tmp_path / "reports"
    write_json(
        data / "prepared_manifest.json",
        [
            {
                "document_id": "DOC-1",
                "file_name": "scan.pdf",
                "source_path": "scan.pdf",
                "page_count": 1,
                "language": ["vi"],
                "source_type": "scan",
                "scan_quality": "clean",
                "test_cases": ["clean_scan", "normal_table"],
                "pages": [
                    {
                        "page_number": 1,
                        "image_path": "page.png",
                        "width": 100,
                        "height": 100,
                        "dpi": 300,
                    }
                ],
            }
        ],
    )
    document_rows = []
    for experiment, cer in (("raw", 0.01), ("preprocessed", 0.02)):
        document_rows.append(
            {
                "document_id": "DOC-1",
                "provider": "mistral",
                "model": "mistral-ocr-4",
                "experiment": experiment,
                "page_count": 1,
                "scan_quality": "clean",
                "test_cases": "clean_scan,normal_table",
                "raw_cer": cer,
                "normalized_cer": cer,
                "raw_wer": cer,
                "normalized_wer": cer,
                "critical_field_accuracy": 1.0,
                "table_detection_f1": 1.0,
                "row_count_accuracy": 1.0,
                "column_count_accuracy": 1.0,
                "cell_text_accuracy": 1.0,
                "table_continuation_accuracy": 1.0,
                "latency_per_page_ms": 100.0,
                "cost_per_page_usd": 0.001,
            }
        )
    write_json(
        reports / "evaluation.json",
        {"by_page": [], "by_document": document_rows, "critical_fields": [], "failures": []},
    )
    write_json(artifacts / "run_status.json", [])

    output = generate_report(data, artifacts, reports, {})

    assert len(output["paired_rows"]) == 2
    for filename in (
        "benchmark_summary.csv",
        "benchmark_by_document.csv",
        "benchmark_by_page.csv",
        "benchmark_by_category.csv",
        "critical_fields.csv",
        "failure_cases.csv",
        "benchmark_report.md",
    ):
        assert (reports / filename).exists()
    report = (reports / "benchmark_report.md").read_text(encoding="utf-8")
    assert "## 15. Findings" in report
    assert "raw/preprocessed" in report
