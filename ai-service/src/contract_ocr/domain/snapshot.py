"""AI1 -> AI2 OCR handoff contract (schema_version "ai1.snapshot.v1").

This is the frozen external contract described in the AI1 OCR snapshot handoff
request: AI2/backend/frontend build fact extraction, citation and bbox-audit
tooling against this shape. It is intentionally kept separate from the internal
benchmarking schema in `domain/entities.py` (Document/Page/Line/Word), which
exists to compare OCR engines and may change shape freely without breaking this
contract. `application/use_cases/build_snapshot.py` converts one into the other.
"""

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

SNAPSHOT_SCHEMA_VERSION = "ai1.snapshot.v1"

DocumentRole = Literal["contract", "annex"]
SnapshotInputType = Literal["TEXT_LAYER", "SCANNED_OCR", "MIXED"]
PageStatus = Literal["SUCCESS", "PARTIAL", "FAILED"]


def _check_bbox_normalized(box: list[float]) -> list[float]:
    if len(box) != 4:
        raise ValueError("bbox_normalized must have exactly 4 values [x0, y0, x1, y1]")
    x0, y0, x1, y1 = box
    if not (0 <= x0 < x1 <= 1) or not (0 <= y0 < y1 <= 1):
        raise ValueError("bbox_normalized requires 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1")
    return box


NormalizedBBox = Annotated[
    list[float], Field(min_length=4, max_length=4), AfterValidator(_check_bbox_normalized)
]


class SnapshotEntity(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class EngineInfo(SnapshotEntity):
    name: str
    version: str


class PageImageRef(SnapshotEntity):
    uri: str
    width_px: int = Field(gt=0)
    height_px: int = Field(gt=0)


class SnapshotWord(SnapshotEntity):
    word_id: str
    line_id: str
    text: str
    line_char_start: int = Field(ge=0)
    line_char_end: int = Field(ge=0)
    bbox_normalized: NormalizedBBox
    confidence: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def _ordered_offsets(self) -> "SnapshotWord":
        if self.line_char_end <= self.line_char_start:
            raise ValueError("line_char_end must be greater than line_char_start")
        return self


class SnapshotLine(SnapshotEntity):
    line_id: str
    text: str
    page_char_start: int = Field(ge=0)
    page_char_end: int = Field(ge=0)
    bbox_normalized: NormalizedBBox
    word_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _ordered_offsets(self) -> "SnapshotLine":
        if self.page_char_end <= self.page_char_start:
            raise ValueError("page_char_end must be greater than page_char_start")
        return self


class SnapshotBlock(SnapshotEntity):
    """Recommended (not required) heading/paragraph grouping; see handoff §4.

    Not yet populated by BuildSnapshot in this version — AI2 may merge line
    bboxes into clause-region bboxes itself in the interim, as the handoff
    request explicitly allows.
    """

    block_id: str
    type: Literal["heading", "paragraph"]
    line_ids: list[str]
    reading_order: int = Field(ge=0)
    bbox_normalized: NormalizedBBox


class Cell(SnapshotEntity):
    cell_id: str
    text: str
    bbox_normalized: NormalizedBBox


class Row(SnapshotEntity):
    row_id: str
    cells: list[Cell]


class Table(SnapshotEntity):
    table_id: str
    bbox_normalized: NormalizedBBox
    rows: list[Row]


class SnapshotPage(SnapshotEntity):
    page_number: int = Field(ge=1)
    status: PageStatus
    input_type: SnapshotInputType
    source_page_width: float = Field(gt=0)
    source_page_height: float = Field(gt=0)
    rotation_degrees: int = 0
    page_image_ref: PageImageRef | None = None
    text: str = ""
    lines: list[SnapshotLine] = Field(default_factory=list)
    words: list[SnapshotWord] = Field(default_factory=list)
    blocks: list[SnapshotBlock] = Field(default_factory=list)
    tables: list[Table] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None

    @model_validator(mode="after")
    def _consistent_with_status(self) -> "SnapshotPage":
        if self.status == "FAILED" and not self.error:
            raise ValueError("FAILED pages must carry an error message")
        if self.status != "FAILED" and self.error:
            raise ValueError("only FAILED pages may carry an error message")
        if (
            self.status == "SUCCESS"
            and not self.text.strip()
            and not self.lines
            and "blank_page" not in self.warnings
        ):
            raise ValueError("empty SUCCESS page must carry a 'blank_page' warning")
        return self


class DocumentSnapshot(SnapshotEntity):
    schema_version: Literal["ai1.snapshot.v1"] = SNAPSHOT_SCHEMA_VERSION
    snapshot_id: str = Field(min_length=1)
    source_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    dossier_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    document_role: DocumentRole
    input_type: SnapshotInputType
    engine: EngineInfo
    page_count: int = Field(ge=0)
    processing_ms: float = Field(ge=0)
    pages: list[SnapshotPage] = Field(default_factory=list)

    @model_validator(mode="after")
    def _page_count_matches(self) -> "DocumentSnapshot":
        if self.page_count != len(self.pages):
            raise ValueError("page_count must match len(pages)")
        return self


class DossierDocumentRef(SnapshotEntity):
    document_id: str
    filename: str
    document_role: DocumentRole


class DossierManifest(SnapshotEntity):
    dossier_id: str = Field(min_length=1)
    documents: list[DossierDocumentRef]
