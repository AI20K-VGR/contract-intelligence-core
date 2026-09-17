"""Input DTO cho POST /dossiers — multipart upload."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class _UploadFile(Protocol):
    """Anti-corruption type cho FastAPI UploadFile.

    Application layer không import FastAPI — chỉ cần Protocol này. Runtime
    FastAPI UploadFile sẽ thỏa mãn Protocol này.
    """

    @property
    def filename(self) -> str: ...
    @property
    def content_type(self) -> str | None: ...
    async def read(self) -> bytes: ...


class ContractUploadRequest(BaseModel):
    """Schema cho POST /dossiers."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=255)
    batch_id: str | None = None
    contract_file: _UploadFile = Field(...)  # type: ignore[valid-type]
    annex_files: list[_UploadFile] = Field(  # type: ignore[valid-type]
        default_factory=list,
        description="0..n phụ lục",
    )
