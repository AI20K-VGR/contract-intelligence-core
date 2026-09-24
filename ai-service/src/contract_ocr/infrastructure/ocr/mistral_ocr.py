import base64
import os
from io import BytesIO
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
from PIL import Image

from contract_ocr.application.ports.ocr_engine import EngineUnavailable, OCREngine
from contract_ocr.domain.bbox import BBox
from contract_ocr.domain.entities import Context, Line, OCRResult, Table
from contract_ocr.domain.enums import GeometryProvenance
from contract_ocr.domain.headings import is_annex_heading
from contract_ocr.infrastructure.observability import observation, response_usage
from contract_ocr.infrastructure.ocr.markdown_tables import (
    build_table_from_block,
    clean_markdown_text,
)

# mistral-ocr-4 is Mistral's dedicated Document AI OCR model (pinned, not the
# `mistral-ocr-latest` alias, so behavior doesn't shift under this codebase when Mistral
# moves the alias) — see https://docs.mistral.ai/capabilities/OCR/basic_ocr/. Confirmed
# against GET /v1/models as a real, currently-served model id (alongside mistral-ocr-4-0,
# mistral-ocr-4-1, mistral-ocr-3, mistral-ocr-3-0, mistral-ocr-2512, mistral-ocr-latest).
# Model naming moves fast; override with the `model` config key if this id is retired.
DEFAULT_MODEL = "mistral-ocr-4"


def _block_bbox(block: Any, width: float, height: float) -> BBox:
    """Normalizes one OCR block's real (measured, pixel) bounding box to [0, 1]
    against the page's own render dimensions -- mirrors
    `backend/app/document_processing.py::_mistral_block_bbox`."""
    return BBox.normalize(
        [block.top_left_x, block.top_left_y, block.bottom_right_x, block.bottom_right_y],
        width,
        height,
    )


class MistralOCREngine(OCREngine):
    """Sends the rendered page image to Mistral's dedicated OCR endpoint (`POST /v1/ocr`,
    `client.ocr.process`). Not local: page images leave this machine. Only use with
    non-confidential documents.

    Unlike the OpenAI/Gemini engines in this package, this is **not** a chat-
    completion vision prompt — the OCR endpoint takes no system prompt at all, so this
    engine does not use (and cannot enforce) `infrastructure/ocr/prompts.OCR_SYSTEM_PROMPT`'s
    "never guess, mark [illegible]" instructions. Its accuracy/hallucination behavior is
    whatever Mistral's OCR model does natively; this has not been separately verified the
    way the shared prompt was against the other three engines.

    Requests `include_blocks=True, confidence_scores_granularity="block"` (mirrors
    `backend/app/document_processing.py::_mistral_vision_page`, the same call shape
    already proven in that production pipeline): every block Mistral's own layout
    detector finds comes back with a REAL (measured) pixel bbox and a confidence
    score, not an evenly-split guess. A `type == "table"` block's markdown content
    (literal `| cell | cell |` syntax) is parsed into a real `Table` by
    `infrastructure/ocr/markdown_tables.py` and returned via `OCRResult.tables` — see
    that module for why each CELL's own bbox (an even split of the block's real bbox)
    is `GeometryProvenance.CLAIMED` while the table's own bbox stays `MEASURED`. A
    `Table`'s `heading_before` is set to the nearest preceding text block that reads
    as a new section/annex heading (`domain.headings.is_annex_heading`), for
    `table_continuity.py`'s cross-page hard guard. Raw markdown is still written to
    `raw.md` per page like every other engine.

    `table_format` is left at its API default (`None`/omitted = tables stay inline in
    `page.markdown`/`page.blocks`), **not** `"markdown"` or `"html"` — those two values,
    confirmed live against a real scanned table, pull the table OUT of `page.markdown`
    into a separate `page.tables[i].content` field (a field of Mistral's own response,
    distinct from this module's `OCRResult.tables`) and leave only a dead-looking
    placeholder link (e.g. `[tbl-0.md](tbl-0.md)`) in its place, which
    `markdown_tables.build_table_from_block` cannot parse — silently dropping every
    table's actual content, the opposite of this engine's purpose.
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

        with observation(
            "transcribe-page",
            as_type="generation",
            input={
                "document_id": context.document_id,
                "page_number": context.page,
                "image_width": image.width,
                "image_height": image.height,
            },
            metadata={"provider": "mistral", "feature": "document-ocr"},
            model=self.model,
            model_parameters={
                "include_blocks": True,
                "confidence_scores_granularity": "block",
            },
        ) as generation:
            response = self._client.ocr.process(
                model=self.model,
                document={"type": "image_url", "image_url": data_url},
                table_format=self.table_format,
                include_blocks=True,
                confidence_scores_granularity="block",
            )
            page = response.pages[0] if response.pages else None
            text = (page.markdown if page else "") or ""
            if generation is not None:
                generation.update(
                    output={
                        "page_count": len(response.pages or []),
                        "character_count": len(text),
                        "block_count": len((page.blocks if page else None) or []),
                    },
                    usage_details=response_usage(response),
                )

        directory = Path(context.output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "raw.md"
        path.write_text(text, encoding="utf-8")

        # Content and geometry deliberately take separate paths.  The full-page
        # markdown is the content source of truth; blocks are used only to map
        # positions onto that text.  A markdown line that cannot be matched to
        # a block is retained with no bbox instead of being dropped.
        block_lines: list[tuple[str, BBox, float | None]] = []
        tables: list[Table] = []
        last_heading: str | None = None
        for block in (page.blocks if page else None) or []:
            bbox = _block_bbox(block, page.dimensions.width, page.dimensions.height)
            scores = block.confidence_scores
            confidence = scores.average_content_confidence_score if scores else None
            content = block.content or ""

            clean_lines = [clean_markdown_text(line) for line in content.splitlines()]
            clean_lines = [line for line in clean_lines if line]
            block_lines.extend((line, bbox, confidence) for line in clean_lines)

            if block.type == "table":
                table = build_table_from_block(
                    table_id=f"{context.document_id}-p{context.page:03d}-t{len(tables) + 1:03d}",
                    block_bbox=bbox,
                    block_content=content,
                    heading_before=last_heading,
                )
                if table is not None:
                    tables.append(table)
                continue

            last_heading = next(
                (line for line in reversed(clean_lines) if is_annex_heading(line)), last_heading
            )

        lines: list[Line] = []
        unused_block_lines = list(block_lines)
        for raw_line in text.splitlines():
            line_text = clean_markdown_text(raw_line)
            if not line_text:
                continue
            match_index = next(
                (
                    i
                    for i, (candidate, _, _) in enumerate(unused_block_lines)
                    if candidate == line_text
                ),
                None,
            )
            if match_index is None:
                lines.append(
                    Line(
                        line_id=f"{context.document_id}-p{context.page:03d}-l{len(lines) + 1:04d}",
                        text=line_text,
                    )
                )
                continue
            _, bbox, confidence = unused_block_lines.pop(match_index)
            lines.append(
                Line(
                    line_id=f"{context.document_id}-p{context.page:03d}-l{len(lines) + 1:04d}",
                    text=line_text,
                    bbox=bbox,
                    geometry_provenance=GeometryProvenance.MEASURED,
                    confidence=confidence,
                )
            )

        return OCRResult(
            lines=lines, tables=tables, raw_markdown=text, raw_output_path=str(path.resolve())
        )
