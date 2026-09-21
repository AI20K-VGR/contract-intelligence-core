#!/usr/bin/env sh
# Docker / Linux entrypoint: migrate then serve.
set -eu
echo "[entrypoint] alembic upgrade head"
uv run alembic upgrade head
echo "[entrypoint] starting uvicorn"
exec uv run uvicorn contract_intelligence.main:app --host 0.0.0.0 --port 8000
