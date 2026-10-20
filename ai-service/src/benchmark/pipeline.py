from __future__ import annotations

import shutil
from pathlib import Path
from time import perf_counter
from typing import Any

import pymupdf
import yaml
from PIL import Image

from benchmark.metrics import evaluate_fields, evaluate_tables, evaluate_text
from benchmark.preprocessing import preprocess
from benchmark.providers import MistralUnavailable, make_mistral_provider
from benchmark.schemas import (
    GroundTruthDocument,
    OCRDocumentResult,
    OCRTable,
    PreparedDocument,
    PreparedPage,
    ProviderInfo,
    RuntimeInfo,
    read_json,
    write_json,
)

SUPPORTED = {".pdf", ".png", ".jpg", ".jpeg"}


def load_config(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _metadata_by_name(root: Path) -> dict[str, dict]:
    path = root / "metadata" / "dataset.json"
    if not path.exists():
        return {}
    payload = read_json(path)
    items = payload.get("documents", payload) if isinstance(payload, dict) else payload
    return {str(item.get("file_name")): item for item in items}


def prepare_dataset(input_dir: Path, data_dir: Path, config: dict[str, Any]) -> list[PreparedDocument]:
    dpi = int(config.get("render", {}).get("dpi", 300))
    prepared_root = data_dir / "prepared"
    prepared_root.mkdir(parents=True, exist_ok=True)
    metadata = _metadata_by_name(data_dir)
    documents: list[PreparedDocument] = []
    for index, source in enumerate(sorted(p for p in input_dir.iterdir() if p.suffix.lower() in SUPPORTED), 1):
        meta = metadata.get(source.name, {})
        if meta.get("source_type", "scan") not in {"scan", "image"}:
            continue
        document_id = str(meta.get("document_id") or f"DOC-{index:03d}")
        target_dir = prepared_root / document_id
        target_dir.mkdir(parents=True, exist_ok=True)
        pages: list[PreparedPage] = []
        if source.suffix.lower() == ".pdf":
            # Deliberately render pixels only. No get_text()/text-layer extraction is
            # called anywhere in this benchmark path.
            with pymupdf.open(source) as pdf:
                for page_index, page in enumerate(pdf, 1):
                    pix = page.get_pixmap(dpi=dpi, alpha=False, colorspace=pymupdf.csRGB)
                    path = target_dir / f"page_{page_index:03d}.png"
                    pix.save(path)
                    pages.append(
                        PreparedPage(
                            page_number=page_index,
                            image_path=str(path.resolve()),
                            width=pix.width,
                            height=pix.height,
                            dpi=dpi,
                        )
                    )
        else:
            path = target_dir / "page_001.png"
            image = Image.open(source).convert("RGB")
            image.save(path, format="PNG")
            pages.append(
                PreparedPage(
                    page_number=1,
                    image_path=str(path.resolve()),
                    width=image.width,
                    height=image.height,
                    dpi=dpi,
                )
            )
        documents.append(
            PreparedDocument(
                document_id=document_id,
                file_name=source.name,
                source_path=str(source.resolve()),
                page_count=len(pages),
                language=meta.get("language", ["vi"]),
                source_type="image" if source.suffix.lower() != ".pdf" else "scan",
                scan_quality=meta.get("scan_quality", "unknown"),
                test_cases=meta.get("test_cases", []),
                pages=pages,
            )
        )
    write_json(data_dir / "prepared_manifest.json", [doc.model_dump(mode="json") for doc in documents])
    return documents


def _load_prepared(data_dir: Path) -> list[PreparedDocument]:
    return [PreparedDocument.model_validate(item) for item in read_json(data_dir / "prepared_manifest.json")]


def _merge_repeated_header_tables(pages: list) -> None:
    """Mark high-confidence adjacent repeated-header fragments as one logical table."""
    previous = None
    for page in pages:
        if not page.tables:
            previous = None
            continue
        current = page.tables[0]
        if previous is not None and previous.rows and current.rows:
            left = [" ".join(cell.casefold().split()) for cell in previous.rows[0]]
            right = [" ".join(cell.casefold().split()) for cell in current.rows[0]]
            if left == right and left:
                current.is_multi_page = True
                previous.is_multi_page = True
                previous.pages = sorted(set(previous.pages + current.pages))
                current.pages = list(previous.pages)
        previous = page.tables[-1]


def run_benchmark(
    data_dir: Path,
    artifacts_dir: Path,
    config: dict[str, Any],
) -> list[dict]:
    documents = _load_prepared(data_dir)
    dpi = int(config.get("render", {}).get("dpi", 300))
    mistral_config = config.get("mistral", {})
    name = "mistral"
    experiments = config.get("experiments", [{"id": "raw", "preprocessing": []}])
    statuses: list[dict] = []
    for experiment in experiments:
        experiment_id = str(experiment["id"])
        steps = list(experiment.get("preprocessing", []))
        experiment_images: dict[tuple[str, int], Path] = {}
        for doc in documents:
            for page in doc.pages:
                source = Path(page.image_path)
                target = artifacts_dir / "_images" / experiment_id / doc.document_id / source.name
                if steps:
                    preprocess(source, target, steps)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if not target.exists():
                        shutil.copy2(source, target)
                experiment_images[(doc.document_id, page.page_number)] = target
        try:
            provider = make_mistral_provider(mistral_config, dpi=dpi)
        except MistralUnavailable as exc:
            statuses.append(
                {
                    "provider": name,
                    "experiment": experiment_id,
                    "status": "SKIPPED",
                    "error": str(exc),
                }
            )
            continue
        for doc in documents:
            pages = []
            tick = perf_counter()
            error = None
            try:
                for page in doc.pages:
                    image_path = experiment_images[(doc.document_id, page.page_number)]
                    pages.append(
                        provider.process_page(
                            image_path,
                            document_id=doc.document_id,
                            page_number=page.page_number,
                        )
                    )
                    raw_path = image_path.parent / "raw" / "raw.md"
                    if raw_path.exists():
                        raw_target = (
                            artifacts_dir
                            / doc.document_id
                            / experiment_id
                            / name
                            / "raw"
                            / f"page_{page.page_number:03d}.md"
                        )
                        raw_target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(raw_path, raw_target)
                _merge_repeated_header_tables(pages)
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
            if error:
                statuses.append(
                    {
                        "document_id": doc.document_id,
                        "provider": name,
                        "experiment": experiment_id,
                        "status": "FAILED",
                        "error": error,
                    }
                )
                continue
            total_ms = (perf_counter() - tick) * 1000
            price = mistral_config.get("price_per_page")
            result = OCRDocumentResult(
                document_id=doc.document_id,
                experiment=experiment_id,
                provider=ProviderInfo(name=name, model=provider.model),
                pages=pages,
                runtime=RuntimeInfo(
                    total_latency_ms=total_ms,
                    pages_processed=len(pages),
                    cost_usd=float(price) * len(pages) if price is not None else None,
                ),
            )
            target = artifacts_dir / doc.document_id / experiment_id / name / "normalized.json"
            write_json(target, result)
            statuses.append(
                {
                    "document_id": doc.document_id,
                    "provider": name,
                    "experiment": experiment_id,
                    "status": "SUCCESS",
                    "error": "",
                }
            )
    write_json(artifacts_dir / "run_status.json", statuses)
    return statuses


def evaluate_benchmark(data_dir: Path, artifacts_dir: Path, reports_dir: Path) -> dict[str, list[dict]]:
    documents = {doc.document_id: doc for doc in _load_prepared(data_dir)}
    by_page: list[dict] = []
    by_document: list[dict] = []
    field_rows: list[dict] = []
    failures: list[dict] = []
    for path in artifacts_dir.glob("*/*/*/normalized.json"):
        result = OCRDocumentResult.model_validate(read_json(path))
        gt_path = data_dir / "ground_truth" / f"{result.document_id}.json"
        if not gt_path.exists():
            continue
        truth = GroundTruthDocument.model_validate(read_json(gt_path))
        truth_pages = {page.page_number: page for page in truth.pages}
        page_metrics = []
        for page in result.pages:
            expected = truth_pages.get(page.page_number)
            if expected is None:
                continue
            text_metrics = evaluate_text(expected.text, page.text)
            fields, details = evaluate_fields(expected.critical_fields, page.text)
            table_metrics = evaluate_tables(expected.tables, page.tables)
            row = {
                "document_id": result.document_id,
                "page_number": page.page_number,
                "provider": result.provider.name,
                "model": result.provider.model,
                "experiment": result.experiment,
                "latency_ms": page.latency_ms,
                **text_metrics,
                **fields,
                **table_metrics,
            }
            by_page.append(row)
            page_metrics.append(row)
            for detail in details:
                detail_row = {**{k: row[k] for k in ("document_id", "page_number", "provider", "experiment")}, **detail}
                field_rows.append(detail_row)
                if not detail["normalized_match"]:
                    failures.append({**detail_row, "error_type": "critical_field_error", "severity": "CRITICAL"})
            if text_metrics["normalized_cer"] > 0:
                failures.append({**row, "error_type": "text_error", "severity": "HIGH" if text_metrics["normalized_cer"] >= 0.2 else "MEDIUM", "ground_truth": expected.text, "prediction": page.text})
            if table_metrics["table_fn"] or table_metrics["table_fp"]:
                failures.append({**row, "error_type": "table_failure", "severity": "HIGH"})
        if not page_metrics:
            continue
        metadata = documents[result.document_id]
        doc_text_ref = "\f".join(page.text for page in truth.pages)
        doc_text_pred = "\f".join(page.text for page in result.pages)
        doc_fields = [field for page in truth.pages for field in page.critical_fields]
        fields, _ = evaluate_fields(doc_fields, doc_text_pred)
        all_gt_tables = [table for page in truth.pages for table in page.tables]
        unique_gt = {table.table_id: table for table in all_gt_tables}
        all_pred_tables = [table for page in result.pages for table in page.tables]
        unique_pred: dict[tuple, OCRTable] = {}
        for table in all_pred_tables:
            key = tuple(table.pages) if table.is_multi_page else (table.table_id,)
            if key not in unique_pred:
                unique_pred[key] = table.model_copy(deep=True)
                continue
            target = unique_pred[key]
            extra_rows = table.rows
            if target.rows and extra_rows and target.rows[0] == extra_rows[0]:
                extra_rows = extra_rows[1:]
            target.rows.extend(extra_rows)
            target.pages = sorted(set(target.pages + table.pages))
        by_document.append(
            {
                "document_id": result.document_id,
                "provider": result.provider.name,
                "model": result.provider.model,
                "experiment": result.experiment,
                "page_count": len(result.pages),
                "scan_quality": metadata.scan_quality,
                "test_cases": ",".join(metadata.test_cases),
                **evaluate_text(doc_text_ref, doc_text_pred),
                **fields,
                **evaluate_tables(list(unique_gt.values()), list(unique_pred.values())),
                "total_latency_ms": result.runtime.total_latency_ms,
                "latency_per_page_ms": result.runtime.total_latency_ms / max(1, result.runtime.pages_processed),
                "total_cost_usd": result.runtime.cost_usd,
                "cost_per_page_usd": result.runtime.cost_usd / max(1, result.runtime.pages_processed) if result.runtime.cost_usd is not None else None,
            }
        )
    for level, rows in (("page", by_page), ("document", by_document)):
        for metric in ("normalized_cer", "normalized_wer"):
            worst = sorted(
                (row for row in rows if row.get(metric) is not None and row[metric] > 0),
                key=lambda row: row[metric],
                reverse=True,
            )[:10]
            failures.extend(
                {
                    **row,
                    "error_type": f"highest_{metric}_{level}",
                    "severity": "HIGH",
                }
                for row in worst
            )
    status_path = artifacts_dir / "run_status.json"
    if status_path.exists():
        failures.extend(
            {
                **item,
                "error_type": "provider_error" if item.get("status") == "FAILED" else "provider_skipped",
                "severity": "HIGH" if item.get("status") == "FAILED" else "INFO",
            }
            for item in read_json(status_path)
            if item.get("status") != "SUCCESS"
        )
    payload = {"by_page": by_page, "by_document": by_document, "critical_fields": field_rows, "failures": failures}
    reports_dir.mkdir(parents=True, exist_ok=True)
    write_json(reports_dir / "evaluation.json", payload)
    return payload
