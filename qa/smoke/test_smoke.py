"""Smoke: is the stack up, and do the critical read paths answer?

Read-only and fast (< 30 s). Run after every deploy or `docker compose up`;
if one of these fails, nothing else is worth running.
"""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.smoke


def test_backend_health(http, cfg):
    """Backend /health answers 200 with status ok."""
    r = http.get(f"{cfg.backend_url}/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_backend_healthz_reports_contract_version(http, cfg):
    """/api/v1/healthz reports status ok and the AI contract version."""
    r = http.get(f"{cfg.backend_url}/api/v1/healthz")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["status"] == "ok"
    assert data.get("ai_contract_version")


def test_backend_readyz_database_ok(http, cfg):
    """/api/v1/readyz reports the database reachable."""
    r = http.get(f"{cfg.backend_url}/api/v1/readyz")
    assert r.status_code == 200
    assert r.json()["data"]["checks"]["db_ok"] is True


def test_backend_openapi_served(http, cfg):
    """OpenAPI schema: served and lists the upload route on local; blocked (401/403/404) on prod."""
    r = http.get(f"{cfg.backend_url}/openapi.json")
    if cfg.is_prod:
        assert r.status_code in (401, 403, 404), (
            f"interactive API schema is reachable on prod (HTTP {r.status_code}); expected it blocked"
        )
        return
    assert r.status_code == 200
    assert "/api/v1/dossiers" in r.json()["paths"]


def test_ai2_health(http, cfg):
    """AI2 service /health answers 200 with status ok (skipped where AI2 is internal-only)."""
    if not cfg.ai2_direct:
        pytest.skip("AI2 is not exposed on its own URL in this environment (internal to ci-network)")
    try:
        r = http.get(f"{cfg.ai2_url}/health")
    except httpx.ConnectError:
        pytest.skip("AI2 port is not published on this host (expected in production)")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_keycloak_realm_discovery(http, cfg):
    """Keycloak realm publishes its OIDC discovery document."""
    r = http.get(f"{cfg.keycloak_url}/realms/{cfg.realm}/.well-known/openid-configuration")
    assert r.status_code == 200
    assert r.json()["issuer"].endswith(f"/realms/{cfg.realm}")


def test_minio_live(http, cfg):
    """MinIO object storage reports live."""
    try:
        r = http.get(f"{cfg.minio_url}/minio/health/live")
    except httpx.ConnectError:
        pytest.skip("MinIO port is not published on this host")
    assert r.status_code == 200


def test_frontend_serves_index(http, cfg):
    """Frontend serves its index page."""
    try:
        r = http.get(cfg.frontend_url + "/")
    except httpx.ConnectError:
        pytest.skip(f"frontend not running at {cfg.frontend_url}")
    assert r.status_code == 200
    assert "<div id=\"root\"" in r.text or "<html" in r.text.lower()


def test_frontend_js_bundle_loads(http, cfg):
    """The index references a JS module bundle, and that bundle downloads as JavaScript.

    Checking only index.html can pass while the app is broken; the bundle is what runs.
    """
    import re

    try:
        index = http.get(cfg.frontend_url + "/")
    except httpx.ConnectError:
        pytest.skip(f"frontend not running at {cfg.frontend_url}")
    srcs = re.findall(r'<script[^>]+src="([^"]+)"', index.text)
    module_srcs = [s for s in srcs if s.endswith(".js") or "/assets/" in s]
    if not module_srcs:
        pytest.skip("no script bundle referenced (dev server may inline modules)")
    src = module_srcs[0]
    url = src if src.startswith("http") else cfg.frontend_url + "/" + src.lstrip("/")
    bundle = http.get(url)
    assert bundle.status_code == 200, f"JS bundle {url} -> {bundle.status_code}"
    ctype = bundle.headers.get("content-type", "")
    assert "javascript" in ctype or "ecmascript" in ctype, f"bundle served as {ctype!r}"
    assert len(bundle.content) > 1000, "JS bundle suspiciously small"


@pytest.mark.parametrize("role", ["ADMINISTRATOR", "OPERATOR", "REVIEWER"])
def test_login_and_auth_me(api, session_for, role):
    """Each seeded role can log in through Keycloak and /auth/me returns its role."""
    session = session_for(role)
    r = api.get("/api/v1/auth/me", headers=session.headers)
    assert r.status_code == 200
    me = r.json()["data"]
    assert me["role"] == role
    assert me["tenant_id"] == session.tenant_id


def test_list_dossiers(api, admin):
    """Authenticated dossier list answers 200 with a paged envelope."""
    r = api.get("/api/v1/dossiers", headers=admin.headers, params={"limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["data"], (list, dict))
    assert "meta" in body


def test_list_runs(api, admin):
    """Pipeline run list answers 200."""
    r = api.get("/api/v1/runs", headers=admin.headers)
    assert r.status_code == 200


def test_dossier_detail_and_documents(api, operator, admin):
    """A readable dossier opens with its detail and document list.

    Reads as the OPERATOR first (owner of its own uploads) then ADMINISTRATOR, so
    the test exercises a real object rather than quietly passing. With
    QA_EXPECT_DATA=1 an empty tenant is a failure, not a skip, so the smoke
    coverage gap is visible.
    """
    import os

    for session in (operator, admin):
        listing = api.get("/api/v1/dossiers", headers=session.headers, params={"limit": 1}).json()["data"]
        items = listing if isinstance(listing, list) else listing.get("items", [])
        if items:
            dossier_id = items[0]["id"]
            detail = api.get(f"/api/v1/dossiers/{dossier_id}", headers=session.headers)
            assert detail.status_code == 200
            body = detail.json()["data"]
            assert body["id"] == dossier_id
            docs = api.get(f"/api/v1/dossiers/{dossier_id}/documents", headers=session.headers)
            assert docs.status_code == 200
            assert isinstance(docs.json()["data"], list)
            return
    if os.getenv("QA_EXPECT_DATA", "").strip().lower() in {"1", "true", "yes"}:
        pytest.fail("QA_EXPECT_DATA is set but no readable dossier exists for OPERATOR or ADMINISTRATOR")
    pytest.skip("no readable dossier in this tenant yet (set QA_EXPECT_DATA=1 to require one)")
