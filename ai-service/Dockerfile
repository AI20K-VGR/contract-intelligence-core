# syntax=docker/dockerfile:1.7
# AI1 OCR service + Kafka worker image
FROM ghcr.io/astral-sh/uv:0.7.13 AS uv_stage
FROM python:3.11-slim

WORKDIR /app

COPY --from=uv_stage /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock ./

# Base OCR + Kafka + cloud OCR SDKs (Mistral/OpenAI/Gemini).
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --extra kafka --extra mistral --extra openai --extra gemini --no-dev --no-install-project

COPY README.md ./
COPY configs/ configs/
COPY src/ src/

# Default: Kafka OCR worker (HTTP API is optional override).
CMD ["uv", "run", "--extra", "kafka", "--extra", "mistral", "python", "-m", "contract_ocr.infrastructure.kafka_worker"]
