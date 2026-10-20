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

# Put the project venv first on PATH so `python` / healthchecks use installed deps.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1

# ----------------------------------------------------------------------------
# 1. Copy ONLY the lock-relevant files first.
#    Docker will cache this layer; subsequent source-code changes won't
#    invalidate `uv sync --frozen` and force re-resolution.
#    requirements.txt is exported from uv.lock (must include aiokafka, etc.).
# ----------------------------------------------------------------------------
COPY pyproject.toml requirements.txt uv.lock ./

# ----------------------------------------------------------------------------
# 2. Install dependencies strictly against uv.lock.
#    --frozen      → fail if pyproject.toml drifts from lock (no silent drift).
#    --no-dev      → runtime image only (dev extras stay in lock for CI/local).
#    --no-install-project → skip installing the local package until sources
#                           are copied; deps still come from the lockfile.
# ----------------------------------------------------------------------------
RUN uv sync --frozen --no-dev --no-install-project \
    && python -c "import aiokafka; print('aiokafka OK', aiokafka.__version__)"

# ----------------------------------------------------------------------------
# 3. Copy source + alembic on top of the cached dependency layer.
# ----------------------------------------------------------------------------
COPY ./README.md ./
COPY src/ src/
COPY alembic.ini ./
COPY alembic/ alembic/
COPY scripts/ scripts/

# Strip CR so a Windows checkout (CRLF) does not break the shebang (`sh\r`).
RUN sed -i 's/\r$//' /app/scripts/entrypoint.sh && chmod +x /app/scripts/entrypoint.sh

EXPOSE 8000

# Migrate schema to head, then start the API (Control Plane).
CMD ["/app/scripts/entrypoint.sh"]
