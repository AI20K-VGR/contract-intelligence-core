from pathlib import Path
from time import perf_counter
from typing import Protocol

from contract_ocr.application.ports.ocr_engine import OCREngine
from contract_ocr.domain.entities import Document, Sample, Settings
from contract_ocr.domain.enums import Status

from .process_document import ProcessDocument


class SampleEvaluatorPort(Protocol):
    def evaluate(self, sample: Sample, document: Document) -> tuple[dict, str, str]: ...


class ReportPort(Protocol):
    def start(self, output: Path, settings: Settings, samples: list[Sample]) -> None: ...
    def prediction(
        self, output: Path, sample: Sample, experiment: str, document: Document
    ) -> None: ...
    def finish(
        self, output: Path, rows: list[dict], failures: list[dict], engines: dict, elapsed_ms: float
    ) -> None: ...


class RunBenchmark:
    def __init__(
        self, processor: ProcessDocument, evaluator: SampleEvaluatorPort, reporter: ReportPort
    ) -> None:
        self.processor, self.evaluator, self.reporter = processor, evaluator, reporter

    def execute(
        self, samples: list[Sample], settings: Settings, engines: dict[str, OCREngine], output: Path
    ) -> list[dict]:
        self.reporter.start(output, settings, samples)
        start = perf_counter()
        rows, failures = [], []
        for sample in samples:
            for experiment in settings.experiments:
                engine = engines.get(experiment.engine)
                row = {
                    "run_id": output.name,
                    **sample.model_dump(),
                    "engine": experiment.engine,
                    "model": engine.model if engine else "native",
                    "experiment": experiment.id,
                    "n": 1,
                    "status": Status.FAILED,
                    "error": "",
                    "external_api_cost_usd": 0,
                }
                reference, prediction = "", ""
                tick = perf_counter()
                try:
                    document = self.processor.execute(
                        sample.file_path,
                        sample.sample_id,
                        experiment,
                        engine,
                        output / "predictions" / sample.sample_id / experiment.id,
                        output.name,
                        settings.render["dpi"],
                    )
                    self.reporter.prediction(output, sample, experiment.id, document)
                    statuses = [p.status for p in document.pages]
                    # Partial samples are not eligible for aggregate accuracy comparisons.
                    row["status"] = (
                        Status.FAILED
                        if Status.FAILED in statuses
                        else Status.SKIPPED
                        if Status.SKIPPED in statuses
                        else Status.SUCCESS
                    )
                    row["error"] = "; ".join(
                        f"page {p.page_number}: {p.error}" for p in document.pages if p.error
                    )
                    row["pages"] = len(document.pages)
                    row["successful_pages"] = statuses.count(Status.SUCCESS)
                    row["native_pages"] = sum(
                        p.engine == "pymupdf" and p.status == Status.SUCCESS for p in document.pages
                    )
                    row["ocr_pages"] = sum(
                        p.engine != "pymupdf" and p.status == Status.SUCCESS for p in document.pages
                    )
                    row["actual_engines"] = ",".join(
                        sorted({p.engine for p in document.pages if p.status == Status.SUCCESS})
                    )
                    row["detected_input_types"] = ",".join(
                        sorted({p.input_type for p in document.pages})
                    )
                    row["geometry_pages"] = sum(p.geometry_available for p in document.pages)
                    metrics, reference, prediction = self.evaluator.evaluate(sample, document)
                    row.update(metrics)
                except Exception as exc:
                    row["status"], row["error"] = Status.FAILED, f"{type(exc).__name__}: {exc}"
                row["processing_ms"] = (perf_counter() - tick) * 1000
                row["milliseconds_per_page"] = (
                    row["processing_ms"] / row["pages"] if row.get("pages") else None
                )
                row["pages_per_minute"] = (
                    row.get("successful_pages", 0) * 60000 / row["processing_ms"]
                    if row["processing_ms"]
                    else None
                )
                rows.append(row)
                reasons = []
                if row["status"] != Status.SUCCESS:
                    reasons.append(row["status"])
                if (
                    row.get("critical_field_accuracy") is not None
                    and row["critical_field_accuracy"] < 1
                ):
                    reasons.append("critical_field_mismatch")
                if not prediction.strip():
                    reasons.append("empty_result")
                if reasons:
                    failures.append(
                        {
                            **row,
                            "error_type": ",".join(reasons),
                            "ground_truth": reference,
                            "prediction": prediction,
                        }
                    )
                row["_ground_truth"], row["_prediction"] = reference, prediction
        for metric in ("cer", "wer"):
            ranked = sorted(
                (r for r in rows if r.get(metric) is not None and r[metric] > 0),
                key=lambda r: r[metric],
                reverse=True,
            )[:10]
            for row in ranked:
                failures.append(
                    {
                        **row,
                        "error_type": f"highest_{metric}",
                        "ground_truth": row["_ground_truth"],
                        "prediction": row["_prediction"],
                    }
                )
        for row in rows:
            row.pop("_ground_truth", None)
            row.pop("_prediction", None)
        for failure in failures:
            failure.pop("_ground_truth", None)
            failure.pop("_prediction", None)
        self.reporter.finish(output, rows, failures, engines, (perf_counter() - start) * 1000)
        return rows
