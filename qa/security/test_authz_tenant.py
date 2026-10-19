"""Authorization (RBAC) and tenant isolation.

Roles: ADMINISTRATOR > OPERATOR (uploads, runs) / REVIEWER (reviews).
Every request must carry X-Tenant-Id equal to the token's tenant_id claim
(DOC-05b §2.2). Only refused requests are sent: nothing here mutates data.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.security

# (method, path, json body or None, roles that must be refused with 403)
ADMIN_ONLY = [
    ("GET", "/api/v1/users", None),
    ("POST", "/api/v1/users", {}),
    ("POST", "/api/v1/users/does-not-exist/disable", None),
    ("POST", "/api/v1/admin/monitoring/session", None),
    ("GET", "/api/v1/ops/service-logs", None),
]


@pytest.mark.parametrize("role", ["OPERATOR", "REVIEWER"])
@pytest.mark.parametrize("method,path,body", ADMIN_ONLY, ids=[f"{m} {p}" for m, p, _ in ADMIN_ONLY])
def test_admin_only_routes_refuse_other_roles(api, session_for, role, method, path, body):
    """Admin-only routes return 403 for OPERATOR and REVIEWER."""
    r = api.request(method, path, headers=session_for(role).headers, json=body)
    assert r.status_code == 403, r.text[:200]


def test_reviewer_cannot_upload_dossier(api, reviewer):
    """REVIEWER cannot create a dossier (upload is OPERATOR/ADMINISTRATOR)."""
    r = api.post(
        "/api/v1/dossiers",
        headers=reviewer.headers,
        files={"contract": ("x.pdf", b"not-a-pdf", "application/pdf"), "metadata": (None, "{}")},
    )
    assert r.status_code == 403


def test_reviewer_cannot_start_ocr(api, reviewer):
    """REVIEWER cannot trigger OCR/reprocess on a dossier."""
    for path in ("/api/v1/dossiers/does-not-exist/ocr", "/api/v1/dossiers/does-not-exist/reprocess"):
        r = api.post(path, headers=reviewer.headers)
        assert r.status_code == 403, f"{path}: {r.status_code}"


def test_operator_cannot_submit_review_decision(api, operator):
    """OPERATOR cannot post a review decision on a finding (REVIEWER/ADMINISTRATOR only)."""
    r = api.post("/api/v1/findings/does-not-exist/review", headers=operator.headers, json={})
    assert r.status_code == 403


def test_admin_can_list_users(api, admin):
    """ADMINISTRATOR is allowed on the user list (positive control for the matrix)."""
    assert api.get("/api/v1/users", headers=admin.headers).status_code == 200


def test_missing_tenant_header_rejected(api, admin):
    """Tenant-scoped route without X-Tenant-Id -> 400."""
    r = api.get("/api/v1/dossiers", headers={"Authorization": f"Bearer {admin.access_token}"})
    assert r.status_code == 400


@pytest.mark.parametrize("tenant", ["tenant_other", "TENANT_VGR_01", "tenant_vgr_01x", "*", "' OR 1=1--"])
def test_cross_tenant_header_rejected(api, admin, tenant):
    """X-Tenant-Id different from the token claim (even case/suffix variants) -> 403."""
    r = api.get(
        "/api/v1/dossiers",
        headers={"Authorization": f"Bearer {admin.access_token}", "X-Tenant-Id": tenant},
    )
    assert r.status_code == 403, r.text[:200]


def test_cross_tenant_lexicon_rejected(api, admin):
    """Reading another tenant's lexicon by path -> 403/404, never 200."""
    r = api.get("/api/v1/tenants/tenant_other/lexicon", headers=admin.headers)
    assert r.status_code in (403, 404)


def test_unknown_object_ids_return_404_not_500(api, admin):
    """Unknown dossier/document/finding ids -> 404 (no server error, no data)."""
    for path in (
        "/api/v1/dossiers/does-not-exist",
        "/api/v1/documents/does-not-exist",
        "/api/v1/findings/does-not-exist",
        "/api/v1/runs/does-not-exist",
    ):
        r = api.get(path, headers=admin.headers)
        assert r.status_code in (403, 404), f"{path}: {r.status_code}"
