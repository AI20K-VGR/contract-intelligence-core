"""`MistralOCREngine.recognize_page` itself has no direct test anywhere else --
`test_markdown_tables.py` only covers its pure-function helpers, and
`tests/integration/test_pipeline.py`'s "mistral" experiments all use a generic
`FakeEngine` stub instead of this class. This file closes that gap: a mocked
Mistral SDK client stands in for the real API call, so these run without
`MISTRAL_API_KEY` or network access.

Note on scope: which pages ever reach an OCR engine's `recognize_page` at all
(native-text pages never do, only SCANNED/MIXED ones) is `ProcessDocument`'s
own routing logic, already covered engine-agnostically by
`test_pipeline.py::test_native_routing_and_ocr` and
`test_mixed_page_is_ocred_not_silently_read_native_only` -- that guard runs
before any engine is invoked, so it applies to `MistralOCREngine` the same as
to any other `OCREngine`, without needing a Mistral-specific repeat of it
here.
"""

from types import SimpleNamespace

import numpy as np
import pytest

from contract_ocr.application.ports.ocr_engine import EngineUnavailable
from contract_ocr.domain.entities import Context
from contract_ocr.infrastructure.ocr.mistral_ocr import MistralOCREngine


def _block(
    kind: str,
    content: str,
    *,
    bbox_px=(10, 10, 90, 30),
    confidence: float | None = 0.95,
):
    x0, y0, x1, y1 = bbox_px
    scores = (
        SimpleNamespace(average_content_confidence_score=confidence)
        if confidence is not None
        else None
    )
    return SimpleNamespace(
        type=kind,
        content=content,
        top_left_x=x0,
        top_left_y=y0,
        bottom_right_x=x1,
        bottom_right_y=y1,
        confidence_scores=scores,
    )


def _response(markdown: str, blocks: list, *, width=100, height=100):
    page = SimpleNamespace(
        markdown=markdown, blocks=blocks, dimensions=SimpleNamespace(width=width, height=height)
    )
    return SimpleNamespace(pages=[page])


class _FakeOcr:
    def __init__(self, response, captured: dict):
        self._response = response
        self._captured = captured

    def process(self, **kwargs):
        self._captured.update(kwargs)
        return self._response


class _FakeClient:
    def __init__(self, response, captured: dict):
        self.ocr = _FakeOcr(response, captured)


def _engine_with(monkeypatch, response, *, config=None, captured=None):
    captured = captured if captured is not None else {}
    monkeypatch.setattr("mistralai.client.Mistral", lambda api_key: _FakeClient(response, captured))
    return MistralOCREngine(api_key="sk-test", **(config or {})), captured


def _context(tmp_path, page=1):
    return Context(document_id="DOC", page=page, output_dir=str(tmp_path / f"p{page:03d}"))


def test_text_block_becomes_a_measured_line(monkeypatch, tmp_path):
    response = _response(
        "Dieu 1. Gia tri hop dong",
        [_block("text", "Dieu 1. Gia tri hop dong", bbox_px=(10, 20, 90, 40), confidence=0.97)],
    )
    engine, _ = _engine_with(monkeypatch, response)

    result = engine.recognize_page(np.zeros((100, 100, 3), dtype=np.uint8), _context(tmp_path))

    assert len(result.lines) == 1
    line = result.lines[0]
    assert line.text == "Dieu 1. Gia tri hop dong"
    assert line.geometry_provenance == "MEASURED"
    assert line.confidence == 0.97
    assert line.bbox.x1 == pytest.approx(0.10) and line.bbox.y1 == pytest.approx(0.20)
    assert result.tables == []


def test_table_block_becomes_a_table_with_heading_before(monkeypatch, tmp_path):
    # Real Vietnamese diacritics on purpose: is_annex_heading() is diacritic-sensitive
    # by design (domain/headings.py -- Mistral, unlike Tesseract, reliably keeps
    # accents), so an unaccented "Phu luc 01" would not be recognized as a heading.
    heading = "Phụ lục 01"
    table_md = "| STT | Ten hang |\n| --- | --- |\n| 1 | Hang A |"
    response = _response(
        heading + "\n\n" + table_md,
        [
            _block("text", heading, bbox_px=(10, 5, 90, 15)),
            _block("table", table_md, bbox_px=(10, 20, 90, 60)),
        ],
    )
    engine, _ = _engine_with(monkeypatch, response)

    result = engine.recognize_page(np.zeros((100, 100, 3), dtype=np.uint8), _context(tmp_path))

    assert result.lines[0].text == heading
    assert len(result.tables) == 1
    table = result.tables[0]
    assert table.header == ["STT", "Ten hang"]
    assert table.heading_before == heading
    assert table.geometry_provenance == "MEASURED"
    assert all(cell.geometry_provenance == "CLAIMED" for row in table.rows for cell in row.cells)


def test_requests_blocks_and_block_level_confidence_and_leaves_table_format_unset(
    monkeypatch, tmp_path
):
    engine, captured = _engine_with(monkeypatch, _response("", []))

    engine.recognize_page(np.zeros((100, 100, 3), dtype=np.uint8), _context(tmp_path))

    assert captured["include_blocks"] is True
    assert captured["confidence_scores_granularity"] == "block"
    assert captured["table_format"] is None


def test_raw_markdown_is_written_to_raw_md(monkeypatch, tmp_path):
    response = _response("Toan van trang", [_block("text", "Toan van trang")])
    engine, _ = _engine_with(monkeypatch, response)
    context = _context(tmp_path)

    result = engine.recognize_page(np.zeros((100, 100, 3), dtype=np.uint8), context)

    assert result.raw_markdown == "Toan van trang"
    raw_path = tmp_path / "p001" / "raw.md"
    assert raw_path.read_text(encoding="utf-8") == "Toan van trang"
    assert result.raw_output_path == str(raw_path.resolve())


def test_no_blocks_returns_empty_result_without_crashing(monkeypatch, tmp_path):
    engine, _ = _engine_with(monkeypatch, _response("", []))

    result = engine.recognize_page(np.zeros((100, 100, 3), dtype=np.uint8), _context(tmp_path))

    assert result.lines == []
    assert result.tables == []


def test_missing_api_key_raises_engine_unavailable(tmp_path, monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    engine = MistralOCREngine()
    with pytest.raises(EngineUnavailable, match="MISTRAL_API_KEY"):
        engine.recognize_page(np.zeros((10, 10, 3), dtype=np.uint8), _context(tmp_path))


def test_unavailability_is_cached_after_first_failure(monkeypatch, tmp_path):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    engine = MistralOCREngine()
    for _ in range(2):
        with pytest.raises(EngineUnavailable):
            engine.recognize_page(np.zeros((10, 10, 3), dtype=np.uint8), _context(tmp_path))
