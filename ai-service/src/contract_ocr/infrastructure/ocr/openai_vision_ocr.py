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

# gpt-5.6-terra is OpenAI's mid-tier GPT-5.6 model (~$2.00/1M input, $12.00/1M output as
# of writing) with vision support — between the flagship gpt-5.6-sol and the budget
# gpt-5.6-luna. Model naming moves fast; override with the `model` config key if this no
# longer matches https://developers.openai.com/api/docs/models.
DEFAULT_MODEL = "gpt-5.6-terra"


class OpenAIVisionOCREngine(OCREngine):
    """Sends the rendered page image to an OpenAI vision model. Not local: page images
    leave this machine. Only use with non-confidential documents."""

    name = "openai_vision"

    def __init__(self, **config: Any) -> None:
        self.config = config
        self.model = config.get("model", DEFAULT_MODEL)
        self.prompt = config.get("prompt", OCR_SYSTEM_PROMPT)
        self.runtime_info = {"provider": "openai", "model": self.model}
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
                raise RuntimeError("OpenAI vision engine disabled in configuration")
            api_key = self.config.get("api_key") or os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY is not set")
            from openai import OpenAI

            client_kwargs: dict[str, Any] = {"api_key": api_key}
            if self.config.get("base_url"):
                client_kwargs["base_url"] = self.config["base_url"]
            self._client = OpenAI(**client_kwargs)
        except Exception as exc:
            self._unavailable = f"OpenAI vision unavailable: {type(exc).__name__}: {exc}"
            raise EngineUnavailable(self._unavailable) from exc
        finally:
            self.initialization_ms = (perf_counter() - start) * 1000

    def recognize_page(self, page_image: np.ndarray, context: Context) -> OCRResult:
        self._load()
        image = Image.fromarray(page_image).convert("RGB")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        data_url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")

        # gpt-5.6+ rejects the legacy max_tokens param (needs max_completion_tokens) and
        # rejects temperature overrides other than its default (1), so both are only
        # sent if explicitly configured rather than hardcoded.
        kwargs: dict[str, Any] = {
            "max_completion_tokens": self.config.get("max_tokens", 4096),
        }
        if "temperature" in self.config:
            kwargs["temperature"] = self.config["temperature"]
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}},
                    ],
                },
            ],
            **kwargs,
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
