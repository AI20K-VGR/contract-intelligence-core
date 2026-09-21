"""FindingRepository Protocol."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class FindingRepository(Protocol):
    """Contract cho Finding persistence — application layer phụ thuộc Protocol này.

    Concrete impl (FindingRepositoryImpl) ở infrastructure phải khớp method names
    và return types. Application chỉ type-hint qua Protocol — không biết ORM tồn tại.
    """

    async def get(self, finding_id: str) -> dict[str, Any] | None: ...

    async def list_by_dossier(
        self,
        dossier_id: str,
        *,
        disposition: str | None = None,
        scope: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]: ...

    async def list_conflicts_for_review(
        self,
        dossier_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]: ...

    async def add(self, finding: object) -> None: ...


@runtime_checkable
class AnnexLinkRepository(Protocol):
    """Contract cho AnnexLink persistence."""

    async def list_by_dossier(self, dossier_id: str) -> list[dict[str, Any]]: ...
