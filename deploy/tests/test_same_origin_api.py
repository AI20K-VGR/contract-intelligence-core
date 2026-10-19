"""The SPA calls the API on its own origin: no CORS preflight per request."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND_CADDY = (ROOT / "deploy" / "frontend.caddy").read_text(encoding="utf-8")


def _block(text: str, opener: str) -> str:
    """The body of `opener { ... }`, braces balanced."""
    start = text.index(opener)
    depth = 0
    for index in range(text.index("{", start), len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError(f"unbalanced block {opener}")


def test_app_host_proxies_api_and_grafana_to_the_backend() -> None:
    api = _block(FRONTEND_CADDY, "handle /api/*")
    grafana = _block(FRONTEND_CADDY, "handle /grafana/*")

    assert "reverse_proxy backend:8000" in api
    assert "flush_interval -1" in api  # SSE run events
    assert "max_size 320MiB" in api  # same upload limit as the API host
    assert "reverse_proxy backend:8000" in grafana
    for header in ("User", "Role", "Name", "Email", "Groups"):
        assert f"header_up -X-Webauth-{header}" in grafana


def test_backchannel_logout_stays_closed_on_the_app_host() -> None:
    api = _block(FRONTEND_CADDY, "handle /api/*")

    assert "@backchannel_logout path /api/v1/auth/backchannel-logout" in api
    assert "respond @backchannel_logout 404" in api


def test_only_the_spa_gets_the_content_security_policy() -> None:
    api = _block(FRONTEND_CADDY, "handle /api/*")
    grafana = _block(FRONTEND_CADDY, "handle /grafana/*")
    spa = FRONTEND_CADDY[FRONTEND_CADDY.rindex("\thandle {") :]

    assert "Content-Security-Policy" not in api
    assert "Content-Security-Policy" not in grafana
    assert "Content-Security-Policy" in spa
    assert "reverse_proxy frontend:80" in spa
    assert FRONTEND_CADDY.count("Content-Security-Policy") == 1


def test_frontend_build_points_the_api_at_the_app_origin() -> None:
    frontend = (ROOT / "deploy" / "compose.frontend.yml").read_text(encoding="utf-8")
    prod = (ROOT / "deploy" / "compose.prod.yml").read_text(encoding="utf-8")

    assert "VITE_API_BASE_URL: https://${APP_HOST:?" in frontend
    assert re.search(r'VITE_API_BASE_URL: "https://\$\{APP_HOST:-\$\{API_HOST:\?', prod)
    assert "GF_SERVER_ROOT_URL: https://${APP_HOST:-${API_HOST:?" in prod


def test_deploy_smoke_checks_the_api_on_the_app_origin() -> None:
    deploy = (ROOT / "deploy" / "deploy.sh").read_text(encoding="utf-8")
    smoke = deploy.split("[deploy] smoke test", 1)[1]

    assert '"https://$app_host/api/v1/health"' in smoke
    assert "back-channel logout blocked on the app origin" in smoke
    assert '"https://$app_host/grafana/"' in smoke
