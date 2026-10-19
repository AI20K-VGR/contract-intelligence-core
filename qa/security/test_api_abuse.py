"""BOPLA / mass assignment and rate limiting.

Mass assignment (OWASP API6:2023): a client must not set server-owned fields —
ownership, tenant, status, ACL grants — by smuggling them into a request body.
Rate limiting (API4): the Q&A/search endpoints must cap calls per user.
"""

from __future__ import annotations

import json
import os

import pytest

from lib.pdf import sample_contract_pdf

pytestmark = pytest.mark.security


@pytest.fixture
def owned_dossier(api, operator, admin, cfg):
    if cfg.is_prod:
        pytest.skip("mass-assignment probes create and delete a dossier; local only")
    r = api.post(
        "/api/v1/dossiers",
        headers=operator.headers,
        files=[
            ("contract", ("ma.pdf", sample_contract_pdf(), "application/pdf")),
            ("metadata", (None, json.dumps({"name": "QA mass-assign"}))),
        ],
    )
    assert r.status_code == 202, r.text[:300]
    dossier_id = r.json()["data"]["dossier_id"]
    yield dossier_id
    api.delete(f"/api/v1/dossiers/{dossier_id}", headers=admin.headers)


def test_metadata_injection_does_not_grant_access(api, operator, reviewer, owned_dossier):
    """Smuggling created_by/shared_with/access_scope into metadata must not change owner or grant access."""
    before = api.get(f"/api/v1/dossiers/{owned_dossier}", headers=operator.headers).json()["data"]
    owner = before["metadata"].get("created_by")
    r = api.patch(
        f"/api/v1/dossiers/{owned_dossier}",
        headers=operator.headers,
        json={
            "metadata": {
                "created_by": "dev-admin-keycloak-id",
                "shared_with": [{"id": reviewer.claims.get("sub"), "permission": "edit"}],
                "access_scope": "shared_out",
            }
        },
    )
    assert r.status_code in (200, 422)
    after = api.get(f"/api/v1/dossiers/{owned_dossier}", headers=operator.headers).json()["data"]
    assert after["metadata"].get("created_by") == owner, "ownership was reassigned via metadata"
    # The injected grant must not let the reviewer in.
    assert api.get(f"/api/v1/dossiers/{owned_dossier}/findings", headers=reviewer.headers).status_code == 403


def test_extra_top_level_fields_ignored_on_patch(api, operator, owned_dossier):
    """Unknown/server-owned top-level fields on PATCH must not change id, tenant or status."""
    before = api.get(f"/api/v1/dossiers/{owned_dossier}", headers=operator.headers).json()["data"]
    r = api.patch(
        f"/api/v1/dossiers/{owned_dossier}",
        headers=operator.headers,
        json={"name": "renamed", "id": "dos_hijack", "tenant_id": "tenant_qa_02",
              "owner": "someone-else", "status": "approved", "has_conflicts": True},
    )
    assert r.status_code in (200, 422)
    after = api.get(f"/api/v1/dossiers/{owned_dossier}", headers=operator.headers).json()["data"]
    assert after["id"] == owned_dossier
    assert after.get("has_conflicts") == before.get("has_conflicts")
    assert api.get(f"/api/v1/dossiers/{owned_dossier}", headers={**operator.headers, "X-Tenant-Id": "tenant_qa_02"}).status_code == 403


def test_user_create_rejects_unknown_fields(api, admin):
    """POST /users must reject unknown fields (e.g. is_superuser) rather than accept them."""
    r = api.post(
        "/api/v1/users",
        headers=admin.headers,
        json={"email": "qa-massassign@example.com", "display_name": "QA", "role": "OPERATOR",
              "is_superuser": True, "tenant_id": "tenant_qa_02"},
    )
    # additionalProperties:false -> 422. (If it 200s, the extra fields must be ignored, not applied.)
    assert r.status_code == 422, f"unknown fields accepted: {r.status_code} {r.text[:200]}"


@pytest.mark.skipif(
    os.getenv("QA_RUN_RATE_LIMIT", "").strip().lower() not in {"1", "true", "yes"},
    reason="opt-in: set QA_RUN_RATE_LIMIT=1 (local) — it makes up to 25 search calls",
)
def test_search_rate_limited(api, operator, admin, cfg):
    """The per-user search/query rate limit returns 429 once the minute budget is spent."""
    if cfg.is_prod:
        pytest.skip("do not hammer prod")
    r = api.post(
        "/api/v1/dossiers",
        headers=operator.headers,
        files=[("contract", ("rl.pdf", sample_contract_pdf(), "application/pdf")),
               ("metadata", (None, json.dumps({"name": "QA rate-limit"})))],
    )
    dossier_id = r.json()["data"]["dossier_id"]
    try:
        codes = []
        for _ in range(25):
            resp = api.post(f"/api/v1/dossiers/{dossier_id}/search", headers=operator.headers, json={"query": "gia tri"})
            codes.append(resp.status_code)
            if resp.status_code == 429:
                break
        assert 429 in codes, f"no 429 after 25 calls; got {codes}"
    finally:
        api.delete(f"/api/v1/dossiers/{dossier_id}", headers=admin.headers)
