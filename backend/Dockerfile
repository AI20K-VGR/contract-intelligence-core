FROM python:3.11-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install deps
COPY pyproject.toml requirements.txt ./
RUN uv sync --frozen --no-install-project

# Copy source
COPY src/ src/
COPY alembic.ini alembic/ ./

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "contract_intelligence.main:app", "--host", "0.0.0.0", "--port", "8000"]
