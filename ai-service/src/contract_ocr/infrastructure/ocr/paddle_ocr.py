import json
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from contract_ocr.application.ports.ocr_engine import EngineUnavailable, OCREngine
from contract_ocr.domain.bbox import BBox
from contract_ocr.domain.entities import Context, Line, OCRResult


class PaddleOCREngine(OCREngine):
    name = "paddleocr"

    def __init__(self, **config: Any) -> None:
        self.config = config
        self.model = config.get("model", "PP-OCRv6")
        self.runtime_info = {"device": config.get("device", "cpu")}
        self._engine = None
        self._unavailable = None

    def _load(self) -> None:
        if self._unavailable:
            raise EngineUnavailable(self._unavailable)
        if self._engine is not None:
            return
        start = perf_counter()
        try:
            if not self.config.get("enabled", True):
                raise RuntimeError("Paddle disabled in configuration")
            from paddleocr import PaddleOCR

            self._engine = PaddleOCR(
                ocr_version=self.model,
                device=self.config.get("device", "cpu"),
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
            )
        except Exception as exc:
            self._unavailable = f"Paddle initialization unavailable: {type(exc).__name__}: {exc}"
            raise EngineUnavailable(self._unavailable) from exc
        finally:
            self.initialization_ms = (perf_counter() - start) * 1000

    def recognize_page(self, page_image: np.ndarray, context: Context) -> OCRResult:
        self._load()
        # Paddle ndarray inputs use BGR; renderer/preprocessors use RGB.
        image = page_image[:, :, ::-1].copy() if page_image.ndim == 3 else page_image
        lines, raw = [], []
        for result in self._engine.predict(image):
            payload = result.json
            if isinstance(payload, str):
                payload = json.loads(payload)
            data = payload.get("res", payload)
            raw.append(data)
            for text, score, polygon in zip(
                data["rec_texts"], data["rec_scores"], data["rec_polys"], strict=True
            ):
                points = np.asarray(polygon)
                box = BBox.normalize(
                    [
                        float(points[:, 0].min()),
                        float(points[:, 1].min()),
                        float(points[:, 0].max()),
                        float(points[:, 1].max()),
                    ],
                    page_image.shape[1],
                    page_image.shape[0],
                )
                lines.append(
                    Line(
                        line_id=f"{context.document_id}-p{context.page:03d}-l{len(lines) + 1:04d}",
                        text=text,
                        confidence=float(score),
                        bbox=box,
                    )
                )
        path = Path(context.output_dir) / "raw.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(raw, ensure_ascii=False, default=lambda x: x.tolist()), encoding="utf-8"
        )
        return OCRResult(lines=lines, raw_output_path=str(path.resolve()))
