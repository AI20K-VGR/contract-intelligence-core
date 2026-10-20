"""Small builders for constructing `Block`/`Page` fixtures in tests."""

from __future__ import annotations

from contract_ocr.reconstruction.schemas.block import Block
from contract_ocr.reconstruction.schemas.page import Page


def make_block(
    block_id: str,
    text: str,
    *,
    type: str = "paragraph",
    bbox: tuple[float, float, float, float] = (100.0, 300.0, 1000.0, 350.0),
    confidence: float = 0.98,
    font_size: float | None = 11.0,
    bold: bool | None = False,
    indent_level: int | None = None,
) -> Block:
    return Block(
        block_id=block_id,
        type=type,
        text=text,
        bbox=bbox,
        confidence=confidence,
        font_size=font_size,
        bold=bold,
        indent_level=indent_level,
    )


def make_page(
    document_id: str,
    page: int,
    blocks: list[Block],
    *,
    width: float = 1654.0,
    height: float = 2339.0,
) -> Page:
    return Page(
        document_id=document_id, page=page, width=width, height=height, blocks=tuple(blocks)
    )
