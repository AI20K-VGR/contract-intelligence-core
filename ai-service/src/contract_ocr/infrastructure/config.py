import csv
import os
from pathlib import Path

import yaml

from contract_ocr.domain.entities import Sample, Settings
from contract_ocr.infrastructure.image.preprocessing import validate_steps


def read_manifest(path: Path, root: Path) -> list[Sample]:
    samples = []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not {"sample_id", "file_path"}.issubset(reader.fieldnames or []):
            raise ValueError("manifest requires sample_id and file_path")
        for row_number, row in enumerate(reader, 2):
            try:
                sample = Sample.model_validate({k: v for k, v in row.items() if v != ""})
            except Exception as exc:
                raise ValueError(f"manifest row {row_number}: {exc}") from exc
            for field in (
                "file_path",
                "ground_truth_text",
                "ground_truth_bbox",
                "ground_truth_critical_fields",
            ):
                value = getattr(sample, field)
                if value:
                    setattr(sample, field, str((root / value).resolve()))
            samples.append(sample)
    if len({s.sample_id for s in samples}) != len(samples):
        raise ValueError("duplicate sample_id in manifest")
    return samples


def load_settings(path: Path) -> Settings:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    settings = Settings.model_validate(data)
    settings.render["dpi"] = int(os.environ.get("OCR_DPI", settings.render.get("dpi", 300)))
    if not 72 <= settings.render["dpi"] <= 600:
        raise ValueError("render DPI must be 72..600")
    if settings.evaluation.get("unicode_normalization", "NFC") != "NFC":
        raise ValueError("evaluation must preserve Vietnamese accents using NFC")
    if not 0 <= settings.evaluation.get("bbox_iou_threshold", 0.5) <= 1:
        raise ValueError("bbox threshold must be in 0..1")
    if len({e.id for e in settings.experiments}) != len(settings.experiments):
        raise ValueError("duplicate experiment id")
    for experiment in settings.experiments:
        validate_steps(experiment.preprocessing)
    return settings
