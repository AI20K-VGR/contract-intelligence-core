FROM python:3.11-slim

WORKDIR /app

# ----------------------------------------------------------------------------
# Install uv (pinned version for reproducible builds).
#
# NOTE: BuildKit forbids variable expansion in `COPY --from=<arg>` AND treats
# ARG-declared-before-FROM as out-of-scope for the FROM itself, so we hardcode
# the uv tag here. To bump uv: change the line below (and rerun `uv lock` so
# backend/uv.lock captures any resolver change).
# ----------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:0.7.13 AS uv_stage
FROM python:3.11-slim

WORKDIR /app

COPY --from=uv_stage /uv /usr/local/bin/uv

# ----------------------------------------------------------------------------
# 1. Copy ONLY the lock-relevant files first.
#    Docker will cache this layer; subsequent source-code changes won't
#    invalidate `uv sync --frozen` and force re-resolution.
# ----------------------------------------------------------------------------
COPY pyproject.toml requirements.txt uv.lock ./

# ----------------------------------------------------------------------------
# 2. Install dependencies strictly against uv.lock.
#    --frozen      → fail if pyproject.toml drifts from lock (no silent drift).
#    --no-install-project → skip the `project.optional-dependencies[dev]` install
#                           for slim prod image; dev deps stay in `uv.lock` for
#                           CI runners to use with `uv sync` directly.
# ----------------------------------------------------------------------------
RUN uv sync --frozen --no-install-project

# ----------------------------------------------------------------------------
# 3. Copy source + alembic on top of the cached dependency layer.
# ----------------------------------------------------------------------------
COPY ./README.md ./
COPY src/ src/
COPY alembic.ini alembic/ ./

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "contract_intelligence.main:app", "--host", "0.0.0.0", "--port", "8000"]
