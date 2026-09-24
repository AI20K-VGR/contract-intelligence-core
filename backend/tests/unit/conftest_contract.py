"""Pytest fixtures cho Contract bounded context tests (Phase 1).

Provides:
- In-memory fake repositories implementing the Protocol contracts
- In-memory fake FileStorage
- A factory for ContractService bound to the fakes

Used by:
- tests/unit/application/test_contract_service.py — service-level unit tests
- tests/integration/test_contract_endpoints.py — endpoint-level integration tests
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, BinaryIO

import pytest_asyncio

from contract_intelligence.contract.application.services.contract_service import (
    ContractService,
)
from contract_intelligence.contract.domain.entities.document import Document, DocumentRole
from contract_intelligence.contract.domain.entities.dossier import Dossier
from contract_intelligence.contract.domain.entities.manifest import (
    Manifest,
    ManifestItem,
    ManifestRelation,
)
from contract_intelligence.contract.domain.repositories.document_repository import (
    DocumentRepository,
)
from contract_intelligence.contract.domain.repositories.dossier_repository import (
    DossierRepository,
)
from contract_intelligence.contract.domain.repositories.job_repository import (
    JobRepository,
)
from contract_intelligence.shared.base import Page
from contract_intelligence.shared.storage import FileStorage

# -----------------------------------------------------------------------------
# In-memory repositories (fakes) — for unit tests
# -----------------------------------------------------------------------------


class FakeDossierRepository(DossierRepository):
    """In-memory Dossier repository — conforms to Protocol."""

    def __init__(self, tenant_id: str) -> None:
        self._tenant_id = tenant_id
        self._store: dict[str, Dossier] = {}

    async def get(self, dossier_id: str) -> Dossier | None:
        d = self._store.get(dossier_id)
        if d is None:
            return None
        # Tenant isolation — refuse cross-tenant access
        if not dossier_id.startswith("dos_"):
            return None
        if getattr(d, "deleted_at", None) is not None:
            return None
        return d

    async def get_for_update(self, dossier_id: str) -> Dossier | None:
        return await self.get(dossier_id)

    async def list(
        self,
        *,
        status: str | None = None,
        has_conflicts: bool | None = None,
        q: str | None = None,
        batch_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Page[Any]:
        items = sorted(
            [d for d in self._store.values() if getattr(d, "deleted_at", None) is None],
            key=lambda d: d.created_at,
            reverse=True,
        )
        if status:
            items = [d for d in items if getattr(d, "_status", "uploaded") == status]
        if has_conflicts is not None:
            items = [d for d in items if d.has_conflicts == has_conflicts]
        if q:
            items = [d for d in items if q.lower() in d.name.lower()]
        if batch_id:
            items = [d for d in items if d.batch_id == batch_id]
        total = len(items)
        sliced = items[offset : offset + limit]
        return Page(items=sliced, total=total, limit=limit, offset=offset)

    async def add(self, dossier: Dossier) -> None:
        self._store[dossier.id] = dossier

    async def save(self, dossier: Dossier) -> None:
        self._store[dossier.id] = dossier

    async def delete(self, dossier_id: str) -> None:
        self._store.pop(dossier_id, None)

    async def update_status(self, dossier_id: str, status: str) -> None:
        if dossier_id in self._store:
            self._store[dossier_id]._status = status

    async def lock(self, dossier_id: str, locked: bool = True) -> None:
        if dossier_id in self._store:
            self._store[dossier_id]._is_locked = locked

    async def approve(self, dossier_id: str, checksum: str) -> None:
        if dossier_id in self._store:
            self._store[dossier_id]._is_approved = True
            self._store[dossier_id]._checksum = checksum
            self._store[dossier_id]._status = "approved"

    async def get_flags(self, dossier_id: str) -> dict[str, object] | None:
        d = self._store.get(dossier_id)
        if d is None:
            return None
        if getattr(d, "deleted_at", None) is not None:
            return None
        return {
            "is_locked": bool(getattr(d, "_is_locked", False)),
            "is_approved": bool(getattr(d, "_is_approved", False)),
            "status": str(getattr(d, "_status", "uploaded")),
        }

    async def is_tombstoned(self, dossier_id: str) -> bool:
        d = self._store.get(dossier_id)
        if d is None:
            return False
        return getattr(d, "deleted_at", None) is not None


class FakeDocumentRepository(DocumentRepository):
    """In-memory Document repository."""

    def __init__(self, tenant_id: str) -> None:
        self._tenant_id = tenant_id
        self._store: dict[str, Document] = {}

    async def get(self, document_id: str) -> Document | None:
        return self._store.get(document_id)

    async def list_by_dossier(self, dossier_id: str) -> list[Document]:
        return sorted(
            [d for d in self._store.values() if d.dossier_id == dossier_id],
            key=lambda d: (d.order_index, d.created_at),
        )

    async def list(
        self,
        *,
        dossier_id: str | None = None,
        role: DocumentRole | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Page[Any]:
        items = list(self._store.values())
        if dossier_id:
            items = [d for d in items if d.dossier_id == dossier_id]
        if role:
            items = [d for d in items if d.role == role]
        total = len(items)
        sliced = items[offset : offset + limit]
        return Page(items=sliced, total=total, limit=limit, offset=offset)

    async def add(self, document: Document) -> None:
        self._store[document.id] = document

    async def save(self, document: Document) -> None:
        self._store[document.id] = document

    async def delete(self, document_id: str) -> None:
        self._store.pop(document_id, None)


class FakeJobRepository(JobRepository):
    """In-memory Job repository — minimal impl for Phase 1 tests."""

    def __init__(self, tenant_id: str) -> None:
        self._tenant_id = tenant_id
        self._store: dict[str, Any] = {}

    async def get(self, job_id: str) -> Any | None:
        return self._store.get(job_id)

    async def list(
        self,
        *,
        dossier_id: str | None = None,
        status: Any = None,
        limit: int = 50,
        offset: int = 0,
        **filters: object,
    ) -> Page[Any]:
        items = list(self._store.values())
        dossier_id = dossier_id or filters.get("dossier_id")  # type: ignore[assignment]
        if dossier_id:
            items = [j for j in items if getattr(j, "dossier_id", None) == dossier_id]
        if status is not None:
            items = [j for j in items if getattr(j, "status", None) == status]
        # Newest first — matches JobRepositoryImpl order
        items = sorted(items, key=lambda j: j.created_at, reverse=True)
        total = len(items)
        sliced = items[offset : offset + limit]
        return Page(items=sliced, total=total, limit=limit, offset=offset)

    async def add(self, entity: Any) -> None:
        self._store[entity.id] = entity

    async def save(self, entity: Any) -> None:
        self._store[entity.id] = entity

    async def delete(self, job_id: str) -> None:
        self._store.pop(job_id, None)


class FakeManifestRepository:
    """In-memory Manifest repository — minimal impl."""

    def __init__(self, tenant_id: str) -> None:
        self._tenant_id = tenant_id
        self._store: dict[str, Manifest] = {}  # keyed by dossier_id

    async def get_by_dossier(self, dossier_id: str) -> Manifest | None:
        return self._store.get(dossier_id)

    async def get_by_dossier_for_update(self, dossier_id: str) -> Manifest | None:
        return await self.get_by_dossier(dossier_id)

    async def create_with_default_items(
        self,
        dossier_id: str,
        documents: list[dict[str, object]],
    ) -> Manifest:
        from ulid import ULID

        contract_ids: list[str] = []
        annex_ids: list[str] = []
        items: list[ManifestItem] = []
        for idx, d in enumerate(documents):
            role = str(d.get("role", "contract")).lower()
            doc_id = str(d.get("id", ""))
            items.append(
                ManifestItem(
                    id=f"mfi_{ULID()}",
                    manifest_id="",
                    document_id=doc_id,
                    filename=str(d.get("filename", "")),
                    doc_type=role,
                    sha256=str(d.get("sha256", "")),
                    confidence="1.0",
                    order_index=int(d.get("order_index", idx) or idx),
                    included=True,
                    page_count=int(d.get("page_count", 0) or 0),
                    file_size_bytes=int(d.get("file_size_bytes", 0) or 0),
                )
            )
            if role == "annex":
                annex_ids.append(doc_id)
            else:
                contract_ids.append(doc_id)

        relations: list[ManifestRelation] = []
        if contract_ids:
            primary = contract_ids[0]
            for annex_id in annex_ids:
                relations.append(
                    ManifestRelation(
                        id=f"mrel_{ULID()}",
                        manifest_id="",
                        source_document_id=annex_id,
                        target_document_id=primary,
                        relation_type="annex_of",
                        confirmation="unconfirmed",
                    )
                )

        m = Manifest(
            id=f"mft_{ULID()}",
            dossier_id=dossier_id,
            status="pending",
            version=1,
            items=items,
            relations=relations,
        )
        for item in m.items:
            item.manifest_id = m.id
        for rel in m.relations:
            rel.manifest_id = m.id
        self._store[dossier_id] = m
        return m

    async def add_item(self, item: Any) -> None:
        return None

    async def confirm(self, manifest_id: str, user_id: str) -> None:
        from datetime import UTC, datetime

        for m in self._store.values():
            if m.id == manifest_id:
                m.status = "confirmed"
                m.confirmed_at = datetime.now(UTC)
                m.confirmed_by = user_id
                m.version = int(m.version or 1) + 1
                return

    async def apply_confirmation(
        self,
        *,
        manifest_id: str,
        user_id: str,
        new_version: int,
        members: list[Any],
        relations: list[Any],
    ) -> Manifest:
        from datetime import UTC, datetime

        for dossier_id, m in self._store.items():
            if m.id != manifest_id:
                continue
            m.items = list(members)
            m.relations = list(relations)
            m.status = "confirmed"
            m.version = new_version
            m.confirmed_at = datetime.now(UTC)
            m.confirmed_by = user_id
            self._store[dossier_id] = m
            return m
        msg = f"Manifest {manifest_id} not found"
        raise LookupError(msg)

    async def list_items(self, manifest_id: str) -> list[ManifestItem]:
        for m in self._store.values():
            if m.id == manifest_id:
                return list(m.items)
        return []

    async def list_relations(self, manifest_id: str) -> list[Any]:
        for m in self._store.values():
            if m.id == manifest_id:
                return list(m.relations)
        return []


class FakeFileStorage(FileStorage):
    """In-memory FileStorage — captures puts for assertions."""

    def __init__(self) -> None:
        self._blobs: dict[str, bytes] = {}
        self.put_calls: list[tuple[str, int]] = []

    async def put(self, key: str, stream: BinaryIO) -> str:
        data = stream.read()
        self._blobs[key] = data
        self.put_calls.append((key, len(data)))
        return f"file:///{key}"

    async def get(self, blob_uri: str) -> bytes:
        # Strip file:// prefix
        key = blob_uri.removeprefix("file:///")
        if key not in self._blobs:
            msg = f"Blob not found: {blob_uri}"
            raise FileNotFoundError(msg)
        return self._blobs[key]

    async def stream(self, blob_uri: str):  # type: ignore[override]
        data = await self.get(blob_uri)
        yield data

    async def exists(self, blob_uri: str) -> bool:
        key = blob_uri.removeprefix("file:///")
        return key in self._blobs

    async def delete(self, blob_uri: str) -> None:
        key = blob_uri.removeprefix("file:///")
        self._blobs.pop(key, None)


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


@pytest_asyncio.fixture
async def fake_repos() -> dict[str, Any]:
    """Return dict of fresh in-memory fakes — bound to a default tenant."""
    tenant_id = "tenant_vgr_01"
    return {
        "dossier_repo": FakeDossierRepository(tenant_id),
        "document_repo": FakeDocumentRepository(tenant_id),
        "job_repo": FakeJobRepository(tenant_id),
        "manifest_repo": FakeManifestRepository(tenant_id),
        "storage": FakeFileStorage(),
        "tenant_id": tenant_id,
    }


@pytest_asyncio.fixture
async def contract_service(fake_repos: dict[str, Any]) -> ContractService:
    """Build ContractService with in-memory fakes — pure unit test."""
    return ContractService(
        dossier_repo=fake_repos["dossier_repo"],
        document_repo=fake_repos["document_repo"],
        job_repo=fake_repos["job_repo"],
        manifest_repo=fake_repos["manifest_repo"],
        storage=fake_repos["storage"],
        tenant_id=fake_repos["tenant_id"],
    )


@pytest_asyncio.fixture
async def tmp_storage_dir(tmp_path: Path) -> AsyncGenerator[Path, None]:
    """Per-test storage dir for LocalFileStorage integration tests."""
    storage_dir = tmp_path / "var" / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    yield storage_dir
