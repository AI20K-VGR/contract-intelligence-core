from __future__ import annotations

import hashlib
import importlib
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from contract_intelligence.config.settings import Settings
from contract_intelligence.infrastructure import ai_adapters
from contract_intelligence.schemas.queries import DossierQueryRequest
from contract_intelligence.shared.auth import AuthenticatedUser

contract_router = importlib.import_module(
    "contract_intelligence.contract.interfaces.api.routers.contract_router"
)
dossier_api = importlib.import_module("contract_intelligence.api.v1.dossiers")


def _user() -> AuthenticatedUser:
    return AuthenticatedUser("owner", "tenant-a", "owner@example.test", "Owner", "OPERATOR")


def _dossier(consent: Any) -> SimpleNamespace:
    metadata: dict[str, Any] = {"created_by": "owner", "ai2_snapshot_digest": "digest-a"}
    if consent is not ...:
        metadata["ai2_content_sharing_consent"] = consent
    return SimpleNamespace(
        id="dossier-a",
        tenant_id="tenant-a",
        metadata_json=metadata,
        metadata=metadata,
        checksum=None,
        deleted_at=None,
    )


class _Session:
    def __init__(self) -> None:
        self.added: list[Any] = []

    async def refresh(self, _record: Any) -> None:
        return None

    async def commit(self) -> None:
        return None

    def add(self, record: Any) -> None:
        self.added.append(record)


@pytest.mark.parametrize(
    "consent,expected", [(True, True), (False, False), (..., False), (None, False)]
)
@pytest.mark.parametrize(
    "server_flags",
    [
        {"egress_allowed": True, "use_vector": True},
        {"egress_allowed": False, "use_vector": False},
    ],
)
@pytest.mark.asyncio
async def test_api_v1_query_signs_stored_consent_separately_from_server_caps(
    monkeypatch, consent, expected, server_flags
):
    # This test isolates signed consent/cap propagation; semantic snapshot reads
    # are covered by the semantic query tests.
    monkeypatch.setattr(
        dossier_api,
        "_semantic_result",
        AsyncMock(
            return_value={
                "semantic_extension": None,
                "state": "NOT_MEASURED",
                "reason": "CURRENT_RUN_ABSENT",
                "run_id": None,
                "result_digest": None,
                "typed_table_projections": {"payment_schedules": [], "boq_checks": []},
            }
        ),
    )
    dossier = _dossier(consent)
    captured: dict[str, Any] = {}

    async def capture(payload: dict[str, Any]) -> dict[str, Any]:
        captured.update(payload)
        return {"state": "ok", "answer": "local answer", "citations": []}

    monkeypatch.setattr(dossier_api, "_acl_check_dossier_access", AsyncMock(return_value=dossier))
    monkeypatch.setattr(dossier_api, "enforce_query_limits", AsyncMock())
    monkeypatch.setattr(dossier_api, "query_ai2", capture)
    monkeypatch.setattr(
        dossier_api, "save_query_trace", AsyncMock(return_value=SimpleNamespace(id="trace-a"))
    )
    monkeypatch.setattr(dossier_api, "_dossier_document_ids", AsyncMock(return_value=set()))
    monkeypatch.setattr(dossier_api, "record_query_answer", lambda *_args: None)
    monkeypatch.setattr(dossier_api, "server_query_policy_flags", lambda: server_flags)
    session = _Session()

    await dossier_api._run_dossier_query(
        endpoint="query",
        dossier_id=dossier.id,
        body=DossierQueryRequest(query="What changed?"),
        session=session,
        user=_user(),
    )

    assert captured["content_sharing_consent"] is expected
    assert captured["policy_flags"] == server_flags


@pytest.mark.parametrize(
    "consent,expected", [(True, True), (False, False), (..., False), (None, False)]
)
@pytest.mark.parametrize(
    "server_flags",
    [
        {"egress_allowed": True, "use_vector": True},
        {"egress_allowed": False, "use_vector": False},
    ],
)
@pytest.mark.asyncio
async def test_contract_search_signs_stored_consent_separately_from_server_caps(
    monkeypatch, consent, expected, server_flags
):
    dossier = _dossier(consent)
    captured: dict[str, Any] = {}

    async def capture(payload: dict[str, Any]) -> dict[str, Any]:
        captured.update(payload)
        return {"state": "ok", "answer": "local answer", "citations": []}

    class Service:
        async def get_dossier(self, _dossier_id: str) -> SimpleNamespace:
            return dossier

        async def list_documents(self, _dossier_id: str) -> list[Any]:
            return []

    monkeypatch.setattr(contract_router, "_require_readable", AsyncMock(return_value=dossier))
    monkeypatch.setattr(contract_router, "_optional_session_factory", lambda: None)
    monkeypatch.setattr(contract_router, "_enforce_search_limits", AsyncMock())
    monkeypatch.setattr(contract_router, "_save_search_trace", AsyncMock(return_value="trace-a"))
    monkeypatch.setattr(contract_router, "server_query_policy_flags", lambda: server_flags)
    monkeypatch.setattr("contract_intelligence.infrastructure.ai_adapters.query_ai2", capture)

    await contract_router.search_dossier(
        dossier_id=dossier.id,
        body=contract_router.DossierSearchBody(query="What changed?"),
        svc=Service(),
        user=_user(),
        _tenant_id="tenant-a",
    )

    assert captured["content_sharing_consent"] is expected
    assert captured["policy_flags"] == server_flags


def test_backend_query_runtime_global_caps_default_on(monkeypatch):
    monkeypatch.delenv("AI2_QUERY_EGRESS_ALLOWED", raising=False)
    monkeypatch.delenv("AI2_QUERY_USE_VECTOR", raising=False)
    settings = Settings(_env_file=None)
    assert settings.ai2_query_egress_allowed is True
    assert settings.ai2_query_use_vector is True


def test_clients_cannot_supply_dossier_consent_or_server_policy():
    with pytest.raises(ValidationError):
        DossierQueryRequest(query="question", content_sharing_consent=True)
    with pytest.raises(ValidationError):
        contract_router.DossierSearchBody(
            query="question", content_sharing_consent=True, policy_flags={"egress_allowed": True}
        )


@pytest.mark.asyncio
async def test_query_adapter_accepts_and_signs_stored_consent(monkeypatch):
    settings = ai_adapters.get_settings()
    monkeypatch.setattr(settings, "ai2_service_hmac_secret", "test-hmac-secret")
    post_json = AsyncMock(return_value={"answer": "ok"})
    monkeypatch.setattr(ai_adapters, "_post_json", post_json)
    payload = {
        "query": "What changed?",
        "dossier_id": "dossier-a",
        "snapshot_version": "latest",
        "snapshot_digest": "digest-a",
        "query_contract_version": "ai2.query.v1",
        "acl_context": "owner",
        "policy_flags": {"egress_allowed": True, "use_vector": True},
        "tenant_id": "tenant-a",
        "actor_id": "owner",
        "content_sharing_consent": True,
    }

    await ai_adapters.query_ai2(payload)

    wire = post_json.await_args.args[1]
    assert wire["content_sharing_consent"] is True
    assert (
        wire["service_envelope"]["payload_sha256"]
        == hashlib.sha256(ai_adapters._canonical_payload(payload)).hexdigest()
    )
