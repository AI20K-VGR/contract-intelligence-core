"""Static contract gate for the reproducible local/E2E and online topologies.

This intentionally does not interpolate Compose files or load a secret-bearing
environment.  It catches drift between the canonical ``docker-compose.yml``,
the compatibility E2E file, and the production override before a build.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


REQUIRED_FLAGS = (
    "AI2_SEMANTIC_ENABLED",
    "AI2_PROCESSING_EGRESS_ALLOWED",
    "AI2_QUERY_EGRESS_ALLOWED",
    "AI2_QUERY_USE_LLM",
    "AI2_QUERY_USE_VECTOR",
    "AI2_VECTOR_RECALL_ENABLED",
    "AI2_EMBEDDING_DISCOVERY_ENABLED",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    e2e = (root / "docker-compose.yml").read_text(encoding="utf-8")
    compatibility = (root / "docker-compose.golive-e2e.yml").read_text(encoding="utf-8")
    prod = (root / "deploy" / "compose.prod.yml").read_text(encoding="utf-8")
    env = (root / ".env.e2e.example").read_text(encoding="utf-8")
    client = (root / "frontend" / "src" / "api" / "client.ts").read_text(encoding="utf-8")
    deploy = (root / "deploy" / "deploy.sh").read_text(encoding="utf-8")
    errors: list[str] = []

    for name, text in {
        "frontend service": e2e,
        "frontend build": e2e,
        "frontend healthcheck": e2e,
        "frontend production service": prod,
    }.items():
        needle = {
            "frontend service": "  frontend:",
            "frontend build": "context: ./frontend",
            "frontend healthcheck": "http://127.0.0.1/healthz",
            "frontend production service": "  frontend:",
        }[name]
        if needle not in text:
            errors.append(f"missing {name}: {needle}")

    for flag in REQUIRED_FLAGS:
        if f"{flag}=true" not in env:
            errors.append(f"E2E example does not enable {flag}")

    def service_block(text: str, service: str) -> str:
        marker = f"  {service}:"
        start = text.find(marker)
        if start < 0:
            return ""
        rest = text[start + len(marker) :]
        next_service = re.search(r"\n  [A-Za-z0-9_.-]+:\s*(?:#.*)?$", rest, re.MULTILINE)
        return rest if next_service is None else rest[: next_service.start()]

    def has_enabled_flag(block: str, flag: str) -> bool:
        # Canonical E2E uses env overrides with a true default; production uses
        # an explicit true value. Both are full-featured, fail-closed profiles.
        return any(
            needle in block
            for needle in (f"{flag}: ${{{flag}:-true}}", f'{flag}: "true"', f"{flag}: true")
        )

    canonical_ai2 = service_block(e2e, "ai2-service")
    for label, compose in (("canonical", e2e), ("compatibility", compatibility), ("production", prod)):
        block = service_block(compose, "ai2-service")
        if not block:
            errors.append(f"{label} compose is missing ai2-service")
            continue
        for flag in REQUIRED_FLAGS:
            if not has_enabled_flag(block, flag):
                errors.append(f"{label} ai2-service does not enable {flag}")
        if "ai2_data:/app/data/ai2" in block:
            errors.append(f"{label} AI2 still mounts the legacy SQLite data volume")

    compatibility_services = {line.strip()[:-1] for line in compatibility.splitlines() if line.startswith("  ") and line.endswith(":")}
    canonical_services = {line.strip()[:-1] for line in e2e.splitlines() if line.startswith("  ") and line.endswith(":")}
    if "frontend" not in compatibility_services:
        errors.append("compatibility golive-e2e compose is missing the frontend service")
    if "frontend" not in canonical_services:
        errors.append("canonical compose is missing the frontend service")
    prod_ai2 = service_block(prod, "ai2-service")
    if "ports: !reset []" not in prod_ai2 or "http://ai2-service:8002" not in prod:
        errors.append("production AI2 is not internal-only")
    if "AI2_DATABASE_URL: postgresql+psycopg://ai2:" not in prod_ai2:
        errors.append("production AI2 is not wired to the PostgreSQL ai2 role")
    if "/readyz" not in deploy or "ai2-service" not in deploy:
        errors.append("production deploy does not wait for AI2 /readyz")
    if "http://localhost:8002/readyz" not in canonical_ai2:
        errors.append("canonical AI2 healthcheck does not require /readyz")
    if "127.0.0.1:8080" in client:
        errors.append("frontend client still has the wrong API fallback")
    for path in (root / "frontend" / "Dockerfile", root / "frontend" / "nginx.conf"):
        if not path.is_file():
            errors.append(f"missing frontend image file: {path.relative_to(root)}")
    caddy = (root / "deploy" / "Caddyfile").read_text(encoding="utf-8")
    bootstrap = (root / "deploy" / "bootstrap.sh").read_text(encoding="utf-8")
    if "{$APP_HOST}" not in caddy or "reverse_proxy frontend:80" not in caddy:
        errors.append("Caddy does not route APP_HOST to the frontend")
    if "s/^APP_HOST=.*/APP_HOST=app-$dashed.sslip.io/" not in bootstrap:
        errors.append("bootstrap does not derive APP_HOST from the server IP")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("PASS: online/e2e topology contract")
    print("PASS: full semantic + LLM + vector flags are present in the E2E example")
    print("PASS: AI2 production service is internal-only and has no SQLite data mount")
    print("PASS: frontend image and browser API fallback are configured")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
