import csv
import hashlib
import importlib.metadata
import json
import platform
import statistics
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psutil

from contract_ocr.domain.entities import Document, Sample, Settings

METRICS = [
    "cer",
    "wer",
    "exact_match",
    "diacritic_error_rate",
    "critical_field_accuracy",
    "processing_ms",
    "word_mean_iou",
    "word_hit_rate",
    "line_mean_iou",
    "line_hit_rate",
]
BASE_COLUMNS = [
    "run_id",
    "sample_id",
    "engine",
    "model",
    "experiment",
    "language",
    "input_type",
    "quality",
    "degradation",
    *METRICS,
    "n",
    "status",
    "error",
]


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    columns = list(dict.fromkeys(columns + [key for row in rows for key in row]))
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def fingerprint(path: str) -> dict:
    p = Path(path)
    if not p.is_file():
        return {"path": path, "sha256": None, "error": "missing"}
    digest = hashlib.sha256()
    with p.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"path": path, "sha256": digest.hexdigest(), "bytes": p.stat().st_size}


def aggregate(rows: list[dict]) -> list[dict]:
    keys = ["engine", "experiment", "language", "input_type", "quality", "degradation"]
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row.get(k, "") for k in keys)].append(row)
    results = []
    for key, group in groups.items():
        result = dict(zip(keys, key, strict=True))
        successes = [r for r in group if r["status"] == "SUCCESS"]
        result.update(
            n=len(group),
            success_n=len(successes),
            failed_n=sum(r["status"] == "FAILED" for r in group),
            skipped_n=sum(r["status"] == "SKIPPED" for r in group),
            success_rate=len(successes) / len(group),
            success_rate_n=len(group),
        )
        for metric in METRICS:
            values = [r[metric] for r in successes if r.get(metric) is not None]
            result[f"{metric}_n"] = len(values)
            result[f"mean_{metric}"] = statistics.mean(values) if values else None
            result[f"median_{metric}"] = statistics.median(values) if values else None
        field_total = sum(r.get("critical_field_total", 0) for r in successes)
        result["critical_fields_n"] = field_total
        result["pooled_critical_field_accuracy"] = (
            sum(r.get("critical_field_correct", 0) for r in successes) / field_total
            if field_total
            else None
        )
        results.append(result)
    return results


def display(value: float | None, n: int) -> str:
    return f"{value:.4f} (n={n})" if value is not None else f"N/A (n={n})"


class FileReporter:
    def start(self, output: Path, settings: Settings, samples: list[Sample]) -> None:
        # Refuse accidental overwrite; use a new run directory.
        output.mkdir(parents=True, exist_ok=False)
        write_json(output / "config.json", settings.model_dump())
        write_json(output / "manifest_snapshot.json", [s.model_dump() for s in samples])
        paths = sorted(
            {
                getattr(s, k)
                for s in samples
                for k in (
                    "file_path",
                    "ground_truth_text",
                    "ground_truth_bbox",
                    "ground_truth_critical_fields",
                )
                if getattr(s, k)
            }
        )
        write_json(output / "input_hashes.json", [fingerprint(p) for p in paths])
        self.environment = {
            "timestamp_utc": datetime.now(UTC).isoformat(),
            "python": sys.version,
            "platform": platform.platform(),
            "processor": platform.processor(),
            "cpu_count": psutil.cpu_count(),
            "ram_bytes": psutil.virtual_memory().total,
            "packages": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
            "external_api_cost_usd": 0,
            "local_compute_cost_usd": None,
        }
        write_json(output / "environment.json", self.environment)

    def prediction(self, output: Path, sample: Sample, experiment: str, document: Document) -> None:
        write_json(
            output / "predictions" / sample.sample_id / experiment / "output.json",
            document.model_dump(mode="json"),
        )

    def finish(
        self, output: Path, rows: list[dict], failures: list[dict], engines: dict, elapsed_ms: float
    ) -> None:
        summary = aggregate(rows)
        write_csv(output / "metrics_by_sample.csv", rows, BASE_COLUMNS)
        write_csv(
            output / "metrics_summary.csv",
            summary,
            ["engine", "experiment", "language", "input_type", "quality", "degradation", "n"],
        )
        write_csv(
            output / "failures.csv",
            failures,
            BASE_COLUMNS + ["error_type", "ground_truth", "prediction"],
        )
        memory = psutil.Process().memory_info()
        self.environment.update(
            total_runtime_ms=elapsed_ms,
            rss_end_bytes=memory.rss,
            peak_rss_bytes=getattr(memory, "peak_wset", None),
            engines={
                name: {
                    "model": engine.model,
                    "initialization_ms": engine.initialization_ms,
                    **engine.runtime_info,
                }
                for name, engine in engines.items()
            },
        )
        write_json(output / "environment.json", self.environment)
        lines = [
            "# Benchmark summary",
            "",
            f"Sample-experiment attempts: n={len(rows)}. Distinct samples: n={len({r['sample_id'] for r in rows})}.",
            "",
            "Accuracy aggregates include only complete SUCCESS samples with annotations. Missing metrics remain blank. Native pages use PyMuPDF in every pipeline; do not attribute their accuracy to the OCR model.",
            "",
            "External API cost: $0. Local compute cost is unestimated; see environment.json.",
            "",
            "## Decision support",
            "",
            "| Engine / experiment / stratum | CER | Critical field accuracy | BBox support | Vietnamese CER | Latency ms/sample | Infrastructure | Failure cases |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for item in summary:
            vi = item["mean_cer"] if item["language"] in {"vi", "vi-en", "bilingual"} else None
            support = (
                "native words/lines"
                if item["engine"] == "pymupdf"
                else "OCR lines; native words"
                if item["engine"] == "paddle"
                else "native pages only"
            )
            label = "/".join(
                str(item[k])
                for k in (
                    "engine",
                    "experiment",
                    "language",
                    "input_type",
                    "quality",
                    "degradation",
                )
            )
            lines.append(
                f"| {label} | {display(item['mean_cer'], item['cer_n'])} | {display(item['pooled_critical_field_accuracy'], item['critical_fields_n'])} | {support} | {display(vi, item['cer_n'] if vi is not None else 0)} | {display(item['mean_processing_ms'], item['processing_ms_n'])} | {'NVIDIA CUDA' if item['engine'] == 'deepseek' else 'CPU'} | failed={item['failed_n']}, skipped={item['skipped_n']} (n={item['n']}) |"
            )
        lines += [
            "",
            "Final model selection requires human review of paired samples, Vietnamese results, and failure artifacts. No automated winner is selected.",
        ]
        (output / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        details = [
            "# Failure analysis",
            "",
            f"Failure entries: n={len(failures)}. A sample may appear in multiple categories.",
            "",
            "Full reference and prediction text is in failures.csv; treat the entire run directory as confidential.",
            "",
        ]
        for row in failures:
            details.append(f"- {row['sample_id']} / {row['experiment']}: {row['error_type']} (n=1)")
        (output / "failure_analysis.md").write_text("\n".join(details) + "\n", encoding="utf-8")
