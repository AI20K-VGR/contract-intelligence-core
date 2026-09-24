"""Input DTO cho POST /dossiers — multipart upload."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _UploadFilePlaceholder:
    """Stub class thay cho FastAPI UploadFile — Application layer không
    phụ thuộc FastAPI.

    Runtime: FastAPI UploadFile được truyền vào (thỏa mãn duck-typing).
    Validation: Pydantic cần concrete class để build schema — Protocol không hỗ trợ.
    """

    @property
    def filename(self) -> str:
        return ""

    @property
    def content_type(self) -> str | None:
        return None

    async def read(self) -> bytes:
        return b""

    def __get_pydantic_core_schema__(self, _source: Any, _handler: Any) -> Any:
        from pydantic_core import core_schema

        return core_schema.any_schema()


# Type alias — runtime FastAPI UploadFile thỏa mãn
UploadFileLike = _UploadFilePlaceholder


class ContractUploadRequest(BaseModel):
    """Schema cho POST /dossiers."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    name: str = Field(..., min_length=1, max_length=255)
    batch_id: str | None = None
    contract_file: Any = Field(...)  # FastAPI UploadFile at runtime
    annex_files: list[Any] = Field(
        default_factory=list,
        description="0..n phụ lục",
    )
