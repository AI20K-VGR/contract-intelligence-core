import json
from pathlib import Path

from contract_ocr.domain.bbox import BBox
from contract_ocr.domain.entities import CriticalField, Document, Sample

from .ocr_metrics import OCRMetrics, bbox_metrics, critical_accuracy


class SampleEvaluator:
    def __init__(self, bbox_threshold: float = 0.5) -> None:
        self.bbox_threshold = bbox_threshold

    def evaluate(self, sample: Sample, document: Document) -> tuple[dict, str, str]:
        prediction = "\f".join("\n".join(line.text for line in p.lines) for p in document.pages)
        metrics, reference = {}, ""
        if sample.ground_truth_text:
            reference = Path(sample.ground_truth_text).read_text(encoding="utf-8")
            metrics.update(OCRMetrics().text(reference, prediction))
        if sample.ground_truth_critical_fields:
            fields = [
                CriticalField.model_validate(f)
                for f in json.loads(
                    Path(sample.ground_truth_critical_fields).read_text(encoding="utf-8")
                )
            ]
            correct, total = 0, 0
            for page_num in {field.page for field in fields}:
                subset = [f for f in fields if f.page == page_num]
                if page_num is not None and page_num > len(document.pages):
                    raise ValueError("critical field annotation references missing page")
                text = (
                    prediction
                    if page_num is None
                    else "\n".join(line.text for line in document.pages[page_num - 1].lines)
                )
                values = critical_accuracy(subset, text)
                correct += values["critical_field_correct"]
                total += values["critical_field_total"]
            metrics.update(
                critical_field_correct=correct,
                critical_field_total=total,
                critical_field_accuracy=correct / total if total else None,
            )
        if sample.ground_truth_bbox:
            annotations = json.loads(Path(sample.ground_truth_bbox).read_text(encoding="utf-8"))
            for annotation in annotations:
                if annotation["level"] not in {"word", "line"} or not 1 <= annotation[
                    "page"
                ] <= len(document.pages):
                    raise ValueError("invalid bbox annotation level or page")
                BBox.model_validate(annotation["bbox"])
            for level in ("word", "line"):
                n, score, hits = 0, 0.0, 0.0
                for page in document.pages:
                    refs = [
                        BBox.model_validate(a["bbox"])
                        for a in annotations
                        if a["level"] == level and a["page"] == page.page_number
                    ]
                    items = (
                        page.lines
                        if level == "line"
                        else [w for line in page.lines for w in line.words]
                    )
                    # Engines without reliable geometry are N/A, not zero-quality geometry.
                    if not any(item.bbox is not None for item in items):
                        continue
                    result = bbox_metrics(
                        refs,
                        [item.bbox for item in items if item.bbox is not None],
                        self.bbox_threshold,
                    )
                    n += result["n"]
                    score += (result["mean_iou"] or 0) * result["n"]
                    hits += (result["hit_rate"] or 0) * result["n"]
                metrics.update(
                    {
                        f"{level}_bbox_n": n,
                        f"{level}_mean_iou": score / n if n else None,
                        f"{level}_hit_rate": hits / n if n else None,
                    }
                )
        return metrics, reference, prediction
