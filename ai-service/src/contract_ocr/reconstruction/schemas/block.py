"""Input contract for a single page-level OCR block.

This mirrors exactly what the page OCR stage emits (`page_NNN.json`).
Reconstruction treats every field here as immutable raw evidence: it is
read, classified and linked, but never rewritten.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Known block types the OCR stage may emit. Not enforced as a strict enum:
# upstream OCR/layout classifiers evolve independently of reconstruction, so
# unrecognized values are accepted and simply treated conservatively (as
# generic content) rather than raising.
HEADING = "heading"
PARAGRAPH = "paragraph"
LIST_ITEM = "list_item"
TABLE_ROW = "table_row"
HEADER = "header"
FOOTER = "footer"
PAGE_NUMBER = "page_number"
WATERMARK = "watermark"
FIGURE = "figure"
SIGNATURE = "signature"

NON_TEXTUAL_TYPES = frozenset({HEADER, FOOTER, PAGE_NUMBER, WATERMARK, FIGURE})


class Block(BaseModel):
    """One OCR-detected content block on one page. Immutable raw evidence."""

    model_config = ConfigDict(extra="allow", frozen=True)

    block_id: str
    type: str
    text: str
    bbox: tuple[float, float, float, float]
    confidence: float = Field(ge=0, le=1)
    font_size: float | None = None
    bold: bool | None = None
    italic: bool | None = None
    indent_level: int | None = None

    @field_validator("bbox", mode="before")
    @classmethod
    def _coerce_bbox(cls, value: object) -> tuple[float, float, float, float]:
        if isinstance(value, list | tuple) and len(value) == 4:
            return tuple(float(v) for v in value)  # type: ignore[return-value]
        raise ValueError("bbox must have exactly 4 numeric values [x0, y0, x1, y1]")

    @property
    def x0(self) -> float:
        return self.bbox[0]

    @property
    def y0(self) -> float:
        return self.bbox[1]

    @property
    def x1(self) -> float:
        return self.bbox[2]

    @property
    def y1(self) -> float:
        return self.bbox[3]

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()
