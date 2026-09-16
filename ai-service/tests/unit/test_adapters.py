import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from contract_ocr.application.ports.ocr_engine import EngineUnavailable
from contract_ocr.domain.entities import Context
from contract_ocr.infrastructure.metrics.ocr_metrics import OCRMetrics
from contract_ocr.infrastructure.ocr.deepseek_ocr import DeepSeekOCRAdapter
from contract_ocr.infrastructure.ocr.paddle_ocr import PaddleOCREngine


def test_paddle_payload_rgb_and_geometry(tmp_path):
    class Stub:
        def predict(self, image):
            assert image[0, 0].tolist() == [30, 20, 10]
            return [
                SimpleNamespace(
                    json={
                        "res": {
                            "rec_texts": ["MOCK"],
                            "rec_scores": [0.9],
                            "rec_polys": [[[1, 2], [8, 2], [8, 4], [1, 4]]],
                        }
                    }
                )
            ]

    adapter = PaddleOCREngine()
    adapter._engine = Stub()
    result = adapter.recognize_page(
        np.full((10, 10, 3), [10, 20, 30], dtype=np.uint8),
        Context(document_id="MOCK", page=1, output_dir=str(tmp_path)),
    )
    assert result.lines[0].bbox.x1 == 0.1
    assert result.lines[0].words == []
    assert json.loads(Path(result.raw_output_path).read_text())[0]["rec_texts"] == ["MOCK"]


def test_deepseek_none_return_reads_raw_markdown(tmp_path, monkeypatch, capsys):
    class Stub:
        def infer(self, tokenizer, **kwargs):
            assert kwargs["image_size"] == 768
            assert "\n" in kwargs["prompt"]
            print("MOCK private text")
            (Path(kwargs["output_path"]) / "result.mmd").write_text("# MOCK text", encoding="utf-8")

    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(cuda=SimpleNamespace(max_memory_allocated=lambda device: 0)),
    )
    adapter = DeepSeekOCRAdapter()
    adapter._engine = Stub()
    adapter._tokenizer = object()
    result = adapter.recognize_page(
        np.zeros((10, 10, 3), dtype=np.uint8),
        Context(document_id="MOCK", page=1, output_dir=str(tmp_path)),
    )
    assert result.raw_markdown == "# MOCK text"
    assert result.lines[0].bbox is None
    assert "private" not in capsys.readouterr().out
    assert "private" in (tmp_path / "inference_stdout.txt").read_text()


def test_deepseek_unavailable_is_cached(monkeypatch):
    monkeypatch.setitem(
        sys.modules, "torch", SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False))
    )
    adapter = DeepSeekOCRAdapter()
    for _ in range(2):
        with pytest.raises(EngineUnavailable, match="CUDA"):
            adapter._load()


def test_diacritic_stroke_d_and_denominator():
    metrics = OCRMetrics()
    result = metrics.text("a\u0111", "\u00e1d")
    assert result["diacritic_aligned_letters"] == 2
    assert result["diacritic_errors"] == 2
    assert metrics.text("\u0111", "d")["diacritic_error_rate"] == 1
    assert metrics.text("?", "d")["diacritic_error_rate"] is None
