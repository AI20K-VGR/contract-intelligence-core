"""Activity feed reads real rows and appends admin-only events."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from contract_intelligence.admin.activity_feed import (
    list_activity,
    record_activity,
    storage_usage,
)
from contract_intelligence.contract.infrastructure.persistence.orm import (
    DocumentORM,
    DossierORM,
)
from contract_intelligence.identity.infrastructure.persistence.orm import AppUserORM
from contract_intelligence.shared.persistence.base import Base
from contract_intelligence.shared.persistence.orm_registry import import_all_models

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def session():
    import_all_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
    await engine.dispose()


async def test_feed_uses_dossier_document_and_member_rows(session) -> None:
    when = datetime(2026, 9, 24, 3, 0, tzinfo=UTC)
    session.add_all(
        [
            DossierORM(
                id="dos_1",
                tenant_id="tenant_a",
                name="Hợp đồng Apex",
                created_at=when,
                updated_at=when,
            ),
            DocumentORM(
                id="doc_1",
                tenant_id="tenant_a",
                dossier_id="dos_1",
                role="CONTRACT",
                filename="apex.pdf",
                sha256="abc",
                blob_uri="s3://apex.pdf",
                file_size_bytes=2048,
                created_at=when,
            ),
            AppUserORM(
                id="usr_1",
                tenant_id="tenant_a",
                email="a@ci.local",
                display_name="An",
                role="OPERATOR",
                keycloak_sub="kc_1",
                created_at=when,
                updated_at=when,
            ),
            DossierORM(
                id="dos_other",
                tenant_id="tenant_b",
                name="Hồ sơ khác",
                created_at=when,
                updated_at=when,
            ),
        ]
    )
    await session.flush()

    page = await list_activity(session, tenant_id="tenant_a", limit=8, offset=0)
    titles = [item.title for item in page.items]

    assert page.total == 3
    assert "Tạo hồ sơ Hợp đồng Apex" in titles
    assert "Tải lên apex.pdf" in titles
    assert "Thêm thành viên An" in titles
    assert all("khác" not in title for title in titles)

    usage = await storage_usage(session, tenant_id="tenant_a")
    assert usage.used_bytes == 2048
    assert usage.quota_bytes is None


async def test_recorded_admin_action_is_newest(session) -> None:
    await record_activity(
        session,
        tenant_id="tenant_a",
        title="Khóa tài khoản An",
        actor_display_name="Admin",
        detail="a@ci.local",
        kind="user.disabled",
    )
    page = await list_activity(session, tenant_id="tenant_a", limit=8, offset=0)
    assert page.total == 1
    assert page.items[0].title == "Khóa tài khoản An"
    assert page.items[0].actor_display_name == "Admin"
    assert page.items[0].detail == "a@ci.local"


async def test_feed_includes_dossier_deletion(session) -> None:
    when = datetime(2026, 9, 24, 4, 0, tzinfo=UTC)
    session.add_all(
        [
            AppUserORM(
                id="usr_admin",
                tenant_id="tenant_a",
                email="admin@ci.local",
                display_name="Quản trị",
                role="ADMINISTRATOR",
                keycloak_sub="kc_admin",
                created_at=when,
                updated_at=when,
            ),
            DossierORM(
                id="dos_gone",
                tenant_id="tenant_a",
                name="Hợp đồng cũ",
                created_at=when,
                updated_at=when,
                deleted_at=when,
                deleted_by="usr_admin",
            ),
        ]
    )
    await session.flush()

    page = await list_activity(session, tenant_id="tenant_a", limit=20, offset=0)
    deleted = next(item for item in page.items if item.title.startswith("Xóa hồ sơ"))
    assert deleted.title == "Xóa hồ sơ Hợp đồng cũ"
    assert deleted.actor_display_name == "admin@ci.local"
    assert deleted.occurred_at == when
