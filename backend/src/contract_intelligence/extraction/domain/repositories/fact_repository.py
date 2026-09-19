"""FactRepository Protocol.

Concrete impl (FactRepositoryImpl) trả về ``dict[str, Any] | None`` — application
layer truy cập qua Protocol này, không thấy ORM.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class FactRepository(Protocol):
    async def get(self, fact_id: str) -> dict[str, Any] | None: ...

    async def list_by_document(self, document_id: str) -> list[dict[str, Any]]: ...

    async def list_by_key(self, key: str) -> list[dict[str, Any]]: ...

    async def add(self, fact: object) -> None: ...
