#!/usr/bin/env sh
# Docker / Linux entrypoint: wait for DB, migrate, then serve.
set -eu

echo "[entrypoint] waiting for database..."
# Retry alembic until Postgres accepts connections (handles cold start /
# password-ready races even when depends_on healthcheck already passed).
i=0
max_attempts=30
until uv run alembic upgrade heads; do
  i=$((i + 1))
  if [ "$i" -ge "$max_attempts" ]; then
    echo "[entrypoint] alembic upgrade head failed after ${max_attempts} attempts" >&2
    exit 1
  fi
  echo "[entrypoint] DB not ready or migration failed (attempt ${i}/${max_attempts}); retrying in 2s..."
  sleep 2
done
echo "[entrypoint] alembic upgrade head OK"

echo "[entrypoint] starting uvicorn"
exec uv run uvicorn contract_intelligence.main:app --host 0.0.0.0 --port 8000
