"""PageRepository Protocol.

Concrete impl (PageRepositoryImpl) trả về ``dict[str, Any] | None`` — match đúng
shape mà application/router đang dùng.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class PageRepository(Protocol):
    async def get(self, page_id: str) -> dict[str, Any] | None: ...

    async def list_by_document(self, document_id: str) -> list[dict[str, Any]]: ...

    async def get_by_document_and_page_no(
        self, document_id: str, page_no: int
    ) -> dict[str, Any] | None: ...

    async def add(self, page: object) -> None: ...
