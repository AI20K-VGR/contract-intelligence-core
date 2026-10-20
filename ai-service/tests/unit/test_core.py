import unicodedata

import numpy as np
import pytest
from pydantic import ValidationError

from contract_ocr.application.use_cases.classify_pdf import PdfPageClassifier
from contract_ocr.domain.bbox import BBox
from contract_ocr.domain.entities import CriticalField, Document, Line, Page, Word
from contract_ocr.infrastructure.config import load_settings, read_manifest
from contract_ocr.infrastructure.image.degradation import VARIANTS, degrade
from contract_ocr.infrastructure.image.preprocessing import (
    ImagePreprocessor,
    rotate,
    validate_steps,
)
from contract_ocr.infrastructure.metrics.ocr_metrics import (
    OCRMetrics,
    bbox_metrics,
    critical_accuracy,
    normalize_value,
)
from contract_ocr.infrastructure.reporting import aggregate


def test_bbox_validation_and_iou():
    box = BBox.normalize([10, 20, 80, 40], 100, 100)
    assert box.x1 == 0.1 and box.iou(box) == 1
    assert box.iou(BBox(x1=0.9, y1=0.9, x2=1, y2=1)) == 0
    with pytest.raises(ValidationError):
        BBox(x1=0.8, y1=0, x2=0.2, y2=1)
    with pytest.raises(ValidationError):
        BBox(x1=float("nan"), y1=0, x2=1, y2=1)
    with pytest.raises(ValueError):
        BBox.normalize([0, 0, 1, 1], 0, 100)
    result = bbox_metrics([box, box], [box])
    assert result["n"] == 2 and result["mean_iou"] == 0.5


def test_metrics_unicode_and_empty():
    text = "\u0110i\u1ec1u kho\u1ea3n h\u1ee3p \u0111\u1ed3ng"
    metrics = OCRMetrics()
    assert metrics.text(text, unicodedata.normalize("NFD", text))["cer"] == 0
    assert metrics.text("abc", "adc")["cer"] == pytest.approx(1 / 3)
    assert metrics.text("one two", "one three")["wer"] == 0.5
    assert metrics.text("", "")["cer"] == 0
    assert metrics.text("", "ab")["cer"] == 2
    assert metrics.text("a\u0111", "\u00e1d")["diacritic_error_rate"] == 1
    assert metrics.text("a", "b")["diacritic_error_rate"] is None


@pytest.mark.parametrize(
    "kind,value,expected",
    [
        ("MONEY", "100.000.000 dong", "100000000"),
        ("MONEY", "10,50", "10.5"),
        ("DATE", "15/09/2026", "2026-09-15"),
        ("TAX_CODE", "0123-456", "0123456"),
        ("PARTY_NAME", "  Company   A ", "company a"),
    ],
)
def test_values(kind, value, expected):
    assert normalize_value(kind, value) == expected


def test_critical_number_boundaries_and_repeats():
    field = CriticalField(type="MONEY", value="100", raw_text="100 dong")
    assert critical_accuracy([field], "1000 dong")["critical_field_accuracy"] == 0
    assert critical_accuracy([field, field], "100 dong")["critical_field_accuracy"] == 0.5


def test_word_and_line_reject_bbox_without_declared_provenance():
    # Positive control (section 26): a bbox must never reach a consumer without
    # declaring how it was obtained. Prove the gate actually rejects the violation,
    # not just that well-formed input passes.
    box = BBox(x1=0.1, y1=0.1, x2=0.2, y2=0.2)
    with pytest.raises(ValidationError):
        Word(word_id="w1", text="x", bbox=box)  # no geometry_provenance
    with pytest.raises(ValidationError):
        Line(line_id="l1", text="x", bbox=box)  # no geometry_provenance
    with pytest.raises(ValidationError):
        Word(word_id="w1", text="x", geometry_provenance="MEASURED")  # provenance, no bbox
    # The well-formed shape the gate must still allow through:
    assert Word(word_id="w1", text="x", bbox=box, geometry_provenance="MEASURED").bbox is not None


def test_classifier():
    classifier = PdfPageClassifier()
    assert classifier.classify(1, 0, 0, 0, 0.97).input_type == "SCANNED"
    assert classifier.classify(1, 100, 20, 3, 0).input_type == "TEXT_LAYER"
    evidence = classifier.classify(1, 100, 20, 3, 0.9)
    assert evidence.input_type == "MIXED" and evidence.usable_text
    assert not classifier.classify(1, 5, 1, 1, 0.9).usable_text


def test_classifier_mixed_page_requires_ocr_regions_even_though_text_is_usable():
    # Section 3's explicit example: usable text + heavy image coverage must not
    # collapse into a plain native-only classification.
    classifier = PdfPageClassifier()
    evidence = classifier.classify(7, 500, 80, 12, 0.82)
    assert evidence.input_type == "MIXED"
    assert evidence.usable_text is True
    assert evidence.requires_ocr_regions is True
    assert "TEXT_LAYER_WITH_HEAVY_IMAGE_OVERLAY" in evidence.reason_codes


def test_classifier_plain_text_page_does_not_require_ocr_regions():
    classifier = PdfPageClassifier()
    evidence = classifier.classify(1, 100, 20, 3, 0)
    assert evidence.requires_ocr_regions is False
    assert "NATIVE_TEXT_USABLE" in evidence.reason_codes


def test_classifier_garbled_text_layer_is_not_usable_even_if_long_enough():
    classifier = PdfPageClassifier()
    garbled = "�" * 200  # a legacy-encoding text layer decoded to replacement chars
    evidence = classifier.classify(1, 200, 40, 5, 0, text_sample=garbled)
    assert evidence.usable_text is False
    assert evidence.input_type == "SCANNED"
    assert evidence.requires_ocr_regions is True
    assert "GARBLED_TEXT_LAYER" in evidence.reason_codes
    assert evidence.garbled_text_ratio == 1.0


def test_classifier_rejects_invalid_thresholds():
    with pytest.raises(ValueError):
        PdfPageClassifier(garbled_threshold=1.5)


def test_manifest(manifest, tmp_path):
    samples = read_manifest(manifest, tmp_path)
    assert len(samples) == 1 and samples[0].sample_id == "SYNTHETIC"
    manifest.write_text("sample_id,file_path\nX,a.pdf\nX,b.pdf\n")
    with pytest.raises(ValueError, match="duplicate"):
        read_manifest(manifest, tmp_path)
    manifest.write_text("sample_id,file_path,has_table\nX,a.pdf,maybe\n")
    with pytest.raises(ValueError, match="row 2"):
        read_manifest(manifest, tmp_path)


def test_schema_and_config(tmp_path):
    page = Page(
        page_number=1,
        width=100,
        height=100,
        engine="test",
        model="mock",
        lines=[Line(line_id="l1", text="MOCK")],
    )
    doc = Document(document_id="MOCK", source_file="mock.pdf", pages=[page])
    assert Document.model_validate_json(doc.model_dump_json()) == doc
    assert not page.lines[0].geometry_available
    with pytest.raises(ValidationError):
        Page(page_number=0, width=1, height=1, engine="x", model="x")
    config = tmp_path / "config.yaml"
    config.write_text("render: {dpi: 0}")
    with pytest.raises(ValueError):
        load_settings(config)


def test_preprocessing_and_inverse_geometry():
    image = np.full((100, 200, 3), 255, dtype=np.uint8)
    with pytest.raises(ValueError):
        validate_steps(["magic"])
    with pytest.raises(ValueError):
        validate_steps(["orientation90", "orientation180"])
    processor = ImagePreprocessor()
    baseline, matrix = processor.apply(image, [])
    assert np.array_equal(image, baseline) and np.array_equal(matrix, np.eye(3))
    rotated, transform = rotate(image, 90)
    corners = np.array([[20, 20, 1], [100, 20, 1], [100, 40, 1], [20, 40, 1]]) @ transform.T
    box = BBox.normalize(
        [corners[:, 0].min(), corners[:, 1].min(), corners[:, 0].max(), corners[:, 1].max()],
        rotated.shape[1],
        rotated.shape[0],
    )
    lines = [Line(line_id="l1", text="test", bbox=box, geometry_provenance="MEASURED")]
    processor.restore(lines, transform, rotated.shape, image.shape)
    assert lines[0].bbox.x1 == pytest.approx(0.1)
    assert lines[0].bbox.y2 == pytest.approx(0.4)
    for step in ("deskew", "grayscale", "contrast", "denoise", "threshold"):
        result, _ = processor.apply(image, [step])
        assert result.dtype == np.uint8


@pytest.mark.parametrize("variant", VARIANTS)
def test_degradation_reproducible(variant):
    image = np.full((60, 80, 3), 128, dtype=np.uint8)
    result, matrix = degrade(image, variant, 42)
    again, _ = degrade(image, variant, 42)
    assert np.array_equal(result, again) and matrix.shape == (3, 3)
    assert np.all(image == 128)


def test_aggregate_missing_and_failed_excluded():
    rows = [
        {"engine": "x", "status": "SUCCESS", "cer": 0.2, "processing_ms": 10},
        {"engine": "x", "status": "SUCCESS", "processing_ms": 20},
        {"engine": "x", "status": "FAILED", "cer": 0.9},
    ]
    result = aggregate(rows)[0]
    assert result["n"] == 3 and result["cer_n"] == 1
    assert result["mean_cer"] == 0.2 and result["success_n"] == 2
    assert result["wer_n"] == 0 and result["mean_wer"] is None
