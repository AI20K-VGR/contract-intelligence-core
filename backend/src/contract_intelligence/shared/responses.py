"""API response envelope chuẩn — dùng cho MỌI endpoint.

Format (xem ``backend/CONTEXT.md`` §6.4):

.. code-block:: json

    {
        "data": { ... },
        "meta": {
            "trace_id": "...",
            "request_id": "..."
        }
    }
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ApiMeta(BaseModel):
    """Metadata chuẩn đi kèm mỗi response."""

    model_config = ConfigDict(extra="forbid")

    trace_id: str | None = None
    request_id: str | None = None
    page: int | None = None
    page_size: int | None = None
    total: int | None = None


class ApiResponse(BaseModel, Generic[T]):
    """Envelope chuẩn ``{ data, meta }`` — generic cho payload."""

    model_config = ConfigDict(extra="forbid")

    data: T
    meta: ApiMeta = ApiMeta()


class ErrorPayload(BaseModel):
    """Payload cho response lỗi — chia sẻ với exception handler."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: dict[str, Any] = {}


class ErrorResponse(BaseModel):
    """Response envelope cho lỗi."""

    model_config = ConfigDict(extra="forbid")

    error: ErrorPayload
    meta: ApiMeta = ApiMeta()
