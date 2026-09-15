from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .bbox import BBox
from .enums import InputType, Status


class Entity(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Word(Entity):
    word_id: str
    text: str
    confidence: float | None = Field(default=None, ge=0, le=1)
    bbox: BBox | None = None
    geometry_available: bool = False

    @model_validator(mode="after")
    def geometry(self) -> "Word":
        self.geometry_available = self.bbox is not None
        return self


class Line(Entity):
    line_id: str
    text: str
    confidence: float | None = Field(default=None, ge=0, le=1)
    bbox: BBox | None = None
    geometry_available: bool = False
    words: list[Word] = Field(default_factory=list)

    @model_validator(mode="after")
    def geometry(self) -> "Line":
        self.geometry_available = self.bbox is not None
        return self


class Evidence(Entity):
    page: int = Field(ge=1)
    input_type: InputType
    native_word_count: int = Field(ge=0)
    native_text_length: int = Field(ge=0)
    native_span_count: int = Field(ge=0)
    image_coverage_ratio: float = Field(ge=0, le=1)
    usable_text: bool


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
    engine: Literal["pymupdf", "paddle", "deepseek", "openai", "gemini", "deepseek_api"]
    preprocessing: list[str] = Field(default_factory=list)


class Settings(Entity):
    render: dict[str, Any] = Field(default_factory=lambda: {"dpi": 300})
    classifier: dict[str, Any] = Field(default_factory=dict)
    paddle: dict[str, Any] = Field(default_factory=dict)
    deepseek: dict[str, Any] = Field(default_factory=dict)
    evaluation: dict[str, Any] = Field(default_factory=lambda: {"bbox_iou_threshold": 0.5})
    experiments: list[Experiment] = Field(default_factory=list)
