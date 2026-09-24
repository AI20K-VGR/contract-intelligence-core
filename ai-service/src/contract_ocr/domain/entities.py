from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .bbox import BBox
from .enums import GeometryProvenance, InputType, Status


class Entity(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Word(Entity):
    word_id: str
    text: str
    confidence: float | None = Field(default=None, ge=0, le=1)
    bbox: BBox | None = None
    geometry_available: bool = False
    # Required whenever bbox is set, forbidden otherwise (see `_provenance_consistency`)
    # so a bbox can never reach a consumer without declaring how it was obtained.
    geometry_provenance: GeometryProvenance | None = None

    @model_validator(mode="after")
    def geometry(self) -> "Word":
        self.geometry_available = self.bbox is not None
        return self

    @model_validator(mode="after")
    def _provenance_consistency(self) -> "Word":
        if (self.bbox is None) != (self.geometry_provenance is None):
            raise ValueError("geometry_provenance must be set if and only if bbox is set")
        return self


class Line(Entity):
    line_id: str
    text: str
    confidence: float | None = Field(default=None, ge=0, le=1)
    bbox: BBox | None = None
    geometry_available: bool = False
    geometry_provenance: GeometryProvenance | None = None
    words: list[Word] = Field(default_factory=list)

    @model_validator(mode="after")
    def geometry(self) -> "Line":
        self.geometry_available = self.bbox is not None
        return self

    @model_validator(mode="after")
    def _provenance_consistency(self) -> "Line":
        if (self.bbox is None) != (self.geometry_provenance is None):
            raise ValueError("geometry_provenance must be set if and only if bbox is set")
        return self


class Cell(Entity):
    text: str
    bbox: BBox | None = None
    geometry_provenance: GeometryProvenance | None = None

    @model_validator(mode="after")
    def _provenance_consistency(self) -> "Cell":
        if (self.bbox is None) != (self.geometry_provenance is None):
            raise ValueError("geometry_provenance must be set if and only if bbox is set")
        return self


class Row(Entity):
    cells: list[Cell] = Field(default_factory=list)


class Table(Entity):
    table_id: str
    bbox: BBox | None = None
    geometry_provenance: GeometryProvenance | None = None
    header: list[str] = Field(default_factory=list)
    rows: list[Row] = Field(default_factory=list)
    # Nearest heading text (e.g. "Phụ lục 02") found directly above this table on the
    # same page, when the detector that built this table knows how to look (currently
    # only the Mistral markdown-block builder does -- see infrastructure/ocr/
    # markdown_tables.py). None means "not computed", not "no heading present"; a table
    # continuity hard guard treats None as "no signal" rather than "confirmed absent".
    heading_before: str | None = None

    @model_validator(mode="after")
    def _provenance_consistency(self) -> "Table":
        if (self.bbox is None) != (self.geometry_provenance is None):
            raise ValueError("geometry_provenance must be set if and only if bbox is set")
        return self


class Evidence(Entity):
    page: int = Field(ge=1)
    input_type: InputType
    native_word_count: int = Field(ge=0)
    native_text_length: int = Field(ge=0)
    native_span_count: int = Field(ge=0)
    image_coverage_ratio: float = Field(ge=0, le=1)
    usable_text: bool
    garbled_text_ratio: float = Field(default=0.0, ge=0, le=1)
    # True whenever the page's image coverage alone means a native-only read would
    # silently drop content the OCR engine could recover (MIXED pages, and any
    # non-usable page). ProcessDocument must not take the native-only fast path
    # when this is set, even if `usable_text` is also True (section 3).
    requires_ocr_regions: bool = False
    reason_codes: list[str] = Field(default_factory=list)


class Page(Entity):
    page_number: int = Field(ge=1)
    input_type: InputType = InputType.SCANNED
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    dimension_unit: Literal["pt", "px"] = "px"
    rotation: int = 0
    engine: str
    model: str
    processing_ms: float = Field(default=0, ge=0)
    status: Status = Status.SUCCESS
    error: str | None = None
    lines: list[Line] = Field(default_factory=list)
    tables: list[Table] = Field(default_factory=list)
    evidence: Evidence | None = None
    raw_markdown: str | None = None
    raw_output_path: str | None = None
    geometry_available: bool = False
    preprocessing: list[str] = Field(default_factory=list)
    transform: list[list[float]] | None = None


class Document(Entity):
    schema_version: str = "1.0"
    document_id: str
    source_file: str
    pages: list[Page] = Field(default_factory=list)


class OCRResult(Entity):
    lines: list[Line] = Field(default_factory=list)
    # Populated only by an engine whose own response already segments tables from prose
    # (currently Mistral OCR's block output -- see infrastructure/ocr/markdown_tables.py).
    # Empty (not None) is the "this engine doesn't supply tables itself" signal that
    # ProcessDocument.run_ocr_job uses to fall back to the pixel-based bordered-grid
    # detector (extract_scanned_tables.build_scanned_tables) instead.
    tables: list[Table] = Field(default_factory=list)
    raw_markdown: str | None = None
    raw_output_path: str | None = None


class Context(Entity):
    document_id: str
    page: int
    output_dir: str


class CriticalField(Entity):
    type: Literal[
        "ARTICLE_NUMBER",
        "CLAUSE_NUMBER",
        "MONEY",
        "DATE",
        "PERCENTAGE",
        "QUANTITY",
        "TAX_CODE",
        "CONTRACT_NUMBER",
        "PARTY_NAME",
    ]
    value: str
    raw_text: str
    page: int | None = Field(default=None, ge=1)


class Sample(Entity):
    sample_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    file_path: str
    source: str = ""
    language: str = ""
    input_type: str = ""
    quality: str = ""
    has_table: bool = False
    has_annex: bool = False
    has_seal: bool = False
    has_signature: bool = False
    is_bilingual: bool = False
    degradation: str = ""
    dpi: int = Field(default=300, ge=72, le=600)
    ground_truth_text: str = ""
    ground_truth_bbox: str = ""
    ground_truth_critical_fields: str = ""
    notes: str = ""


class Experiment(Entity):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    engine: Literal["pymupdf", "openai", "gemini", "mistral"]
    preprocessing: list[str] = Field(default_factory=list)


class Settings(Entity):
    render: dict[str, Any] = Field(default_factory=lambda: {"dpi": 300})
    classifier: dict[str, Any] = Field(default_factory=dict)
    evaluation: dict[str, Any] = Field(default_factory=lambda: {"bbox_iou_threshold": 0.5})
    experiments: list[Experiment] = Field(default_factory=list)
