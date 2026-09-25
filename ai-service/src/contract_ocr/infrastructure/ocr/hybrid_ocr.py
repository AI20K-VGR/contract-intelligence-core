"""Splits one page's OCR between two engines instead of picking a single
best-overall engine: `text_engine` (OpenAI's vision model) reads prose --
its Vietnamese diacritic accuracy is measurably better than Mistral's
dedicated OCR endpoint on this codebase's documents -- while `table_engine`
(Mistral) supplies table structure and bounding-box geometry, since it is
the only engine here whose blocks carry a real, measured pixel bbox and
whose table markdown `markdown_tables.build_table_from_block` can parse.

The two engines run independently against the same page image; nothing is
cross-matched line-by-line, so a failure or mistake in one can never corrupt
the other's output.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from contract_ocr.application.ports.ocr_engine import EngineUnavailable, OCREngine
from contract_ocr.domain.entities import Context, OCRResult, Table

logger = logging.getLogger(__name__)


class HybridOCREngine(OCREngine):
    """`text_engine` is the source of truth for `lines`/`raw_markdown` (the
    prose a human or downstream clause extractor reads). `table_engine` is
    the source of truth for `tables` only -- if it fails or is unavailable,
    tables come back empty rather than failing the whole page, and
    `ProcessDocument`'s own pixel-based table detector already runs as a
    fallback in that case (see `process_document.py`), so nothing is lost.
    """

    def __init__(self, text_engine: OCREngine, table_engine: OCREngine) -> None:
        self.text_engine = text_engine
        self.table_engine = table_engine
        self.name = text_engine.name
        self.model = text_engine.model
        self.runtime_info = {
            "text_engine": text_engine.runtime_info,
            "table_engine": table_engine.runtime_info,
        }

    def recognize_page(self, page_image: Any, context: Context) -> OCRResult:
        with ThreadPoolExecutor(max_workers=2) as pool:
            text_future = pool.submit(self.text_engine.recognize_page, page_image, context)
            table_future = pool.submit(self._safe_tables, page_image, context)
            text_result = text_future.result()
            tables = table_future.result()

        return OCRResult(
            lines=text_result.lines,
            tables=tables,
            raw_markdown=text_result.raw_markdown,
            raw_output_path=text_result.raw_output_path,
        )

    def _safe_tables(self, page_image: Any, context: Context) -> list[Table]:
        try:
            return self.table_engine.recognize_page(page_image, context).tables
        except EngineUnavailable as exc:
            logger.warning(
                "ocr.table_engine_unavailable document_id=%s page=%s engine=%s error=%s",
                context.document_id,
                context.page,
                self.table_engine.name,
                exc,
            )
        except Exception:
            logger.exception(
                "ocr.table_engine_failed document_id=%s page=%s engine=%s",
                context.document_id,
                context.page,
                self.table_engine.name,
            )
        return []
