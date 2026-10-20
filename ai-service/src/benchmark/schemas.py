from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class ImageInfo(BaseModel):
    width: int
    height: int
    dpi: int
    path: str


class OCRTable(BaseModel):
    table_id: str
    rows: list[list[str]] = Field(default_factory=list)
    pages: list[int] = Field(default_factory=list)
    is_multi_page: bool = False


class OCRPageResult(BaseModel):
    page_number: int
    image: ImageInfo
    text: str = ""
    blocks: list[dict[str, Any]] = Field(default_factory=list)
    tables: list[OCRTable] = Field(default_factory=list)
    latency_ms: float = 0
    error: str | None = None


class ProviderInfo(BaseModel):
    name: str
    model: str


class RuntimeInfo(BaseModel):
    total_latency_ms: float
    pages_processed: int
    cost_usd: float | None = None


class OCRDocumentResult(BaseModel):
    schema_version: Literal["ocr-benchmark.v1"] = "ocr-benchmark.v1"
    document_id: str
    experiment: str
    provider: ProviderInfo
    pages: list[OCRPageResult]
    runtime: RuntimeInfo


class PreparedPage(BaseModel):
    page_number: int
    image_path: str
    width: int
    height: int
    dpi: int


class PreparedDocument(BaseModel):
    document_id: str
    file_name: str
    source_path: str
    page_count: int
    language: list[str] = Field(default_factory=lambda: ["vi"])
    source_type: Literal["scan", "image"] = "scan"
    scan_quality: str = "unknown"
    test_cases: list[str] = Field(default_factory=list)
    pages: list[PreparedPage]


class GroundTruthField(BaseModel):
    field_type: str
    raw_value: str
    normalized_value: str | None = None


class GroundTruthTable(BaseModel):
    table_id: str
    pages: list[int]
    is_multi_page: bool = False
    rows: list[list[str]] = Field(default_factory=list)


class GroundTruthPage(BaseModel):
    page_number: int
    text: str
    critical_fields: list[GroundTruthField] = Field(default_factory=list)
    tables: list[GroundTruthTable] = Field(default_factory=list)


class GroundTruthDocument(BaseModel):
    document_id: str
    pages: list[GroundTruthPage]


def read_json(path: Path) -> Any:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
