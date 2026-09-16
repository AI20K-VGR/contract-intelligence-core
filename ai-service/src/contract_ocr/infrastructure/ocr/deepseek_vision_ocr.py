import base64
import os
from io import BytesIO
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
from PIL import Image

from contract_ocr.application.ports.ocr_engine import EngineUnavailable, OCREngine
from contract_ocr.domain.entities import Context, Line, OCRResult
from contract_ocr.infrastructure.ocr.prompts import OCR_SYSTEM_PROMPT

DEFAULT_MODEL = "deepseek-flash"
DEFAULT_BASE_URL = "https://api.deepseek.com"


class DeepSeekVisionOCREngine(OCREngine):
    """Sends the rendered page image to DeepSeek's hosted vision API (OpenAI-compatible
    Chat Completions endpoint, model deepseek-flash). Not local: page images leave this
    machine. Only use with non-confidential documents.

    This is a different underlying model from the local, GPU-only deepseek-ai/DeepSeek-
    OCR-2 adapter used by the CLI benchmark (deepseek_ocr.py) — DeepSeek's hosted API
    does not currently expose that OCR-specialized model, only its general-purpose
    vision-capable chat model. Reuses the `openai` SDK since the API is wire-compatible.
    """

    name = "deepseek_vision"

    def __init__(self, **config: Any) -> None:
        self.config = config
        self.model = config.get("model", DEFAULT_MODEL)
        self.prompt = config.get("prompt", OCR_SYSTEM_PROMPT)
        self.runtime_info = {"provider": "deepseek", "model": self.model}
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
                raise RuntimeError("DeepSeek vision engine disabled in configuration")
            api_key = self.config.get("api_key") or os.environ.get("DEEPSEEK_API_KEY")
            if not api_key:
                raise RuntimeError("DEEPSEEK_API_KEY is not set")
            from openai import OpenAI

            self._client = OpenAI(
                api_key=api_key, base_url=self.config.get("base_url", DEFAULT_BASE_URL)
            )
        except Exception as exc:
            self._unavailable = f"DeepSeek vision unavailable: {type(exc).__name__}: {exc}"
            raise EngineUnavailable(self._unavailable) from exc
        finally:
            self.initialization_ms = (perf_counter() - start) * 1000

    def recognize_page(self, page_image: np.ndarray, context: Context) -> OCRResult:
        self._load()
        image = Image.fromarray(page_image).convert("RGB")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        data_url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")

        # deepseek-flash defaults to thinking mode (effort "high"), which can burn the
        # entire max_tokens budget on reasoning_content before writing any answer,
        # leaving finish_reason="length" and an empty message.content. OCR transcription
        # doesn't need multi-step reasoning, so this is disabled unless overridden.
        thinking_enabled = self.config.get("thinking", False)
        response = self._client.chat.completions.create(
            model=self.model,
            temperature=0,
            max_tokens=self.config.get("max_tokens", 4096),
            extra_body={"thinking": {"type": "enabled" if thinking_enabled else "disabled"}},
            messages=[
                {"role": "system", "content": self.prompt},
                {
                    "role": "user",
                    "content": [{"type": "image_url", "image_url": {"url": data_url}}],
                },
            ],
        )
        text = response.choices[0].message.content or ""

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
