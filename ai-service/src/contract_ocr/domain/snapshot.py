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
# Section 15: a page's table result must never collapse "checked, none found"
# and "not checked at all" into the same empty list.
# NOT_CHECKED: no table detector ran for this page's input type yet (today:
#     every SCANNED_OCR/MIXED page -- see infrastructure/pdf/pymupdf_extractor.py).
# NOT_PRESENT: the detector ran and found no table.
# DETECTED: the detector ran and `tables[]` holds the result.
# Deliberately not yet including STRUCTURE_UNAVAILABLE/NEEDS_REVIEW/FAILED from
# the target design: nothing in this codebase can produce them honestly yet
# (no scanned-page detector, no partial-reconstruction recovery path) -- adding
# them now would describe a capability that does not exist.
TableStatus = Literal["NOT_CHECKED", "NOT_PRESENT", "DETECTED"]
# How a bbox_normalized value was obtained (see contract_ocr.domain.enums.GeometryProvenance,
# mirrored here as a plain Literal to keep this module's external contract self-contained).
# MEASURED: directly measured (native glyph rects, a CV detector's own output).
# DERIVED: computed from other trusted geometry (e.g. union of measured word boxes).
# CLAIMED: reported by a model. AI2 must not treat CLAIMED geometry as citation-grade.
GeometryProvenance = Literal["MEASURED", "DERIVED", "CLAIMED"]


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
    geometry_provenance: GeometryProvenance
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
    geometry_provenance: GeometryProvenance
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
    geometry_provenance: GeometryProvenance


class Cell(SnapshotEntity):
    cell_id: str
    text: str
    # A merged/spanning cell a detector could not resolve to its own rect has no
    # bbox rather than a fabricated one (section 15: absence, not a guess).
    bbox_normalized: NormalizedBBox | None = None
    geometry_provenance: GeometryProvenance | None = None

    @model_validator(mode="after")
    def _provenance_consistency(self) -> "Cell":
        if (self.bbox_normalized is None) != (self.geometry_provenance is None):
            raise ValueError(
                "geometry_provenance must be set if and only if bbox_normalized is set"
            )
        return self


class Row(SnapshotEntity):
    row_id: str
    cells: list[Cell]


class Table(SnapshotEntity):
    table_id: str
    bbox_normalized: NormalizedBBox
    geometry_provenance: GeometryProvenance
    header: list[str] = Field(default_factory=list)
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
    table_status: TableStatus = "NOT_CHECKED"
    tables: list[Table] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None

    @model_validator(mode="after")
    def _table_status_consistency(self) -> "SnapshotPage":
        if self.table_status == "DETECTED" and not self.tables:
            raise ValueError("table_status=DETECTED requires a non-empty tables[]")
        if self.table_status != "DETECTED" and self.tables:
            raise ValueError("tables[] must be empty unless table_status=DETECTED")
        return self

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


class TableContinuityLink(SnapshotEntity):
    """One cross-page continuity decision (section 11) between the last table on one
    page and the first table on the next. Does not merge rows/cells -- only records the
    decision and why, same as `backend/app/tables.py`'s own `link_continuations`
    (independently landing on the same "link, don't merge" answer). No LLM gray-zone
    agent produced this in the current build (deterministic only -- see
    docs/ai1-decisions.md D8); MERGE/SPLIT come from hard guards and a deterministic
    score, anything in between is NEEDS_REVIEW rather than a guess.
    """

    from_table_id: str
    from_page: int = Field(ge=1)
    to_table_id: str
    to_page: int = Field(ge=1)
    decision: Literal["MERGE", "SPLIT", "NEEDS_REVIEW"]
    confidence: float = Field(ge=0, le=1)
    reason_codes: list[str] = Field(default_factory=list)


class StructuralNode(SnapshotEntity):
    """One node of the document's clause hierarchy (section 8): Document ->
    Section/Article -> Clause -> Point. Built by `application.use_cases.
    build_structure.BuildStructure` from real OCR lines — every node resolves
    to the `line_ids` it was built from, which resolve to real `SnapshotLine`s
    on a real page. See that module's docstring for the current limitation
    (no cross-page merging of a clause body split by a page break yet).
    """

    node_id: str = Field(min_length=1)
    # UNMARKED: text with no recognized numbering marker at all, kept as its own
    # node rather than discarded (section 15: absence must stay distinguishable
    # from silently-dropped content).
    type: Literal["ARTICLE", "CLAUSE", "POINT", "UNMARKED"]
    label_raw: str | None = None
    label_normalized: str = Field(min_length=1)
    parent_id: str | None = None
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    line_ids: list[str] = Field(default_factory=list)
    bbox_normalized: NormalizedBBox | None = None
    geometry_provenance: GeometryProvenance | None = None

    @model_validator(mode="after")
    def _provenance_consistency(self) -> "StructuralNode":
        if (self.bbox_normalized is None) != (self.geometry_provenance is None):
            raise ValueError(
                "geometry_provenance must be set if and only if bbox_normalized is set"
            )
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
    nodes: list[StructuralNode] = Field(default_factory=list)
    table_continuity: list[TableContinuityLink] = Field(default_factory=list)

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
