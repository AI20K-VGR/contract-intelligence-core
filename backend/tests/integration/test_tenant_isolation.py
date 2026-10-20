"""M-07 cross-access suite: no request returns data outside tenant/ACL (DOC-11 §4.2 #9).

DOC-03 M-07 = share of requests that return data outside the caller's tenant
or ACL; the threshold is 0. This suite seeds one dossier with every kind of
sub-resource, then calls every dossier-scoped read endpoint of the OpenAPI
spec as:

- the owner (control: the endpoint must not refuse them),
- an ADMINISTRATOR of the same tenant with no grant,
- an ADMINISTRATOR of another tenant,
- a user whose grant has expired,
- a user whose grant is disabled.

Outsiders are ADMINISTRATORs so that RBAC cannot mask a missing ACL check.
Any 2xx for an outsider is a violation; so is the dossier showing up in their
list endpoints. Endpoints are taken from the live OpenAPI spec, so a new
route with a dossier-scoped parameter is covered without editing this file —
or fails the "unmapped parameter" check until it is.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tests.integration.test_ai2_review_fixes_flow import (
    BODY_DOCUMENT_ID,
    DOSSIER_ID,
    OPERATOR,
    RUN_ID,
    TENANT_ID,
    _processing_result,
    _seed_dossier,
)

from contract_intelligence.contract.infrastructure.persistence.orm import DocumentORM, DossierORM
from contract_intelligence.extraction.infrastructure.persistence.orm import (
    CitationORM,
    ClauseNodeORM,
    FactORM,
    PageORM,
    PipelineRunORM,
)
from contract_intelligence.extraction.infrastructure.persistence.orm_reocr import ReOcrRequestORM
from contract_intelligence.main import app
from contract_intelligence.review.infrastructure.persistence.orm import ReviewItemORM
from contract_intelligence.shared.ai.persistence import persist_ai2_processing_result
from contract_intelligence.shared.auth import AuthenticatedUser, get_current_user
from contract_intelligence.shared.auth.tenant import get_tenant_id
from contract_intelligence.shared.persistence import Base, bind_engine, reset_engine
from contract_intelligence.shared.persistence.orm_registry import import_all_models
from contract_intelligence.shared.persistence.session import get_async_session

pytestmark = pytest.mark.integration

OTHER_TENANT = "tenant-m07-other"


def _admin(user_id: str, tenant_id: str = TENANT_ID) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=user_id,
        tenant_id=tenant_id,
        email=f"{user_id}@m07.test",
        display_name=user_id,
        role="ADMINISTRATOR",
    )


# The owner, as ADMINISTRATOR so every route's RBAC lets them in (control).
OWNER = _admin(OPERATOR.user_id)

OUTSIDERS = {
    "same-tenant, no grant": _admin("m07-stranger"),
    "other tenant": _admin("m07-foreign", OTHER_TENANT),
    "expired grant": _admin("m07-expired"),
    "disabled grant": _admin("m07-disabled"),
}

# Path parameters that address something inside the seeded dossier.
SCOPED_PARAMS = {
    "dossier_id",
    "id",
    "document_id",
    "run_id",
    "fact_id",
    "finding_id",
    "citation_id",
    "item_id",
    "node_id",
    "page_id",
    "page_no",
    "request_id",
}
# Tenant-wide lists that must not reveal the dossier to outsiders.
LIST_ROUTES = ("/api/v1/dossiers", f"/api/v1/runs?dossier_id={DOSSIER_ID}")


@pytest_asyncio.fixture
async def factory(tmp_path: Any) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    import_all_models()
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'm07.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    bind_engine(engine)  # the SSE route opens its own short sessions
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await _seed_dossier(session_factory)
    async with session_factory() as session:
        await persist_ai2_processing_result(
            session,
            tenant_id=TENANT_ID,
            dossier_id=DOSSIER_ID,
            result=_processing_result(),
            run_id=RUN_ID,
        )
        page = PageORM(
            id="page-m07-1",
            tenant_id=TENANT_ID,
            document_id=BODY_DOCUMENT_ID,
            page_no=1,
            width_pt="595",
            height_pt="842",
        )
        session.add(page)
        session.add(
            ClauseNodeORM(
                id="node-m07-1",
                tenant_id=TENANT_ID,
                document_id=BODY_DOCUMENT_ID,
                node_type="article",
                label="Điều 1",
                number="1",
                text="Điều 1. Phạm vi",
                page_start=1,
                page_end=1,
            )
        )
        session.add(
            ReOcrRequestORM(
                id="reocr-m07-1",
                tenant_id=TENANT_ID,
                document_id=BODY_DOCUMENT_ID,
                page_ids=json.dumps(["page-m07-1"]),
                reason="m07",
                requested_by=OPERATOR.user_id,
            )
        )
        # The shared seed writes upper-case roles; the domain enum is lower-case.
        for document in (await session.scalars(select(DocumentORM))).all():
            document.role = document.role.lower()
        run = await session.get(PipelineRunORM, RUN_ID)
        assert run is not None
        run.status = "succeeded"  # the SSE stream then ends for the owner
        dossier = await session.get(DossierORM, DOSSIER_ID)
        assert dossier is not None
        past = (datetime.now(tz=UTC) - timedelta(hours=1)).isoformat(timespec="seconds")
        metadata = dict(dossier.metadata_json or {})
        metadata["access_scope"] = "shared_out"
        metadata["shared_with"] = [
            *metadata.get("shared_with", []),
            {"id": "m07-expired", "permission": "edit", "expires_at": past},
            {"id": "m07-disabled", "permission": "edit", "status": "disabled"},
        ]
        dossier.metadata_json = metadata
        await session.commit()
    yield session_factory
    reset_engine()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncClient, None]:
    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_async_session] = override_session
    # A route that fails on sqlite (e.g. LATERAL joins) answers 500 instead of raising;
    # a 500 is never counted as a leak or as the owner being refused.
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _act_as(user: AuthenticatedUser) -> None:
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_tenant_id] = lambda: user.tenant_id


async def _ids(factory: async_sessionmaker[AsyncSession]) -> dict[str, str]:
    async with factory() as session:

        async def first(column: Any) -> str:
            value = await session.scalar(select(column).limit(1))
            assert value is not None, f"seed produced no {column}"
            return str(value)

        return {
            "dossier_id": DOSSIER_ID,
            "id": DOSSIER_ID,
            "document_id": BODY_DOCUMENT_ID,
            "run_id": RUN_ID,
            "fact_id": await first(FactORM.id),
            "finding_id": await first(_finding_id_column()),
            "citation_id": await first(CitationORM.id),
            "item_id": await first(ReviewItemORM.id),
            "node_id": "node-m07-1",
            "page_id": "page-m07-1",
            "page_no": "1",
            "request_id": "reocr-m07-1",
        }


def _finding_id_column() -> Any:
    from contract_intelligence.conflict.infrastructure.persistence.orm import FindingORM

    return FindingORM.id


def _scoped_routes() -> list[tuple[str, str]]:
    """(method, path template) of every dossier-scoped read endpoint."""
    routes: list[tuple[str, str]] = []
    for path, operations in app.openapi()["paths"].items():
        params = set(re.findall(r"{(\w+)}", path))
        if not params or not params <= SCOPED_PARAMS:
            continue
        for method in operations:
            if method == "get" or (method == "post" and re.search(r"/(query|search|ask)$", path)):
                routes.append((method.upper(), path))
    return sorted(routes, key=lambda item: item[1])


async def _call(client: AsyncClient, method: str, url: str) -> int:
    if method == "GET":
        response = await client.get(url, timeout=10)
    else:
        response = await client.post(url, json={"query": "Điều khoản thanh toán?"}, timeout=10)
    return response.status_code


def test_every_dossier_scoped_parameter_is_mapped() -> None:
    """A new id kind in a route must be added to SCOPED_PARAMS (and seeded)."""
    dossier_words = (
        "dossier",
        "document",
        "run",
        "fact",
        "finding",
        "citation",
        "item",
        "node",
        "page",
        "request",
    )
    unmapped = sorted(
        {
            param
            for path in app.openapi()["paths"]
            for param in re.findall(r"{(\w+)}", path)
            if param not in SCOPED_PARAMS and any(word in param for word in dossier_words)
        }
    )
    assert unmapped == []


@pytest.mark.asyncio
async def test_m07_no_request_returns_data_outside_tenant_or_acl(
    factory: async_sessionmaker[AsyncSession], client: AsyncClient
) -> None:
    ids = await _ids(factory)
    routes = _scoped_routes()
    assert len(routes) >= 20, routes

    ai2_answer = {"state": "PASS", "answer": "ok", "citations": [], "hits": []}
    violations: list[str] = []
    control_refused: list[str] = []
    requests = 0
    with (
        patch(
            "contract_intelligence.api.v1.dossiers.query_ai2",
            new=AsyncMock(return_value=ai2_answer),
        ),
        patch(
            "contract_intelligence.infrastructure.ai_adapters.query_ai2",
            new=AsyncMock(return_value=ai2_answer),
        ),
    ):
        for method, template in routes:
            url = template.format(**ids)
            _act_as(OWNER)
            owner_status = await _call(client, method, url)
            if owner_status in (401, 403):
                control_refused.append(f"{method} {template} → {owner_status}")
            for label, outsider in OUTSIDERS.items():
                _act_as(outsider)
                requests += 1
                status = await _call(client, method, url)
                if 200 <= status < 300:
                    violations.append(f"{label}: {method} {template} → {status}")

        for url in LIST_ROUTES:
            for label, outsider in OUTSIDERS.items():
                _act_as(outsider)
                requests += 1
                response = await client.get(url)
                if response.status_code < 300 and DOSSIER_ID in response.text:
                    violations.append(f"{label}: GET {url} lists the dossier")

    m07 = len(violations) / requests
    print(f"\nM-07 = {len(violations)}/{requests} = {m07:.4f} over {len(routes)} endpoints")
    for line in control_refused:
        print("  owner refused:", line)
    for line in violations:
        print("  leak:", line)
    assert control_refused == [], "owner refused — the route or the seed is broken"
    assert violations == [], "\n".join(violations)
