"""PaddleOCR (detection) + VietOCR (recognition) adapter.

PaddleOCR's own end-to-end pipeline already does detection+recognition
together (see `infrastructure/ocr/paddle_ocr.py`), but this adapter
deliberately splits the two steps: PaddleOCR only DETECTS text-line boxes,
and VietOCR — a recognizer trained specifically on Vietnamese diacritics —
reads each one. Output granularity therefore follows detection: one `Word`
per detected LINE, not per word.

Both the detector and recognizer are injected as `LineDetector`/
`TextRecognizer` (see `protocols.py`) so tests never need PaddleOCR or
VietOCR installed; the real backends are only imported lazily, on first
real use, exactly like `OpenAIVisionOCREngine._load()`.
"""

from __future__ import annotations

from typing import Any

from contract_ocr.application.ports.ocr_engine import EngineUnavailable
from contract_ocr.table_reconstruct.types import Bbox, Word

from .protocols import LineDetector, TextRecognizer
from .types import Region


class OcrAdapter:
    def __init__(
        self, detector: LineDetector | None = None, recognizer: TextRecognizer | None = None
    ) -> None:
        self._detector = detector
        self._recognizer = recognizer

    def extract(self, image: Any, region: Region) -> list[Word]:
        detector = self._get_detector()
        recognizer = self._get_recognizer()

        region_crop = _crop(image, region.bbox)
        words: list[Word] = []
        for local_bbox in detector.detect(region_crop):
            line_crop = _crop(region_crop, local_bbox)
            text = recognizer.recognize(line_crop)
            if not text.strip():
                continue
            bbox = _to_absolute(local_bbox, region.bbox)
            words.append(
                Word(text=text, x0=bbox[0], y0=bbox[1], x1=bbox[2], y1=bbox[3], page=region.page, source="ocr")
            )
        return words

    def _get_detector(self) -> LineDetector:
        if self._detector is None:
            self._detector = _PaddleLineDetector()
        return self._detector

    def _get_recognizer(self) -> TextRecognizer:
        if self._recognizer is None:
            self._recognizer = _VietOCRRecognizer()
        return self._recognizer


def _crop(image: Any, bbox: Bbox) -> Any:
    x0, y0, x1, y1 = (int(round(v)) for v in bbox)
    return image[y0:y1, x0:x1]


def _to_absolute(local_bbox: Bbox, region_bbox: Bbox) -> Bbox:
    rx0, ry0, _, _ = region_bbox
    lx0, ly0, lx1, ly1 = local_bbox
    return (rx0 + lx0, ry0 + ly0, rx0 + lx1, ry0 + ly1)


class _PaddleLineDetector:
    """Lazily-loaded PaddleOCR text-DETECTION-only pipeline. The exact
    class name (`TextDetection`) matches recent PaddleOCR/PaddleX releases;
    pin/adjust in `contract-ocr-lab[paddle]` if a different installed
    version renames it."""

    def __init__(self) -> None:
        self._model: Any = None

    def _load(self) -> Any:
        if self._model is None:
            try:
                from paddleocr import TextDetection
            except ImportError as exc:
                raise EngineUnavailable(
                    "paddleocr is not installed (pip install 'contract-ocr-lab[paddle]')"
                ) from exc
            self._model = TextDetection()
        return self._model

    def detect(self, image: Any) -> list[Bbox]:
        model = self._load()
        boxes: list[Bbox] = []
        for item in model.predict(image):
            for poly in item.get("dt_polys", []):
                xs = [point[0] for point in poly]
                ys = [point[1] for point in poly]
                boxes.append((min(xs), min(ys), max(xs), max(ys)))
        return boxes


class _VietOCRRecognizer:
    """Lazily-loaded VietOCR recognizer, run on CPU by default."""

    def __init__(self) -> None:
        self._predictor: Any = None

    def _load(self) -> Any:
        if self._predictor is None:
            try:
                from vietocr.tool.config import Cfg
                from vietocr.tool.predictor import Predictor
            except ImportError as exc:
                raise EngineUnavailable(
                    "vietocr is not installed (pip install 'contract-ocr-lab[vietocr]')"
                ) from exc
            config = Cfg.load_config_from_name("vgg_transformer")
            config["device"] = "cpu"
            self._predictor = Predictor(config)
        return self._predictor

    def recognize(self, crop: Any) -> str:
        predictor = self._load()
        from PIL import Image

        return predictor.predict(Image.fromarray(crop))
