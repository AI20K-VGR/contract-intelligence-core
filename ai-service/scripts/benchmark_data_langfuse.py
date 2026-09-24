"""Benchmark every PDF in a directory and emit local Langfuse-ready reports.

The OCR pipeline decides page-by-page whether native extraction is sufficient.
Only scanned pages invoke the configured OCR provider. Reports contain filenames
and aggregate metrics locally; Langfuse continues to receive privacy-safe
metadata from the application's observability layer.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from contract_ocr.application.use_cases.classify_pdf import PdfPageClassifier
from contract_ocr.infrastructure.backend_ocr_job import (
    BackendOcrJobRequest,
    get_backend_job,
    new_backend_job,
    run_backend_ocr,
)
from contract_ocr.infrastructure.observability import flush_langfuse, get_langfuse
from contract_ocr.infrastructure.pdf.pymupdf_extractor import PyMuPDFExtractor

MISTRAL_OCR_USD_PER_PAGE = 4.0 / 1000.0


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _pdf_inventory(path: Path) -> tuple[bytes, str, int, int, int]:
    content = path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    extractor = PyMuPDFExtractor()
    classifier = PdfPageClassifier()
    with extractor.open(path) as pdf:
        page_count = pdf.page_count
        evidence = [
            classifier.classify(index + 1, *extractor.evidence(page))
            for index, page in enumerate(pdf)
        ]
    native_pages = sum(item.usable_text for item in evidence)
    ocr_pages = sum(item.requires_ocr_regions for item in evidence)
    return content, digest, page_count, native_pages, ocr_pages


def _write_reports(rows: list[dict[str, Any]], output_dir: Path, run_id: str) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"langfuse-data-raw-benchmark-{run_id}.json"
    csv_path = output_dir / f"langfuse-data-raw-benchmark-{run_id}.csv"
    markdown_path = output_dir / f"langfuse-data-raw-benchmark-{run_id}.md"

    successful = [row for row in rows if row["status"] == "completed"]
    latencies = [float(row["latency_seconds"]) for row in successful]
    summary = {
        "file_count": len(rows),
        "successful_files": len(successful),
        "failed_files": len(rows) - len(successful),
        "total_pages": sum(int(row["page_count"]) for row in rows),
        "native_pages": sum(int(row["native_pages"]) for row in rows),
        "scanned_pages": sum(int(row["scanned_pages"]) for row in rows),
        "total_wall_seconds": round(sum(float(row["latency_seconds"]) for row in rows), 3),
        "average_file_latency_seconds": round(statistics.mean(latencies), 3)
        if latencies
        else 0.0,
        "p50_file_latency_seconds": round(_percentile(latencies, 0.50), 3),
        "p95_file_latency_seconds": round(_percentile(latencies, 0.95), 3),
        "max_file_latency_seconds": round(max(latencies), 3) if latencies else 0.0,
        "estimated_mistral_cost_usd": round(
            sum(float(row["estimated_cost_usd"]) for row in rows), 6
        ),
        "mistral_price_usd_per_page": MISTRAL_OCR_USD_PER_PAGE,
    }
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": summary,
        "files": rows,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    fieldnames = list(rows[0]) if rows else []
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Báo cáo benchmark OCR và Langfuse",
        "",
        f"- Thời điểm tạo (UTC): `{payload['generated_at']}`",
        f"- Số file: **{summary['file_count']}**",
        f"- Thành công / thất bại: **{summary['successful_files']} / {summary['failed_files']}**",
        f"- Tổng số trang: **{summary['total_pages']}**",
        f"- Trang có text native / trang cần OCR: **{summary['native_pages']} / "
        f"{summary['scanned_pages']}**",
        f"- Tổng thời gian tuần tự: **{summary['total_wall_seconds']:.3f} giây**",
        f"- Độ trễ file trung bình: **{summary['average_file_latency_seconds']:.3f} giây**",
        f"- P50 / P95 / Max: **{summary['p50_file_latency_seconds']:.3f} / "
        f"{summary['p95_file_latency_seconds']:.3f} / {summary['max_file_latency_seconds']:.3f} giây**",
        f"- Chi phí Mistral ước tính: **${summary['estimated_mistral_cost_usd']:.6f} USD**",
        "",
        "> Chi phí dùng đơn giá Mistral OCR 4 là $4/1.000 trang. Langfuse hiện chưa "
        "suy luận được cost cho alias `mistral-ocr-4`; xem cột trace để đối chiếu từng lần chạy.",
        "",
        "| # | File | Trang | Native | Scan | Trạng thái | Độ trễ (s) | Chi phí USD | Trace |",
        "|---:|---|---:|---:|---:|---|---:|---:|---|",
    ]
    for index, row in enumerate(rows, start=1):
        filename = str(row["file"]).replace("|", "\\|")
        trace = f"[mở]({row['trace_url']})" if row.get("trace_url") else "-"
        lines.append(
            f"| {index} | `{filename}` | {row['page_count']} | {row['native_pages']} | "
            f"{row['scanned_pages']} | {row['status']} | {row['latency_seconds']:.3f} | "
            f"{row['estimated_cost_usd']:.6f} | {trace} |"
        )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "json": str(json_path.resolve()),
        "csv": str(csv_path.resolve()),
        "markdown": str(markdown_path.resolve()),
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--output-dir", type=Path, default=Path("../output/reports"))
    parser.add_argument("--engine", choices=["pymupdf", "mistral"], default="mistral")
    args = parser.parse_args()

    paths = sorted(args.input_dir.rglob("*.pdf"))
    if not paths:
        raise SystemExit(f"No PDF files found under {args.input_dir}")

    run_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    client = get_langfuse()
    rows: list[dict[str, Any]] = []
    batch_started = time.perf_counter()

    for index, source in enumerate(paths, start=1):
        _content, digest, page_count, native_pages, scanned_pages = _pdf_inventory(source)
        request = BackendOcrJobRequest(
            task_id=index,
            attempt_id=1,
            tenant_id="local-benchmark",
            document_id=f"benchmark-{run_id}-{index:03d}-{digest[:10]}",
            source_blob_get_url=source.resolve().as_uri(),
            source_sha256=digest,
            pages_to_process=list(range(1, page_count + 1)),
            render_target={},
            options={
                "engine": args.engine,
                "dpi": 150,
                "document_role": "contract",
                "filename": "contract.pdf",
            },
        )
        job_id, _ = new_backend_job("ocr")
        trace_seed = f"benchmark-{run_id}-{index:03d}-{digest[:12]}"
        started = time.perf_counter()
        try:
            run_backend_ocr(job_id, request, trace_seed=trace_seed)
            job = get_backend_job(job_id) or {}
            status = str(job.get("status") or "unknown")
            error = str(job.get("error") or "")
        except Exception as exc:  # keep the batch running and report the failure
            status = "failed"
            error = f"{type(exc).__name__}: {exc}"
        latency = time.perf_counter() - started
        trace_id = client.create_trace_id(seed=trace_seed) if client else ""
        flush_langfuse()
        trace_url = client.get_trace_url(trace_id=trace_id) if client and trace_id else ""
        row = {
            "file": source.as_posix(),
            "page_count": page_count,
            "native_pages": native_pages,
            "scanned_pages": scanned_pages,
            "status": status,
            "latency_seconds": round(latency, 3),
            "estimated_cost_usd": round(scanned_pages * MISTRAL_OCR_USD_PER_PAGE, 6),
            "trace_id": trace_id or "",
            "trace_url": trace_url or "",
            "error": error,
        }
        rows.append(row)
        report_paths = _write_reports(rows, args.output_dir, run_id)
        print(
            json.dumps(
                {
                    "progress": f"{index}/{len(paths)}",
                    "file": source.as_posix(),
                    "status": status,
                    "latency_seconds": row["latency_seconds"],
                    "scanned_pages": scanned_pages,
                    "estimated_cost_usd": row["estimated_cost_usd"],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

    flush_langfuse()
    total_elapsed = time.perf_counter() - batch_started
    print(
        json.dumps(
            {
                "status": "completed",
                "total_elapsed_seconds": round(total_elapsed, 3),
                "reports": report_paths,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
