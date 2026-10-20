"""Builders for constructing `Word`/`Fragment` fixtures without real PDFs."""

from __future__ import annotations

from typing import Literal

from contract_ocr.table_reconstruct import Fragment, Word
from contract_ocr.table_reconstruct.types import Bbox

# Default 3-column layout: STT | Ten hang hoa | Thanh tien.
DEFAULT_COLUMNS: tuple[tuple[float, float], ...] = ((50.0, 80.0), (100.0, 260.0), (300.0, 420.0))
DEFAULT_PAGE_BBOX: Bbox = (0.0, 0.0, 500.0, 800.0)
LINE_HEIGHT = 12.0
ROW_GAP = 8.0

WordSource = Literal["native", "ocr", "vision"]


def word(
    text: str,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    *,
    page: int = 1,
    source: WordSource = "native",
) -> Word:
    return Word(text=text, x0=x0, y0=y0, x1=x1, y1=y1, page=page, source=source)


def line_words(
    cells: list[str],
    y0: float,
    *,
    columns: tuple[tuple[float, float], ...] = DEFAULT_COLUMNS,
    page: int = 1,
    height: float = LINE_HEIGHT,
    source: WordSource = "native",
) -> list[Word]:
    """One physical line's words: `cells[i]` (may be `""`) becomes one word
    filling most of `columns[i]`'s x-range, at height `y0..y0+height`."""
    words: list[Word] = []
    for (x0col, x1col), text in zip(columns, cells):
        if not text:
            continue
        width = min(len(text) * 7.0 + 4.0, x1col - x0col)
        words.append(word(text, x0col, y0, x0col + width, y0 + height, page=page, source=source))
    return words


def table_words(
    rows: list[list[str]],
    *,
    columns: tuple[tuple[float, float], ...] = DEFAULT_COLUMNS,
    start_y: float = 10.0,
    row_height: float = LINE_HEIGHT,
    row_gap: float = ROW_GAP,
    page: int = 1,
) -> list[Word]:
    """Stack `rows` (each a list of per-column cell text) top to bottom at a
    constant row pitch. For a logical row that wraps onto 2-3 physical
    lines, pass one `rows` entry per physical line and leave the anchor
    (first) column blank on the continuation lines.
    """
    words: list[Word] = []
    y = start_y
    for cells in rows:
        words.extend(line_words(cells, y, columns=columns, page=page, height=row_height))
        y += row_height + row_gap
    return words


def fragment(
    doc_id: str,
    page: int,
    rows: list[list[str]],
    *,
    columns: tuple[tuple[float, float], ...] = DEFAULT_COLUMNS,
    bbox: Bbox = DEFAULT_PAGE_BBOX,
    start_y: float = 10.0,
    row_height: float = LINE_HEIGHT,
    row_gap: float = ROW_GAP,
) -> Fragment:
    words = table_words(
        rows,
        columns=columns,
        start_y=start_y,
        row_height=row_height,
        row_gap=row_gap,
        page=page,
    )
    return Fragment(doc_id=doc_id, page=page, bbox=bbox, words=words)
