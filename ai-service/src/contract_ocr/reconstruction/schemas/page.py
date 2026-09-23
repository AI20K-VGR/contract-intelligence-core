"""Input contract for one page's worth of OCR output (`page_NNN.json`)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .block import Block


class Page(BaseModel):
    """Page-level OCR output. Immutable raw evidence for reconstruction."""

    model_config = ConfigDict(extra="allow", frozen=True)

    document_id: str
    page: int = Field(ge=1)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    blocks: tuple[Block, ...] = Field(default_factory=tuple)

    @property
    def meaningful_blocks(self) -> list[Block]:
        """Blocks in reading order with empty text dropped."""
        return [b for b in self.blocks if not b.is_empty]
