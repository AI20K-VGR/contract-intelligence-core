"""Static/runtime contract gate for the PostgreSQL and full-provider topology."""

from __future__ import annotations

import argparse
from pathlib import Path
import re


FLAGS = (
    "AI2_SEMANTIC_ENABLED",
    "AI2_PROCESSING_EGRESS_ALLOWED",
    "AI2_QUERY_EGRESS_ALLOWED",
    "AI2_QUERY_USE_LLM",
    "AI2_QUERY_USE_VECTOR",
    "AI2_VECTOR_RECALL_ENABLED",
)

SEMANTIC_PROFILE_KEYS = (
    "version",
    "contract_type",
    "context_bounds",
    "alias_proposal_minimum_length",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    base = (root / "docker-compose.yml").read_text(encoding="utf-8")
    prod = (root / "deploy" / "compose.prod.yml").read_text(encoding="utf-8")
    compatibility = (root / "docker-compose.golive-e2e.yml").read_text(encoding="utf-8")
    engine = (root / "ai-service" / "app" / "db" / "engine.py").read_text(encoding="utf-8")
    api = (root / "ai-service" / "app" / "api" / "main.py").read_text(encoding="utf-8")
    deploy = (root / "deploy" / "deploy.sh").read_text(encoding="utf-8")
    errors: list[str] = []
    versions = [root / "backend" / "alembic" / "versions" / f"v{i}__" for i in range(20, 24)]

    if "AI2_DATABASE_URL" not in base or "AI2_REQUIRE_DATABASE" not in base:
        errors.append("canonical compose does not require AI2_DATABASE_URL")
    for label, text in (("canonical", base), ("compatibility", compatibility)):
        for service in ("backend", "backend-worker"):
            match = re.search(rf"^  {re.escape(service)}:\s*(?:#.*)?$", text, re.MULTILINE)
            block = text[match.end() :] if match else ""
            if match is None:
                errors.append(f"{label} compose is missing {service}")
                continue
            next_service = re.search(r"\n  [A-Za-z0-9_.-]+:\s*(?:#.*)?$", block, re.MULTILINE)
            if next_service:
                block = block[: next_service.start()]
            if "AI2_SEMANTIC_ENABLED:" not in block:
                errors.append(f"{label} {service} does not enable semantic processing")
            if "AI2_SEMANTIC_PROFILE_CONFIG:" not in block:
                errors.append(f"{label} {service} is missing AI2_SEMANTIC_PROFILE_CONFIG")
            for key in SEMANTIC_PROFILE_KEYS:
                if key not in block:
                    errors.append(f"{label} {service} semantic profile misses {key}")
            if service == "backend-worker" and not re.search(
                r"\n\s+backend:\s*\n\s+condition:\s+service_healthy\s*$",
                block,
                re.MULTILINE,
            ):
                errors.append(f"{label} backend-worker does not wait for healthy backend migrations")
    if "ai2_data:/app/data/ai2" in base or "ai2_data:/app/data/ai2" in prod:
        errors.append("runtime still mounts the legacy SQLite volume")
    if "postgresql+psycopg://ai2:" not in prod:
        errors.append("online override does not bind the ai2 PostgreSQL role")
    if "ports: !reset []" not in prod:
        errors.append("online override does not remove host ports")
    if "@app.get(\"/readyz\")" not in api:
        errors.append("AI2 readiness endpoint is missing")
    if "ai2-service" not in deploy or "/readyz" not in deploy:
        errors.append("online deploy does not wait for AI2 full readiness")
    if "AI2_DATABASE_URL must select PostgreSQL" not in engine:
        errors.append("AI2 database guard does not reject non-PostgreSQL URLs")
    for flag in FLAGS:
        if f'{flag}: "true"' not in prod:
            errors.append(f"online override does not force {flag}=true")
    for prefix in versions:
        if not list(prefix.parent.glob(prefix.name + "*.py")):
            errors.append(f"migration prefix missing: {prefix.name}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("PASS: PostgreSQL/pgvector runtime contract")
    print("PASS: online AI2 uses schema ai2 and has no public/SQLite runtime path")
    print("PASS: full flags and /readyz fail-fast capability contract")
    print("PASS: migration chain v20-v23 is present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
