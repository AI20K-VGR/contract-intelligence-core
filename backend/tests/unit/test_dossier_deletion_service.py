"""Unit tests for DossierDeletionService (SQLite in-memory, no HTTP)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from io import BytesIO

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tests.unit.conftest_contract import FakeFileStorage

from contract_intelligence.contract.domain.entities.dossier import Dossier
from contract_intelligence.contract.infrastructure.persistence.dossier_deletion_service import (
    DossierDeletionService,
)
from contract_intelligence.contract.infrastructure.persistence.deletion_ledger import (
    DeletionLedgerORM,
)
from contract_intelligence.contract.infrastructure.persistence.orm import (
    DocumentORM,
    DossierORM,
    JobORM,
)
from contract_intelligence.contract.infrastructure.persistence.repository_impl import (
    DossierRepositoryImpl,
)
from contract_intelligence.extraction.infrastructure.persistence.orm import OcrLineORM
from contract_intelligence.shared.ai.client import StubAiServiceClient
from contract_intelligence.shared.base import new_ulid, utcnow
from contract_intelligence.shared.persistence.base import Base
from contract_intelligence.shared.persistence.orm_registry import import_all_models


@pytest_asyncio.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    import_all_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as sess:
        yield sess
    await engine.dispose()


@pytest.mark.asyncio
async def test_tombstone_and_purge_keeps_shells_and_clears_content(
    session: AsyncSession,
) -> None:
    tenant = "tenant_test"
    storage = FakeFileStorage()
    dossier_id = new_ulid("dos_")
    job_id = new_ulid("job_")
    doc_id = new_ulid("doc_")

    await storage.put("contracts/a.pdf", BytesIO(b"%PDF"))
    session.add(
        DossierORM(
            id=dossier_id,
            tenant_id=tenant,
            name="Secret Contract",
            status="processing",
            metadata_json={"notes": "classified"},
        )
    )
    session.add(
        JobORM(
            id=job_id,
            tenant_id=tenant,
            dossier_id=dossier_id,
            status="processing",
            error_detail='{"msg":"ocr boom"}',
        )
    )
    session.add(
        DocumentORM(
            id=doc_id,
            tenant_id=tenant,
            dossier_id=dossier_id,
            role="contract",
            order_index=0,
            filename="secret.pdf",
            sha256="abc",
            blob_uri="contracts/a.pdf",
            file_size_bytes=4,
        )
    )
    session.add(
        OcrLineORM(
            id=new_ulid("oln_"),
            tenant_id=tenant,
            document_id=doc_id,
            page_no=1,
            line_no=1,
            text="Điều 1. Nội dung mật",
            bbox="[0,0,1,1]",
        )
    )
    await session.commit()

    svc = DossierDeletionService(
        session=session,
        storage=storage,
        ai_client=StubAiServiceClient(),
        tenant_id=tenant,
    )
    result = await svc.tombstone(dossier_id, actor_user_id="usr_1")
    await session.commit()
    assert result.purge_status == "pending"

    job_orm = (await session.execute(select(JobORM).where(JobORM.id == job_id))).scalar_one()
    assert job_orm.status == "cancelled"

    await svc.purge(dossier_id)
    await session.commit()

    dossier = (
        await session.execute(select(DossierORM).where(DossierORM.id == dossier_id))
    ).scalar_one()
    assert dossier.deleted_at is not None
    assert dossier.purge_status == "completed"
    assert dossier.name == "[deleted]"
    assert dossier.metadata_json is None

    assert (await session.execute(select(JobORM).where(JobORM.id == job_id))).scalar_one()
    doc = (await session.execute(select(DocumentORM).where(DocumentORM.id == doc_id))).scalar_one()
    assert doc.filename == "[purged]"
    assert doc.blob_uri is None

    lines = (
        (await session.execute(select(OcrLineORM).where(OcrLineORM.document_id == doc_id)))
        .scalars()
        .all()
    )
    assert lines == []

    ledger = (
        await session.execute(
            select(DeletionLedgerORM).where(DeletionLedgerORM.dossier_id == dossier_id)
        )
    ).scalar_one()
    assert ledger.requested_by == "usr_1"
    assert ledger.purge_status == "completed"
    assert not await storage.exists("contracts/a.pdf")


@pytest.mark.asyncio
async def test_list_excludes_tombstoned(session: AsyncSession) -> None:
    tenant = "tenant_test"
    repo = DossierRepositoryImpl(session, tenant)
    d = Dossier(id=new_ulid("dos_"), name="visible")
    await repo.add(d)
    await session.commit()

    row = (await session.execute(select(DossierORM).where(DossierORM.id == d.id))).scalar_one()
    row.deleted_at = utcnow()
    await session.commit()

    page = await repo.list()
    assert page.total == 0
    assert await repo.get(d.id) is None
