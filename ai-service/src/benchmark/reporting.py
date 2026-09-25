from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from benchmark.metrics.statistics import bootstrap_ci, describe
from benchmark.schemas import PreparedDocument, read_json

METRICS = [
    "raw_cer",
    "normalized_cer",
    "raw_wer",
    "normalized_wer",
    "critical_field_accuracy",
    "table_detection_f1",
    "row_count_accuracy",
    "column_count_accuracy",
    "cell_text_accuracy",
    "table_continuation_accuracy",
    "latency_per_page_ms",
    "cost_per_page_usd",
]


def write_csv(path: Path, rows: list[dict]) -> None:
    columns = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _paired(rows: list[dict]) -> tuple[list[dict], list[str]]:
    providers = sorted({row["provider"] for row in rows})
    docs_by_group: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in rows:
        docs_by_group[(row["experiment"], row["provider"])].add(row["document_id"])
    paired_docs: set[str] | None = None
    for docs in docs_by_group.values():
        paired_docs = set(docs) if paired_docs is None else paired_docs & docs
    paired_docs = paired_docs or set()
    return [row for row in rows if row["document_id"] in paired_docs], providers


def _aggregate(rows: list[dict], keys: tuple[str, ...]) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        groups[tuple(row.get(key, "") for key in keys)].append(row)
    output = []
    for key, group in sorted(groups.items()):
        item = dict(zip(keys, key, strict=True))
        item["documents"] = len({row["document_id"] for row in group})
        item["pages"] = sum(int(row.get("page_count", 0)) for row in group)
        for metric in METRICS:
            values = [float(row[metric]) for row in group if row.get(metric) is not None]
            for stat, value in describe(values).items():
                item[f"{metric}_{stat}"] = value
            doc_values = {row["document_id"]: float(row[metric]) for row in group if row.get(metric) is not None}
            low, high = bootstrap_ci(doc_values)
            item[f"{metric}_ci_low"] = low
            item[f"{metric}_ci_high"] = high
        output.append(item)
    return output


def generate_report(
    data_dir: Path, artifacts_dir: Path, reports_dir: Path, config: dict | None = None
) -> dict:
    config = config or {}
    stats = config.get("statistics", {})
    iterations = int(stats.get("bootstrap_iterations", 1000))
    confidence = float(stats.get("confidence_level", 0.95))
    seed = int(stats.get("seed", 42))
    evaluation = read_json(reports_dir / "evaluation.json")
    documents = [PreparedDocument.model_validate(item) for item in read_json(data_dir / "prepared_manifest.json")]
    paired, providers = _paired(evaluation["by_document"])
    # `_aggregate` uses the documented defaults. Non-default settings are applied
    # below to every CI field so the report remains configuration-driven.
    summary = _aggregate(paired, ("provider", "experiment"))
    categories = []
    expanded = []
    for row in paired:
        cases = [case for case in str(row.get("test_cases", "")).split(",") if case] or ["uncategorized"]
        expanded.extend({**row, "category": case} for case in cases)
    categories = _aggregate(expanded, ("provider", "experiment", "category"))
    if (iterations, confidence, seed) != (1000, 0.95, 42):
        for collection in (summary, categories):
            for item in collection:
                source = [
                    row
                    for row in (paired if collection is summary else expanded)
                    if all(row.get(key) == item.get(key) for key in ("provider", "experiment"))
                    and (collection is summary or row.get("category") == item.get("category"))
                ]
                for metric in METRICS:
                    values = {row["document_id"]: float(row[metric]) for row in source if row.get(metric) is not None}
                    low, high = bootstrap_ci(values, iterations=iterations, confidence=confidence, seed=seed)
                    item[f"{metric}_ci_low"], item[f"{metric}_ci_high"] = low, high

    write_csv(reports_dir / "benchmark_summary.csv", summary)
    write_csv(reports_dir / "benchmark_by_document.csv", paired)
    write_csv(reports_dir / "benchmark_by_page.csv", evaluation["by_page"])
    write_csv(reports_dir / "benchmark_by_category.csv", categories)
    write_csv(reports_dir / "critical_fields.csv", evaluation["critical_fields"])
    write_csv(reports_dir / "failure_cases.csv", evaluation["failures"])

    status = read_json(artifacts_dir / "run_status.json") if (artifacts_dir / "run_status.json").exists() else []
    failed = [item for item in status if item.get("status") != "SUCCESS"]
    lines = [
        "# OCR Pilot Benchmark",
        "",
        "> Preliminary benchmark on the current labelled scan dataset; results are not representative of the full contract population.",
        "",
        "## 1. Objective",
        "",
        "Measure Mistral scan-only OCR on text, critical fields, tables, latency, cost, and difficult scan categories.",
        "",
        "## 2. Dataset",
        "",
        f"- Documents prepared: {len(documents)}",
        f"- Rendered/image pages: {sum(doc.page_count for doc in documents)}",
        f"- Paired documents used in raw/preprocessed comparison: {len({row['document_id'] for row in paired})}",
        "",
        "## 3. Scan Characteristics",
        "",
        ", ".join(sorted({case for doc in documents for case in doc.test_cases})) or "No categories annotated.",
        "",
        "## 4. OCR Provider",
        "",
        ", ".join(providers) or "No successful Mistral runs.",
        "",
        "## 5. Benchmark Protocol",
        "",
        "Every PDF page is rendered to a 300-DPI image. Mistral receives the immutable image for each experiment; raw and preprocessed runs use the same source pages. No PDF text layer is used.",
        "",
        "## 6. Metrics",
        "",
        "Raw/normalized CER and WER; exact/normalized critical fields; table detection, dimensions, cells and continuation; latency and configured cost. Confidence intervals use document-level bootstrap (1000 iterations, 95%, seed 42).",
        "",
        "## 7. Overall Results",
        "",
        "| Provider | Experiment | Docs | normalized CER mean [95% CI] | Critical fields | Table F1 |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in summary:
        cer = row.get("normalized_cer_mean")
        low, high = row.get("normalized_cer_ci_low"), row.get("normalized_cer_ci_high")
        cer_text = f"{cer:.4f} [{low:.4f}, {high:.4f}]" if None not in (cer, low, high) else "N/A"
        field = row.get("critical_field_accuracy_mean")
        table = row.get("table_detection_f1_mean")
        lines.append(f"| {row['provider']} | {row['experiment']} | {row['documents']} | {cer_text} | {field if field is not None else 'N/A'} | {table if table is not None else 'N/A'} |")
    lines += [
        "",
        "## 8. Results by Scan Type",
        "",
        "See `benchmark_by_category.csv`; every document contributes to each of its annotated categories.",
        "",
        "## 9. Critical Field Results",
        "",
        "See `critical_fields.csv`. Business-critical mismatches are copied to `failure_cases.csv` with CRITICAL severity.",
        "",
        "## 10. Table Results",
        "",
        "MVP evaluates table detection, row/column counts, cell text by coordinates, and annotated multi-page continuation.",
        "",
        "## 11. Latency & Cost",
        "",
        "Latency is measured per page and document. Cost is reported only when `price_per_page` is configured; missing pricing remains N/A.",
        "",
        "## 12. Failure Cases",
        "",
        f"Failure entries: {len(evaluation['failures'])}; Mistral run failures/skips: {len(failed)}. See `failure_cases.csv` and `artifacts/run_status.json`.",
        "",
        "## 13. Confidence Intervals",
        "",
        f"All summary metric intervals are bootstrap intervals sampled at document level, never character level ({iterations} iterations, confidence={confidence}, seed={seed}).",
        "",
        "## 14. Limitations",
        "",
        "This is a small pilot dataset. Table pairing is page/order based, Mistral pricing may be unconfigured, and ground truth quality depends on human review.",
        "",
        "## 15. Findings",
        "",
        "Use the paired raw/preprocessed results to decide whether preprocessing improves Mistral OCR on this dataset.",
    ]
    (reports_dir / "benchmark_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"summary": summary, "categories": categories, "paired_rows": paired}
