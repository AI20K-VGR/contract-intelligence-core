"""Unit tests for ContractService — Phase 1 endpoints.

Layer: application — orchestrates dossier/document/job/manifest logic.

Tests use in-memory fakes (see conftest_contract.py) — no DB, no MinIO, no HTTP.
Each test exercises a single use case of ContractService and verifies the
domain entity state + repository side effects.
"""

from __future__ import annotations

import hashlib
from io import BytesIO
from typing import Any

import pytest

from contract_intelligence.contract.application.services.contract_service import (
    ContractService,
)
from contract_intelligence.contract.domain.entities.document import DocumentRole
from contract_intelligence.shared.exceptions import NotFoundError

pytestmark = pytest.mark.asyncio


# =============================================================================
# create_dossier
# =============================================================================


class TestCreateDossier:
    async def test_creates_dossier_with_ulid_id(
        self,
        contract_service: ContractService,
    ) -> None:
        dossier = await contract_service.create_dossier(name="Hợp đồng A", batch_id=None)
        assert dossier.id.startswith("dos_")
        assert dossier.name == "Hợp đồng A"
        assert dossier.batch_id is None
        assert dossier.has_conflicts is False

    async def test_creates_initial_job_with_uploaded_status(
        self,
        contract_service: ContractService,
        fake_repos: dict[str, Any],
    ) -> None:
        dossier = await contract_service.create_dossier(name="With Job", batch_id=None)
        job = dossier.latest_job()
        assert job is not None
        assert job.id.startswith("job_")
        assert job.dossier_id == dossier.id
        assert job.status.value == "uploaded"
        # Persisted in job repo
        loaded = await fake_repos["job_repo"].get(job.id)
        assert loaded is not None
        assert loaded.dossier_id == dossier.id

    async def test_creates_dossier_with_metadata(
        self,
        contract_service: ContractService,
    ) -> None:
        meta = {"tags": ["q2"], "notes": "urgent"}
        dossier = await contract_service.create_dossier(name="Meta", batch_id=None, metadata=meta)
        assert dossier.metadata == meta

    async def test_creates_dossier_with_batch_id(
        self,
        contract_service: ContractService,
    ) -> None:
        dossier = await contract_service.create_dossier(name="Batch test", batch_id="bat_01HZ")
        assert dossier.batch_id == "bat_01HZ"
        job = dossier.latest_job()
        assert job is not None
        assert job.batch_id == "bat_01HZ"

    async def test_persists_dossier_in_repo(
        self,
        contract_service: ContractService,
        fake_repos: dict[str, Any],
    ) -> None:
        dossier = await contract_service.create_dossier(name="X", batch_id=None)
        # Reload from repo to confirm persistence
        loaded = await fake_repos["dossier_repo"].get(dossier.id)
        assert loaded is not None
        assert loaded.id == dossier.id
        assert loaded.name == "X"


class TestGetDossierHydratesJob:
    async def test_get_dossier_includes_latest_job(
        self,
        contract_service: ContractService,
    ) -> None:
        created = await contract_service.create_dossier(name="X", batch_id=None)
        # Clear navigation to force re-hydrate from job repo
        created.jobs = []
        loaded = await contract_service.get_dossier(created.id)
        latest = loaded.latest_job()
        assert latest is not None
        assert latest.dossier_id == created.id
        assert latest.status.value == "uploaded"


# =============================================================================
# upload_document
# =============================================================================


class TestUploadDocument:
    async def test_uploads_contract_pdf_with_sha256_and_size(
        self,
        contract_service: ContractService,
        fake_repos: dict[str, Any],
    ) -> None:
        dossier = await contract_service.create_dossier(name="D", batch_id=None)
        content = BytesIO(b"%PDF-1.4 fake content")

        doc = await contract_service.upload_document(
            dossier_id=dossier.id,
            filename="contract.pdf",
            content=content,
            role=DocumentRole.CONTRACT,
            order_index=0,
        )

        assert doc.id.startswith("doc_")
        assert doc.dossier_id == dossier.id
        assert doc.role == DocumentRole.CONTRACT
        assert doc.order_index == 0
        assert doc.filename == "contract.pdf"
        expected_sha = hashlib.sha256(b"%PDF-1.4 fake content").hexdigest()
        assert doc.sha256 == expected_sha
        assert doc.file_size_bytes == len(b"%PDF-1.4 fake content")
        assert doc.blob_uri.startswith("contracts/")

    async def test_uploads_annex_with_explicit_size(
        self,
        contract_service: ContractService,
        fake_repos: dict[str, Any],
    ) -> None:
        dossier = await contract_service.create_dossier(name="D", batch_id=None)
        content = BytesIO(b"annex bytes")

        doc = await contract_service.upload_document(
            dossier_id=dossier.id,
            filename="annex.pdf",
            content=content,
            role=DocumentRole.ANNEX,
            order_index=1,
            file_size_bytes=11,  # override computed size
        )

        assert doc.role == DocumentRole.ANNEX
        assert doc.order_index == 1
        # Explicit size takes precedence over computed
        assert doc.file_size_bytes == 11

    async def test_writes_blob_to_storage(
        self,
        contract_service: ContractService,
        fake_repos: dict[str, Any],
    ) -> None:
        dossier = await contract_service.create_dossier(name="D", batch_id=None)
        payload = b"%PDF-1.4 hello"

        doc = await contract_service.upload_document(
            dossier_id=dossier.id,
            filename="test.pdf",
            content=BytesIO(payload),
            role=DocumentRole.CONTRACT,
            order_index=0,
        )

        # Verify blob persisted in fake storage
        assert doc.blob_uri in [k for k, _ in fake_repos["storage"].put_calls]
        stored = await fake_repos["storage"].get(doc.blob_uri)
        assert stored == payload

    async def test_upload_to_nonexistent_dossier_raises_not_found(
        self,
        contract_service: ContractService,
    ) -> None:
        with pytest.raises(NotFoundError):
            await contract_service.upload_document(
                dossier_id="dos_DOS_NOT_EXIST",
                filename="x.pdf",
                content=BytesIO(b"data"),
                role=DocumentRole.CONTRACT,
                order_index=0,
            )


# =============================================================================
# list_dossiers / get_dossier / patch_dossier
# =============================================================================


class TestListDossiers:
    async def test_returns_empty_when_no_dossiers(
        self,
        contract_service: ContractService,
    ) -> None:
        items, total = await contract_service.list_dossiers(limit=10, offset=0)
        assert items == []
        assert total == 0

    async def test_returns_all_dossiers(
        self,
        contract_service: ContractService,
    ) -> None:
        await contract_service.create_dossier(name="A", batch_id=None)
        await contract_service.create_dossier(name="B", batch_id=None)
        await contract_service.create_dossier(name="C", batch_id=None)

        items, total = await contract_service.list_dossiers(limit=10, offset=0)
        assert total == 3
        assert len(items) == 3

    async def test_respects_limit_offset(
        self,
        contract_service: ContractService,
    ) -> None:
        for i in range(5):
            await contract_service.create_dossier(name=f"D{i}", batch_id=None)

        items, total = await contract_service.list_dossiers(limit=2, offset=1)
        assert total == 5
        assert len(items) == 2

    async def test_filters_by_has_conflicts(
        self,
        contract_service: ContractService,
        fake_repos: dict[str, Any],
    ) -> None:
        d1 = await contract_service.create_dossier(name="C", batch_id=None)
        await contract_service.create_dossier(name="NC", batch_id=None)
        # Mutate + persist the change
        d1.has_conflicts = True
        await fake_repos["dossier_repo"].save(d1)

        items, total = await contract_service.list_dossiers(has_conflicts=True, limit=10, offset=0)
        assert total == 1
        assert items[0].id == d1.id

    async def test_filters_by_q_name_search(
        self,
        contract_service: ContractService,
    ) -> None:
        await contract_service.create_dossier(name="Hợp đồng mua bán", batch_id=None)
        await contract_service.create_dossier(name="Phụ lục gia hạn", batch_id=None)
        await contract_service.create_dossier(name="Hợp đồng thuê nhà", batch_id=None)

        items, total = await contract_service.list_dossiers(q="Hợp đồng", limit=10, offset=0)
        assert total == 2
        assert all("Hợp đồng" in d.name for d in items)

    async def test_filters_by_batch_id(
        self,
        contract_service: ContractService,
    ) -> None:
        await contract_service.create_dossier(name="A", batch_id="bat_01")
        await contract_service.create_dossier(name="B", batch_id="bat_02")
        await contract_service.create_dossier(name="C", batch_id="bat_01")

        items, total = await contract_service.list_dossiers(batch_id="bat_01", limit=10, offset=0)
        assert total == 2
        assert all(d.batch_id == "bat_01" for d in items)

    async def test_q_filter_is_case_insensitive(
        self,
        contract_service: ContractService,
    ) -> None:
        await contract_service.create_dossier(name="Alpha Contract", batch_id=None)
        await contract_service.create_dossier(name="Beta", batch_id=None)

        items, total = await contract_service.list_dossiers(q="alpha", limit=10, offset=0)
        assert total == 1
        assert items[0].name == "Alpha Contract"


class TestGetDossier:
    async def test_returns_existing_dossier(
        self,
        contract_service: ContractService,
    ) -> None:
        created = await contract_service.create_dossier(name="X", batch_id=None)
        loaded = await contract_service.get_dossier(created.id)
        assert loaded.id == created.id
        assert loaded.name == "X"

    async def test_raises_not_found_for_missing_dossier(
        self,
        contract_service: ContractService,
    ) -> None:
        with pytest.raises(NotFoundError):
            await contract_service.get_dossier("dos_MISSING")


class TestPatchDossier:
    async def test_updates_name(
        self,
        contract_service: ContractService,
    ) -> None:
        dossier = await contract_service.create_dossier(name="Old", batch_id=None)
        patched = await contract_service.patch_dossier(dossier.id, name="New")
        assert patched.name == "New"

    async def test_no_op_when_name_is_none(
        self,
        contract_service: ContractService,
    ) -> None:
        dossier = await contract_service.create_dossier(name="Same", batch_id=None)
        patched = await contract_service.patch_dossier(dossier.id, name=None)
        assert patched.name == "Same"

    async def test_raises_not_found_when_dossier_missing(
        self,
        contract_service: ContractService,
    ) -> None:
        with pytest.raises(NotFoundError):
            await contract_service.patch_dossier("dos_MISSING", name="X")

    async def test_updates_metadata(
        self,
        contract_service: ContractService,
    ) -> None:
        dossier = await contract_service.create_dossier(name="D", batch_id=None)
        assert dossier.metadata is None

        meta = {"tags": ["urgent", "q2-2026"], "notes": "Internal review needed"}
        patched = await contract_service.patch_dossier(dossier.id, name=None, metadata=meta)
        assert patched.metadata == meta

    async def test_updates_name_and_metadata_together(
        self,
        contract_service: ContractService,
    ) -> None:
        dossier = await contract_service.create_dossier(name="Old", batch_id=None)
        patched = await contract_service.patch_dossier(
            dossier.id, name="New Name", metadata={"priority": "high"}
        )
        assert patched.name == "New Name"
        assert patched.metadata == {"priority": "high"}

    async def test_metadata_persists_across_get(
        self,
        contract_service: ContractService,
    ) -> None:
        dossier = await contract_service.create_dossier(name="D", batch_id=None)
        await contract_service.patch_dossier(dossier.id, name=None, metadata={"key": "value"})
        reloaded = await contract_service.get_dossier(dossier.id)
        assert reloaded.metadata == {"key": "value"}

    async def test_metadata_none_does_not_overwrite(
        self,
        contract_service: ContractService,
    ) -> None:
        """When metadata is None (not provided), existing metadata should remain."""
        dossier = await contract_service.create_dossier(name="D", batch_id=None)
        await contract_service.patch_dossier(dossier.id, name=None, metadata={"existing": True})
        # Patch again without metadata — should keep existing
        patched = await contract_service.patch_dossier(dossier.id, name="Updated")
        assert patched.metadata == {"existing": True}


# =============================================================================
# list_documents / get_document / get_document_blob
# =============================================================================


class TestListDocuments:
    async def test_returns_empty_for_dossier_without_documents(
        self,
        contract_service: ContractService,
    ) -> None:
        dossier = await contract_service.create_dossier(name="D", batch_id=None)
        docs = await contract_service.list_documents(dossier.id)
        assert docs == []

    async def test_returns_documents_ordered_by_order_index(
        self,
        contract_service: ContractService,
    ) -> None:
        dossier = await contract_service.create_dossier(name="D", batch_id=None)
        # Upload in non-sequential order to verify sorting
        await contract_service.upload_document(
            dossier_id=dossier.id,
            filename="annex_2.pdf",
            content=BytesIO(b"a2"),
            role=DocumentRole.ANNEX,
            order_index=2,
        )
        await contract_service.upload_document(
            dossier_id=dossier.id,
            filename="contract.pdf",
            content=BytesIO(b"c"),
            role=DocumentRole.CONTRACT,
            order_index=0,
        )
        await contract_service.upload_document(
            dossier_id=dossier.id,
            filename="annex_1.pdf",
            content=BytesIO(b"a1"),
            role=DocumentRole.ANNEX,
            order_index=1,
        )

        docs = await contract_service.list_documents(dossier.id)
        assert len(docs) == 3
        assert [d.order_index for d in docs] == [0, 1, 2]
        assert [d.filename for d in docs] == ["contract.pdf", "annex_1.pdf", "annex_2.pdf"]


class TestGetDocument:
    async def test_returns_existing_document(
        self,
        contract_service: ContractService,
    ) -> None:
        dossier = await contract_service.create_dossier(name="D", batch_id=None)
        uploaded = await contract_service.upload_document(
            dossier_id=dossier.id,
            filename="x.pdf",
            content=BytesIO(b"data"),
            role=DocumentRole.CONTRACT,
            order_index=0,
        )
        loaded = await contract_service.get_document(uploaded.id)
        assert loaded.id == uploaded.id
        assert loaded.filename == "x.pdf"

    async def test_raises_not_found_for_missing_document(
        self,
        contract_service: ContractService,
    ) -> None:
        with pytest.raises(NotFoundError):
            await contract_service.get_document("doc_MISSING")


class TestGetDocumentBlob:
    async def test_streams_blob_bytes_from_storage(
        self,
        contract_service: ContractService,
        fake_repos: dict[str, Any],
    ) -> None:
        dossier = await contract_service.create_dossier(name="D", batch_id=None)
        payload = b"%PDF-1.4 content here"
        uploaded = await contract_service.upload_document(
            dossier_id=dossier.id,
            filename="dl.pdf",
            content=BytesIO(payload),
            role=DocumentRole.CONTRACT,
            order_index=0,
        )

        data, filename = await contract_service.get_document_blob(uploaded.id)
        assert data == payload
        assert filename == "dl.pdf"

    async def test_raises_not_found_for_missing_document(
        self,
        contract_service: ContractService,
    ) -> None:
        with pytest.raises(NotFoundError):
            await contract_service.get_document_blob("doc_MISSING")
