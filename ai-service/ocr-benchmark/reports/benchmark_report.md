# OCR Pilot Benchmark

> Preliminary benchmark on the current labelled scan dataset; results are not representative of the full contract population.

## 1. Objective

Measure Mistral scan-only OCR on text, critical fields, tables, latency, cost, and difficult scan categories.

## 2. Dataset

- Documents prepared: 3
- Rendered/image pages: 9
- Paired documents used in raw/preprocessed comparison: 3

## 3. Scan Characteristics

baseline_clean, stamp_over_table, table_interruption, table_no_header, table_no_stt

## 4. OCR Provider

mistral

## 5. Benchmark Protocol

Every PDF page is rendered to a 300-DPI image. Mistral receives the immutable image for each experiment; raw and preprocessed runs use the same source pages. No PDF text layer is used.

## 6. Metrics

Raw/normalized CER and WER; exact/normalized critical fields; table detection, dimensions, cells and continuation; latency and configured cost. Confidence intervals use document-level bootstrap (1000 iterations, 95%, seed 42).

## 7. Overall Results

| Provider | Experiment | Docs | normalized CER mean [95% CI] | Critical fields | Table F1 |
|---|---|---:|---:|---:|---:|
| mistral | raw | 3 | 0.0550 [0.0005, 0.1042] | 0.9444444444444445 | 0.7777777777777777 |

## 8. Results by Scan Type

See `benchmark_by_category.csv`; every document contributes to each of its annotated categories.

## 9. Critical Field Results

See `critical_fields.csv`. Business-critical mismatches are copied to `failure_cases.csv` with CRITICAL severity.

## 10. Table Results

MVP evaluates table detection, row/column counts, cell text by coordinates, and annotated multi-page continuation.

## 11. Latency & Cost

Latency is measured per page and document. Cost is reported only when `price_per_page` is configured; missing pricing remains N/A.

## 12. Failure Cases

Failure entries: 28; Mistral run failures/skips: 0. See `failure_cases.csv` and `artifacts/run_status.json`.

## 13. Confidence Intervals

All summary metric intervals are bootstrap intervals sampled at document level, never character level (1000 iterations, confidence=0.95, seed=42).

## 14. Limitations

This is a small pilot dataset. Table pairing is page/order based, Mistral pricing may be unconfigured, and ground truth quality depends on human review.

## 15. Findings

Use the paired raw/preprocessed results to decide whether preprocessing improves Mistral OCR on this dataset.
