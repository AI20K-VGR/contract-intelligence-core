"""Output contract: `document_structure.json`.

Every reconstructed object keeps `source_blocks` pointing back to the raw
`(page, block_id)` it came from — see `provenance.py`. Nothing here is ever
built from text that cannot be traced to a source block.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ..models import Relationship, ResolutionMethod, SourceBlockRef

RECONSTRUCTION_VERSION = "1.0.0"


class ReconstructionInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    was_merged: bool = False
    method: ResolutionMethod
    confidence: float = Field(ge=0, le=1)


class Clause(BaseModel):
    """One node of the clause tree (Điều / Khoản / Điểm / sub-điểm / ...)."""

    model_config = ConfigDict(extra="forbid")

    clause_id: str
    parent_id: str | None
    level: int = Field(ge=1)
    marker: str | None = None
    title: str | None = None
    text: str
    page_start: int
    page_end: int
    source_blocks: list[SourceBlockRef]
    reconstruction: ReconstructionInfo
    children: list["Clause"] = Field(default_factory=list)


Clause.model_rebuild()


class TableRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    values: list[str]
    source_pages: list[int]
    source_blocks: list[SourceBlockRef] = Field(default_factory=list)


class Table(BaseModel):
    model_config = ConfigDict(extra="forbid")

    table_id: str
    page_start: int
    page_end: int
    columns: list[str]
    rows: list[TableRow]
    repeated_header_blocks: list[SourceBlockRef] = Field(default_factory=list)


class ReviewItem(BaseModel):
    """A boundary the pipeline refused to resolve automatically (section 15)."""

    model_config = ConfigDict(extra="forbid")

    status: str = "NEEDS_REVIEW"
    previous_page: int
    next_page: int
    possible_relationships: list[Relationship]
    source_blocks: list[SourceBlockRef]
    confidence: float = Field(ge=0, le=1)


class DocumentMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_pages: int = Field(ge=0)
    reconstruction_version: str = RECONSTRUCTION_VERSION


class ReconstructedDocument(BaseModel):
    """The final `document_structure.json` payload."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    sections: list[Clause] = Field(default_factory=list)
    clauses: list[Clause] = Field(default_factory=list)
    tables: list[Table] = Field(default_factory=list)
    review_items: list[ReviewItem] = Field(default_factory=list)
    metadata: DocumentMetadata
