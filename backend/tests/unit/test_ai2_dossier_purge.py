"""Deletion adapter must sign scope and fail closed on incomplete erasure."""

from __future__ import annotations

import hashlib
import hmac
import json

import httpx
import pytest

from contract_intelligence.config.settings import get_settings
from contract_intelligence.infrastructure import ai_adapters


@pytest.mark.asyncio
@pytest.mark.parametrize("base_suffix", ["", "/api/v1"])
async def test_purge_signs_canonical_tenant_scope_and_returns_only_evidence(
    monkeypatch, base_suffix
):
    settings = get_settings()
    monkeypatch.setattr(settings, "ai2_base_url", "http://ai2.test" + base_suffix)
    monkeypatch.setattr(settings, "ai2_service_hmac_secret", "purge-unit-only")

    def handler(request):
        assert request.method == "DELETE"
        assert request.url.path == "/api/v1/dossiers/dossier"
        data = json.loads(request.content)
        env = data.pop("service_envelope")
        assert data == {"tenant_id": "tenant", "dossier_id": "dossier"}
        assert env["scopes"] == ["ai2.dossier.delete"]
        assert env["tenant_id"] == "tenant"
        assert env["dossier_id"] == "dossier"
        signature = env.pop("signature")

        def canonical(obj):
            return json.dumps(
                obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode()

        assert env["payload_sha256"] == hashlib.sha256(canonical(data)).hexdigest()
        assert hmac.compare_digest(
            signature, hmac.new(b"purge-unit-only", canonical(env), hashlib.sha256).hexdigest()
        )
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "deleted": {"jobs": 0},
                "evidence": {
                    "deleted": {"jobs": 4},
                    "blob_directories": 1,
                    "ignored": "not retained",
                },
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(ai_adapters.httpx, "AsyncClient", lambda **_kw: client)
    assert await ai_adapters.purge_ai2_dossier(tenant_id="tenant", dossier_id="dossier") == {
        "deleted": {"jobs": 4},
        "blob_directories": 1,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,body",
    [
        (503, {"secret": "must not be recorded"}),
        (200, {"status": "pending", "evidence": {"deleted": {}}}),
        (200, {"status": "completed"}),
        (200, {"status": "completed", "evidence": {"deleted": {"jobs": -1}}}),
    ],
)
async def test_incomplete_or_invalid_purge_never_completes(monkeypatch, status, body):
    monkeypatch.setattr(ai_adapters, "_service_envelope", lambda *_a, **_kw: {})
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _req: httpx.Response(status, json=body))
    )
    monkeypatch.setattr(ai_adapters.httpx, "AsyncClient", lambda **_kw: client)
    with pytest.raises(ai_adapters.AiAdapterError) as exc:
        await ai_adapters.purge_ai2_dossier(tenant_id="tenant", dossier_id="dossier")
    assert "must not be recorded" not in str(exc.value)
