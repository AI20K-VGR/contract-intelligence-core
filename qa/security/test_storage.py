"""Object storage exposure: MinIO must not serve data anonymously, and object
bytes must reach the browser only through the authenticated API."""

from __future__ import annotations

import httpx
import pytest

from lib.config import REPO_ROOT

pytestmark = pytest.mark.security


def test_minio_denies_anonymous_access(http, cfg):
    """MinIO refuses anonymous bucket listing and object GET (no public buckets)."""
    if cfg.is_prod:
        pytest.skip("MinIO is internal on prod")
    try:
        root = http.get(f"{cfg.minio_url}/")
        bucket = http.get(f"{cfg.minio_url}/dossiers/")
        obj = http.get(f"{cfg.minio_url}/dossiers/probe-nonexistent")
    except httpx.ConnectError:
        pytest.skip("MinIO port not published here")
    assert root.status_code == 403
    assert bucket.status_code in (403, 404)
    assert obj.status_code in (403, 404)


def test_page_image_requires_auth(api, admin, operator):
    """The page-image endpoint streams through the authenticated API, not a public URL."""
    listing = api.get("/api/v1/dossiers", headers=operator.headers, params={"limit": 20}).json()["data"]
    items = listing if isinstance(listing, list) else listing.get("items", [])
    document_id = None
    for item in items:
        docs = api.get(f"/api/v1/dossiers/{item['id']}/documents", headers=operator.headers).json().get("data") or []
        if docs:
            document_id = docs[0]["id"]
            break
    if not document_id:
        pytest.skip("no document to probe")
    # No token -> 401/403, never the image bytes.
    anon = api.get(f"/api/v1/documents/{document_id}/pages/1/image")
    assert anon.status_code in (401, 403), anon.status_code


def test_presign_ttl_is_bounded():
    """Presigned-URL TTL default is short and bounded (60 s .. 24 h), never unbounded."""
    settings = (REPO_ROOT / "backend" / "src" / "contract_intelligence" / "config" / "settings.py").read_text(
        encoding="utf-8"
    )
    block = settings.split("kafka_presign_expires_seconds", 1)[1][:300]
    assert "le=86400" in block, "presigned TTL upper bound should be <= 24h"
    assert "ge=60" in block
