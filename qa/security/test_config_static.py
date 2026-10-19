"""Static checks on repo config: secrets, production exposure, hardening.

No network: these read files in the repo, so they also run in CI.
"""

from __future__ import annotations

import json
import re
import subprocess

import pytest

from lib.config import REPO_ROOT

pytestmark = [pytest.mark.security, pytest.mark.static]

PROD_COMPOSE = REPO_ROOT / "deploy" / "compose.prod.yml"
CADDYFILE = REPO_ROOT / "deploy" / "Caddyfile"


def _tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout
    return out.splitlines()


def test_no_env_files_tracked():
    """Only *.example env files are committed; real .env files are ignored."""
    tracked = [f for f in _tracked_files() if re.search(r"(^|/)\.env(\.|$)", f)]
    real = [f for f in tracked if not f.endswith(".example")]
    assert real == []


SECRET_PATTERNS = {
    "OpenAI key": re.compile(r"sk-(proj-)?[A-Za-z0-9_-]{32,}"),
    "AWS access key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "private key": re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "GitHub token": re.compile(r"gh[pousr]_[A-Za-z0-9]{36}"),
    "Slack token": re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
}
SCAN_SUFFIXES = (
    ".py", ".ts", ".tsx", ".js", ".yml", ".yaml", ".json", ".toml", ".md", ".sh", ".ps1", ".example", ".conf",
)


def test_no_hardcoded_provider_secrets():
    """No API keys / private keys committed in source, config or docs."""
    hits = []
    for rel in _tracked_files():
        if not rel.endswith(SCAN_SUFFIXES) or "node_modules" in rel:
            continue
        path = REPO_ROOT / rel
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for name, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                hits.append(f"{rel}: {name}")
    assert hits == []


def test_prod_compose_publishes_only_caddy():
    """In production only Caddy publishes ports; DBs, Kafka, MinIO, AI2, Keycloak stay internal."""
    text = PROD_COMPOSE.read_text(encoding="utf-8")
    services = re.split(r"\n  (?=[a-z0-9-]+:\n)", text)
    published = []
    for block in services:
        name = block.split(":", 1)[0].strip()
        if re.search(r"\n    ports:\s*\n\s+- ", block) and name != "caddy":
            published.append(name)
    assert published == []
    for internal in ("backend-db", "keycloak-db", "kafka", "minio", "ai2-service"):
        block = next((b for b in services if b.startswith(internal + ":") or b.strip().startswith(internal + ":")), "")
        if block:
            assert "ports: !reset []" in block, f"{internal} may publish ports in prod"


def test_prod_keycloak_enables_brute_force_protection():
    """Prod Keycloak setup turns on brute-force lockout (dev realm has it off)."""
    script = (REPO_ROOT / "deploy" / "keycloak_configure.py").read_text(encoding="utf-8")
    assert '"bruteForceProtected": True' in script


def test_dev_realm_has_no_extra_public_clients():
    """Realm export: only the SPA is public, and it has Direct Access Grants off."""
    realm = json.loads((REPO_ROOT / "keycloak" / "realm-export.json").read_text(encoding="utf-8"))
    ours = [c for c in realm["clients"] if c["clientId"].startswith("contract-intel")]
    public = [c["clientId"] for c in ours if c.get("publicClient")]
    assert public == ["contract-intel-frontend"]
    spa = next(c for c in ours if c["clientId"] == "contract-intel-frontend")
    assert not spa.get("directAccessGrantsEnabled")
    assert "*" not in (spa.get("redirectUris") or [])
    assert "*" not in (spa.get("webOrigins") or [])


def test_prod_caddy_sets_hsts_and_nosniff():
    """Prod reverse proxy sends HSTS and X-Content-Type-Options."""
    text = CADDYFILE.read_text(encoding="utf-8")
    assert "Strict-Transport-Security" in text
    assert 'X-Content-Type-Options "nosniff"' in text


@pytest.mark.xfail(
    reason="FINDING SEC-01: no X-Frame-Options / CSP frame-ancestors on the frontend (clickjacking)",
    strict=True,
)
def test_prod_caddy_blocks_framing():
    """Prod reverse proxy forbids framing the app."""
    text = CADDYFILE.read_text(encoding="utf-8")
    assert "X-Frame-Options" in text or "frame-ancestors" in text


def test_backend_refuses_dev_secrets_in_prod():
    """Backend settings carry a prod guard that refuses placeholder secrets."""
    settings = (REPO_ROOT / "backend" / "src" / "contract_intelligence" / "config" / "settings.py").read_text(
        encoding="utf-8"
    )
    assert "_GUARDED_ENVS" in settings and '"prod"' in settings


def test_prod_cors_example_has_no_wildcard():
    """deploy/.env.prod.example does not allow '*' as a CORS origin."""
    example = (REPO_ROOT / "deploy" / ".env.prod.example").read_text(encoding="utf-8")
    line = next((row for row in example.splitlines() if row.startswith("CORS_ALLOW_ORIGINS")), "")
    assert "*" not in line
