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

# mistral-ocr-4 is Mistral's dedicated Document AI OCR model (pinned, not the
# `mistral-ocr-latest` alias, so behavior doesn't shift under this codebase when Mistral
# moves the alias) — see https://docs.mistral.ai/capabilities/OCR/basic_ocr/. Confirmed
# against GET /v1/models as a real, currently-served model id (alongside mistral-ocr-4-0,
# mistral-ocr-4-1, mistral-ocr-3, mistral-ocr-3-0, mistral-ocr-2512, mistral-ocr-latest).
# Model naming moves fast; override with the `model` config key if this id is retired.
DEFAULT_MODEL = "mistral-ocr-4"


class MistralOCREngine(OCREngine):
    """Sends the rendered page image to Mistral's dedicated OCR endpoint (`POST /v1/ocr`,
    `client.ocr.process`). Not local: page images leave this machine. Only use with
    non-confidential documents.

    Unlike the OpenAI/Gemini/DeepSeek engines in this package, this is **not** a chat-
    completion vision prompt — the OCR endpoint takes no system prompt at all, so this
    engine does not use (and cannot enforce) `infrastructure/ocr/prompts.OCR_SYSTEM_PROMPT`'s
    "never guess, mark [illegible]" instructions. Its accuracy/hallucination behavior is
    whatever Mistral's OCR model does natively; this has not been separately verified the
    way the shared prompt was against the other three engines. The response is also
    genuine Markdown rather than the plain-text-per-line convention the other engines are
    instructed to follow — a real table in the source image ends up as literal
    `| cell | cell |` syntax in `OCRResult.raw_markdown`/the `Line`s built from it, since
    nothing here parses pipe tables back out. That raw markdown is still written to
    `raw.md` per page like every other engine, so it is a legitimate table-to-markdown
    output on its own; it is just not (yet) fed into `extract_scanned_tables.py`'s
    bordered-grid/bbox pipeline, which expects OCR `Line`s, not table markdown.

    `table_format` is left at its API default (`None`/omitted = tables stay inline in
    `page.markdown`), **not** `"markdown"` or `"html"` — those two values, confirmed live
    against a real scanned table, pull the table OUT of `page.markdown` into a separate
    `page.tables[i].content` field and leave only a dead-looking placeholder link (e.g.
    `[tbl-0.md](tbl-0.md)`) in its place. Since `OCRResult` here only carries `raw_markdown`/
    `Line`s (no `tables` field), passing either of those values would silently drop every
    table's actual content — the opposite of this engine's purpose. If a future caller wants
    the structured `page.tables` objects instead, that needs a real `OCRResult`/`OCREngine`
    extension, not a `table_format` override on this constructor.
    """

    name = "mistral_ocr"

    def __init__(self, **config: Any) -> None:
        self.config = config
        self.model = config.get("model", DEFAULT_MODEL)
        self.table_format = config.get("table_format")
        self.runtime_info = {"provider": "mistral", "model": self.model}
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
                raise RuntimeError("Mistral OCR engine disabled in configuration")
            api_key = self.config.get("api_key") or os.environ.get("MISTRAL_API_KEY")
            if not api_key:
                raise RuntimeError("MISTRAL_API_KEY is not set")
            from mistralai.client import Mistral

            self._client = Mistral(api_key=api_key)
        except Exception as exc:
            self._unavailable = f"Mistral OCR unavailable: {type(exc).__name__}: {exc}"
            raise EngineUnavailable(self._unavailable) from exc
        finally:
            self.initialization_ms = (perf_counter() - start) * 1000

    def recognize_page(self, page_image: np.ndarray, context: Context) -> OCRResult:
        self._load()
        image = Image.fromarray(page_image).convert("RGB")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        data_url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")

        response = self._client.ocr.process(
            model=self.model,
            document={"type": "image_url", "image_url": data_url},
            table_format=self.table_format,
        )
        text = response.pages[0].markdown if response.pages else ""

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
