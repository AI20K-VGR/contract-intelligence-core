"""ManifestRepository Protocol — abstract contract for persistence."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from contract_intelligence.contract.domain.entities.manifest import (
    Manifest,
    ManifestItem,
    ManifestRelation,
)


@runtime_checkable
class ManifestRepository(Protocol):
    """Contract cho Manifest persistence — application chỉ phụ thuộc Protocol này.

    Infrastructure cung cấp concrete impl (ManifestRepositoryImpl) khớp methods.
    Application KHÔNG được biết ORM tồn tại.
    """

    async def get_by_dossier(self, dossier_id: str) -> Manifest | None: ...

    async def get_by_dossier_for_update(self, dossier_id: str) -> Manifest | None:
        """Load manifest with row lock (SELECT … FOR UPDATE)."""
        ...

    async def create_with_default_items(
        self, dossier_id: str, documents: list[dict[str, object]]
    ) -> Manifest: ...

    async def confirm(self, manifest_id: str, user_id: str) -> None: ...

    async def apply_confirmation(
        self,
        *,
        manifest_id: str,
        user_id: str,
        new_version: int,
        members: list[ManifestItem],
        relations: list[ManifestRelation],
    ) -> Manifest:
        """Persist confirmed membership + relations; bump version & status."""
        ...

    async def list_items(self, manifest_id: str) -> list[ManifestItem]: ...

    async def list_relations(self, manifest_id: str) -> list[ManifestRelation]: ...
