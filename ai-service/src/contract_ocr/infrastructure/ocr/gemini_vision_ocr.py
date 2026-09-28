import os
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
from PIL import Image

from contract_ocr.application.ports.ocr_engine import EngineUnavailable, OCREngine
from contract_ocr.domain.entities import Context, Line, OCRResult
from contract_ocr.infrastructure.observability import observation, response_usage
from contract_ocr.infrastructure.ocr.prompts import OCR_SYSTEM_PROMPT

# Model naming moves fast; override with GEMINI_MODEL or the `model` config key if this
# default no longer matches https://ai.google.dev/gemini-api/docs/models.
DEFAULT_MODEL = "gemini-3-flash-preview"


class GeminiVisionOCREngine(OCREngine):
    """Sends the rendered page image to a Gemini vision model. Not local: page images
    leave this machine. Only use with non-confidential documents."""

    name = "gemini_vision"

    def __init__(self, **config: Any) -> None:
        self.config = config
        self.model = config.get("model") or os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
        self.prompt = config.get("prompt", OCR_SYSTEM_PROMPT)
        self.runtime_info = {"provider": "gemini", "model": self.model}
        self._client = None
        self._unavailable = None

    def _load(self) -> None:
        if self._unavailable:
            raise EngineUnavailable(self._unavailable)
        if self._client is not None:
            return
        start = perf_counter()
        try:
            if not self.config.get("enabled", True):
                raise RuntimeError("Gemini vision engine disabled in configuration")
            api_key = self.config.get("api_key") or os.environ.get("GEMINI_API_KEY")
            if not api_key:
                raise RuntimeError("GEMINI_API_KEY is not set")
            from google import genai

            self._client = genai.Client(api_key=api_key)
        except Exception as exc:
            self._unavailable = f"Gemini vision unavailable: {type(exc).__name__}: {exc}"
            raise EngineUnavailable(self._unavailable) from exc
        finally:
            self.initialization_ms = (perf_counter() - start) * 1000

    def recognize_page(self, page_image: np.ndarray, context: Context) -> OCRResult:
        self._load()
        from google.genai import types

        image = Image.fromarray(page_image).convert("RGB")
        max_output_tokens = self.config.get("max_tokens", 4096)
        with observation(
            "transcribe-page",
            as_type="generation",
            input={
                "document_id": context.document_id,
                "page_number": context.page,
                "image_width": image.width,
                "image_height": image.height,
            },
            metadata={"provider": "google", "feature": "document-ocr"},
            model=self.model,
            model_parameters={"temperature": 0, "max_output_tokens": max_output_tokens},
        ) as generation:
            response = self._client.models.generate_content(
                model=self.model,
                contents=[image],
                config=types.GenerateContentConfig(
                    system_instruction=self.prompt,
                    temperature=0,
                    max_output_tokens=max_output_tokens,
                ),
            )
            text = response.text or ""
            if generation is not None:
                generation.update(
                    output={"character_count": len(text)},
                    usage_details=response_usage(response),
                )

        directory = Path(context.output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "raw.md"
        path.write_text(text, encoding="utf-8")

        lines = [
            Line(line_id=f"{context.document_id}-p{context.page:03d}-l{i:04d}", text=line_text)
            for i, line_text in enumerate(text.splitlines(), 1)
            if line_text.strip()
        ]
        return OCRResult(lines=lines, raw_markdown=text, raw_output_path=str(path.resolve()))
