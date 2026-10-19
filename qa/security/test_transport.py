"""CORS and HTTP surface of the running backend."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.security


def test_cors_rejects_unknown_origin(api):
    """Preflight from an unlisted origin gets no Access-Control-Allow-Origin."""
    r = api.options(
        "/api/v1/dossiers",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in r.headers


def test_cors_never_wildcard_with_credentials(api, cfg):
    """Allowed origin is echoed exactly; '*' is never combined with credentials."""
    r = api.options(
        "/api/v1/dossiers",
        headers={
            "Origin": cfg.allowed_origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,x-tenant-id",
        },
    )
    assert r.headers.get("access-control-allow-origin") == cfg.allowed_origin
    assert r.headers.get("access-control-allow-origin") != "*"


def test_cors_simple_request_from_unknown_origin(api, admin):
    """A credentialed GET from an unlisted origin is not readable by that origin."""
    r = api.get("/api/v1/auth/me", headers={**admin.headers, "Origin": "https://evil.example"})
    assert r.headers.get("access-control-allow-origin") not in ("*", "https://evil.example")


def test_unknown_route_returns_json_404(api):
    """Unknown routes -> plain 404, no framework debug page."""
    r = api.get("/api/v1/definitely-not-a-route")
    assert r.status_code == 404
    assert "<html" not in r.text.lower()


def test_request_id_header_present(api):
    """Every response carries X-Request-Id for tracing incidents."""
    assert api.get("/health").headers.get("x-request-id")


def test_trace_method_disabled(api):
    """HTTP TRACE is not served."""
    assert api.request("TRACE", "/health").status_code in (404, 405)


def test_api_docs_not_public(api, cfg):
    """Interactive API docs must not be reachable anonymously.

    FINDING SEC-02: open on the local dev build (db5d2b13) — marked xfail there.
    Fixed on prod, where /docs, /redoc and /openapi.json all return 403, so on
    prod this is asserted strictly.
    """
    codes = [api.get(path).status_code for path in ("/docs", "/redoc", "/openapi.json")]
    if cfg.is_prod:
        assert all(c in (401, 403, 404) for c in codes), f"API docs reachable on prod: {codes}"
    elif all(c in (401, 403, 404) for c in codes):
        pytest.skip("docs already blocked here (SEC-02 fixed); nothing to flag")
    else:
        pytest.xfail(f"FINDING SEC-02: interactive docs public on this build: {codes}")
