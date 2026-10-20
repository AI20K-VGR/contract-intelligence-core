"""PyMuPDF native-text adapter — a digital PDF page needs no OCR at all."""

from __future__ import annotations

import pymupdf

from contract_ocr.table_reconstruct.types import Bbox, Word

from .types import Region


class NativeAdapter:
    """Wraps `page.get_text("words")`. PyMuPDF already gives word-level text
    with a trustworthy bbox for a digital PDF page, so — unlike `OcrAdapter`
    and `VisionAdapter` — there is no detection, recognition or vision call
    here at all, just filtering to `region` and rotation handling.
    """

    def extract(self, page: pymupdf.Page, region: Region) -> list[Word]:
        words: list[Word] = []
        for raw in page.get_text("words", sort=True):
            text = raw[4]
            if not text.strip():
                continue
            # `get_text("words")` returns coordinates in the page's
            # unrotated space; apply rotation_matrix before comparing
            # against `region.bbox`, which is expressed in the same
            # (rotated/visual) space layout detection would report —
            # mirrors `infrastructure/pdf/pymupdf_extractor.py`.
            rect = pymupdf.Rect(raw[:4]) * page.rotation_matrix
            if not _center_within(rect, region.bbox):
                continue
            words.append(
                Word(
                    text=text,
                    x0=rect.x0,
                    y0=rect.y0,
                    x1=rect.x1,
                    y1=rect.y1,
                    page=region.page,
                    source="native",
                )
            )
        return words


def _center_within(rect: pymupdf.Rect, bbox: Bbox) -> bool:
    cx, cy = (rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2
    x0, y0, x1, y1 = bbox
    return x0 <= cx <= x1 and y0 <= cy <= y1
