"""Real multi-tenant isolation: two tenants with independent data.

This needs tokens whose `tenant_id` claim actually differs. On the dev realm the
claim is a HARDCODED mapper (tenant_vgr_01 for everyone) — see FINDING ARCH-01 —
so a second-tenant user still logs in as tenant_vgr_01. The fixture detects that
and skips, pointing at the finding, instead of passing a hollow test.

To exercise this for real, change the `tenant_id` client mapper from a hardcoded
value to a user-attribute mapper (User Attribute -> claim tenant_id), then re-run.
"""

from __future__ import annotations

import json
import time

import pytest

from lib.auth import login
from lib.pdf import sample_contract_pdf

pytestmark = pytest.mark.security


@pytest.fixture(scope="module")
def two_tenants(cfg, admin, api):
    if cfg.is_prod:
        pytest.skip("multi-tenant setup provisions Keycloak users; local only")
    from lib.kc_admin import KcAdmin, KcAdminError

    try:
        kc = KcAdmin(cfg)
    except KcAdminError as exc:
        pytest.skip(f"Keycloak master admin not available: {exc}")

    stamp = str(int(time.time()))
    try:
        u1 = kc.create_user(f"qa-t1-{stamp}@ci.local", "Qa-T1-2026", "tenant_vgr_01", "OPERATOR")
        u2 = kc.create_user(f"qa-t2-{stamp}@ci.local", "Qa-T2-2026", "tenant_qa_02", "OPERATOR")
        s1 = login(u1.username, u1.password, role="OPERATOR", cfg=cfg)
        s2 = login(u2.username, u2.password, role="OPERATOR", cfg=cfg)
        if s2.tenant_id == s1.tenant_id:
            pytest.skip(
                "FINDING ARCH-01: the realm hardcodes the tenant_id claim, so a second-tenant "
                f"user still authenticates as {s1.tenant_id!r}. Real two-tenant isolation cannot "
                "be exercised until the claim is driven by a user attribute."
            )
        yield {"t1": s1, "t2": s2}
    finally:
        kc.cleanup()


def test_tenants_have_distinct_claims(two_tenants):
    """The two users carry different tenant_id claims."""
    assert two_tenants["t1"].tenant_id != two_tenants["t2"].tenant_id


def test_tenant2_cannot_see_tenant1_dossier(two_tenants, api, admin):
    """A dossier created in tenant 1 is invisible and unreadable from tenant 2."""
    t1, t2 = two_tenants["t1"], two_tenants["t2"]
    r = api.post(
        "/api/v1/dossiers",
        headers=t1.headers,
        files=[
            ("contract", ("mt.pdf", sample_contract_pdf(), "application/pdf")),
            ("metadata", (None, json.dumps({"name": "QA MT t1"}))),
        ],
    )
    assert r.status_code == 202
    dossier_id = r.json()["data"]["dossier_id"]
    try:
        # Not in tenant 2's listing.
        listing = api.get("/api/v1/dossiers", headers=t2.headers, params={"limit": 100}).json()["data"]
        items = listing if isinstance(listing, list) else listing.get("items", [])
        assert all(item["id"] != dossier_id for item in items)
        # Direct read with tenant 2's own (matching) header is refused.
        direct = api.get(f"/api/v1/dossiers/{dossier_id}", headers=t2.headers)
        assert direct.status_code in (403, 404)
    finally:
        api.delete(f"/api/v1/dossiers/{dossier_id}", headers=admin.headers)
