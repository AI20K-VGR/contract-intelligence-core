from __future__ import annotations

import os
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
from PIL import Image

from benchmark.schemas import ImageInfo, OCRPageResult, OCRTable
from contract_ocr.domain.entities import Context
from contract_ocr.infrastructure.ocr.mistral_ocr import MistralOCREngine


class MistralUnavailable(RuntimeError):
    pass


class MistralBenchmarkProvider:
    """Thin adapter from the project's Mistral engine to benchmark output schemas."""

    def __init__(self, config: dict[str, Any], *, dpi: int) -> None:
        if not os.getenv("MISTRAL_API_KEY"):
            raise MistralUnavailable("MISTRAL_API_KEY is not set")
        self.engine = MistralOCREngine(**config)
        self.model = self.engine.model
        self.dpi = dpi

    def process_page(
        self,
        image_path: Path,
        *,
        document_id: str,
        page_number: int,
    ) -> OCRPageResult:
        image = np.asarray(Image.open(image_path).convert("RGB"))
        tick = perf_counter()
        try:
            result = self.engine.recognize_page(
                image,
                Context(
                    document_id=document_id,
                    page=page_number,
                    output_dir=str(image_path.parent / "raw"),
                ),
            )
        except Exception as exc:
            if "API_KEY" in str(exc) or "unavailable" in str(exc).lower():
                raise MistralUnavailable(str(exc)) from exc
            raise
        tables = []
        for table in result.tables:
            rows = [list(table.header)] if table.header else []
            rows.extend([[cell.text for cell in row.cells] for row in table.rows])
            tables.append(OCRTable(table_id=table.table_id, rows=rows, pages=[page_number]))
        return OCRPageResult(
            page_number=page_number,
            image=ImageInfo(
                width=image.shape[1],
                height=image.shape[0],
                dpi=self.dpi,
                path=str(image_path),
            ),
            text="\n".join(line.text for line in result.lines),
            tables=tables,
            latency_ms=(perf_counter() - tick) * 1000,
        )


def make_mistral_provider(
    config: dict[str, Any],
    *,
    dpi: int,
) -> MistralBenchmarkProvider:
    return MistralBenchmarkProvider(config, dpi=dpi)
