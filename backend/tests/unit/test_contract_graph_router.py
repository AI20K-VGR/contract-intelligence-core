from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from contract_intelligence.contract.application.services.contract_service import ContractService
from contract_intelligence.contract.domain.entities.dossier import Dossier
from contract_intelligence.contract.interfaces.api.dependencies import get_contract_service
from contract_intelligence.main import app
from contract_intelligence.shared.auth import get_current_user
from contract_intelligence.shared.auth.schemas import AuthenticatedUser
from contract_intelligence.shared.auth.tenant import get_tenant_id


def _reader() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="reader-a",
        tenant_id="tenant-a",
        email="reader@example.test",
        display_name="Reader",
        role="OPERATOR",
    )


@pytest.fixture
def dossier() -> Dossier:
    return Dossier(
        id="dossier-a",
        name="Dossier A",
        metadata={"created_by": "reader-a", "ai2_snapshot_digest": "digest-a"},
    )


@pytest_asyncio.fixture
async def client(dossier: Dossier) -> AsyncGenerator[tuple[AsyncClient, AsyncMock], None]:
    svc = AsyncMock(spec=ContractService)
    svc.get_dossier.return_value = dossier
    app.dependency_overrides[get_contract_service] = lambda: svc
    app.dependency_overrides[get_current_user] = lambda: _reader()
    app.dependency_overrides[get_tenant_id] = lambda: "tenant-a"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, svc
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_query_only_share_cannot_read_graph_and_adapter_is_not_called(client, monkeypatch):
    ac, svc = client
    svc.get_dossier.return_value.metadata = {
        "shared_with": [{"id": "reader-a", "permission": "read", "actions": ["query"]}],
        "ai2_snapshot_digest": "digest-a",
    }
    adapter = AsyncMock(return_value={"status": "READY", "edges": [{"id": "secret-edge"}]})
    monkeypatch.setattr(
        "contract_intelligence.infrastructure.ai_adapters.read_ai2_contract_graph",
        adapter,
        raising=False,
    )

    response = await ac.get(
        "/api/v1/dossiers/dossier-a/ai2/contract-graph/pair",
        params={"job_id": "job-a", "snapshot_digest": "digest-a"},
    )

    assert response.status_code == 403
    assert "secret-edge" not in response.text
    adapter.assert_not_awaited()


@pytest.mark.asyncio
async def test_share_revoked_while_ai2_is_awaited_returns_403_without_graph_body(
    client, monkeypatch
):
    ac, svc = client
    started = asyncio.Event()
    release = asyncio.Event()
    svc.get_dossier.side_effect = [
        Dossier(
            id="dossier-a",
            name="Dossier A",
            metadata={
                "shared_with": [{"id": "reader-a", "permission": "edit"}],
                "ai2_snapshot_digest": "digest-a",
            },
        ),
        Dossier(
            id="dossier-a",
            name="Dossier A",
            metadata={"access_scope": "mine", "ai2_snapshot_digest": "digest-a"},
        ),
    ]

    async def blocked_adapter(*_args, **_kwargs):
        started.set()
        await release.wait()
        return {"status": "READY", "edges": [{"id": "private-edge"}]}

    monkeypatch.setattr(
        "contract_intelligence.infrastructure.ai_adapters.read_ai2_contract_graph",
        blocked_adapter,
        raising=False,
    )
    request = asyncio.create_task(
        ac.get(
            "/api/v1/dossiers/dossier-a/ai2/contract-graph/pair",
            params={"job_id": "job-a", "snapshot_digest": "digest-a"},
        )
    )
    await asyncio.wait_for(started.wait(), timeout=2)
    release.set()
    response = await request

    assert response.status_code == 403
    assert "private-edge" not in response.text


@pytest.mark.asyncio
async def test_snapshot_changed_while_ai2_is_awaited_returns_409_without_graph_body(
    client, monkeypatch
):
    ac, svc = client
    svc.get_dossier.side_effect = [
        Dossier(
            id="dossier-a",
            name="Dossier A",
            metadata={"created_by": "reader-a", "ai2_snapshot_digest": "digest-a"},
        ),
        Dossier(
            id="dossier-a",
            name="Dossier A",
            metadata={"created_by": "reader-a", "ai2_snapshot_digest": "digest-b"},
        ),
    ]
    monkeypatch.setattr(
        "contract_intelligence.infrastructure.ai_adapters.read_ai2_contract_graph",
        AsyncMock(return_value={"status": "READY", "edges": [{"id": "private-edge"}]}),
        raising=False,
    )

    response = await ac.get(
        "/api/v1/dossiers/dossier-a/ai2/contract-graph/pair",
        params={"job_id": "job-a", "snapshot_digest": "digest-a"},
    )

    assert response.status_code == 409
    assert "private-edge" not in response.text


@pytest.mark.asyncio
async def test_graph_page_uses_scope_bound_cursor_and_rechecks_acl_for_each_page(
    client, monkeypatch
):
    from contract_intelligence.contract.interfaces.api.routers import contract_router

    ac, _svc = client
    monkeypatch.setattr(contract_router, "_graph_cursor_secret", lambda: b"test-secret")
    adapter = AsyncMock(
        side_effect=[
            {
                "status": "READY",
                "graph_kind": "pair",
                "snapshot_digest": "digest-a",
                "edges": [
                    {
                        "id": "pair-1",
                        "kind": "PAIR",
                        "label": "REFERENCE",
                        "directed": False,
                        "source_node_id": "node-a",
                        "target_node_id": "node-b",
                        "review_state": "NEEDS_REVIEW",
                        "source_citation_ref": "cite:a",
                        "target_citation_ref": "cite:b",
                        "digest": "edge-hash",
                        "tenant_id": "tenant-a",
                        "dossier_id": "dossier-a",
                        "job_id": "job-a",
                        "snapshot_digest": "digest-a",
                    }
                ],
                "total_count": 2,
                "has_more": True,
                "next_cursor": "cpair:pair-1",
            },
            {
                "status": "READY",
                "graph_kind": "pair",
                "snapshot_digest": "digest-a",
                "edges": [],
                "total_count": 2,
                "has_more": False,
                "next_cursor": None,
            },
        ]
    )
    monkeypatch.setattr(
        "contract_intelligence.infrastructure.ai_adapters.read_ai2_contract_graph", adapter
    )

    first = await ac.get(
        "/api/v1/dossiers/dossier-a/ai2/contract-graph/pair",
        params={"job_id": "job-a", "snapshot_digest": "digest-a"},
    )
    assert first.status_code == 200
    first_data = first.json()["data"]
    assert first_data["has_more"] is True
    assert first_data["edges"][0]["id"] == "pair-1"
    assert "tenant_id" not in first_data["edges"][0]

    second = await ac.get(
        "/api/v1/dossiers/dossier-a/ai2/contract-graph/pair",
        params={
            "job_id": "job-a",
            "snapshot_digest": "digest-a",
            "cursor": first_data["next_cursor"],
        },
    )
    assert second.status_code == 200
    assert second.json()["data"]["has_more"] is False
    assert [call.kwargs["cursor"] for call in adapter.await_args_list] == [None, "cpair:pair-1"]
    assert len(adapter.await_args_list) == 2


def test_graph_cursor_is_signed_and_bound_to_tenant_job_digest_and_kind(monkeypatch):
    from fastapi import HTTPException

    from contract_intelligence.contract.interfaces.api.routers import contract_router

    monkeypatch.setattr(contract_router, "_graph_cursor_secret", lambda: b"test-secret")
    token = contract_router._encode_graph_cursor(
        "cpair:edge-7",
        tenant_id="tenant-a",
        dossier_id="dossier-a",
        job_id="job-a",
        snapshot_digest="digest-a",
        graph_kind="pair",
    )
    assert token
    assert (
        contract_router._decode_graph_cursor(
            token,
            tenant_id="tenant-a",
            dossier_id="dossier-a",
            job_id="job-a",
            snapshot_digest="digest-a",
            graph_kind="pair",
        )
        == "cpair:edge-7"
    )

    with pytest.raises(HTTPException) as stale:
        contract_router._decode_graph_cursor(
            token,
            tenant_id="tenant-a",
            dossier_id="dossier-a",
            job_id="job-b",
            snapshot_digest="digest-a",
            graph_kind="pair",
        )
    assert stale.value.status_code == 409

    with pytest.raises(HTTPException) as tampered:
        contract_router._decode_graph_cursor(
            token[:-1] + ("A" if token[-1] != "A" else "B"),
            tenant_id="tenant-a",
            dossier_id="dossier-a",
            job_id="job-a",
            snapshot_digest="digest-a",
            graph_kind="pair",
        )
    assert tampered.value.status_code == 400
