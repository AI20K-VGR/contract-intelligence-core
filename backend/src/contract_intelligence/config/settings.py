"""Pydantic Settings — đọc env / .env.

Một số quy ước (xem ``docs/DOC-04-architecture.md`` §5 Technology stack):

- ``DATABASE_URL`` — async DSN (dùng ``postgresql+asyncpg://``).
- ``MINIO_*`` — endpoint, access key, secret, bucket cho file storage.
- ``AI_SERVICE_URL`` — base URL của ai-service (Sprint 1 polling).
- ``OTEL_*`` — OpenTelemetry exporter config.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Root settings — load từ env / ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # Runtime
    # -------------------------------------------------------------------------
    env: Literal["dev", "test", "staging", "prod"] = Field(default="dev")
    debug: bool = Field(default=False)

    # -------------------------------------------------------------------------
    # Database (async DSN)
    # -------------------------------------------------------------------------
    database_url: str = Field(
        default="postgresql+asyncpg://ci:ci@localhost:5432/ci",
        description="Async SQLAlchemy DSN — dùng postgresql+asyncpg driver",
    )
    database_pool_size: int = Field(default=10, ge=1, le=100)
    database_max_overflow: int = Field(default=20, ge=0, le=200)
    database_echo: bool = Field(default=False)

    # -------------------------------------------------------------------------
    # MinIO (S3-compatible)
    # -------------------------------------------------------------------------
    minio_endpoint: str = Field(default="localhost:9000")
    minio_access_key: str = Field(default="minioadmin")
    minio_secret_key: str = Field(default="minioadmin")
    minio_bucket_pdf: str = Field(default="ci-pdf")
    minio_bucket_render: str = Field(default="ci-render")
    minio_secure: bool = Field(default=False)

    # -------------------------------------------------------------------------
    # AI Service (FastAPI bên ngoài — REST polling trong Sprint 1)
    # -------------------------------------------------------------------------
    ai_service_url: str = Field(default="http://localhost:8001")
    ai_service_api_key: str | None = Field(default=None)
    ai_service_timeout_seconds: float = Field(default=30.0, gt=0)

    # -------------------------------------------------------------------------
    # OpenTelemetry
    # -------------------------------------------------------------------------
    otel_service_name: str = Field(default="contract-intelligence-backend")
    otel_exporter_otlp_endpoint: str | None = Field(default=None)
    otel_exporter_console: bool = Field(default=False)  # debug only

    # -------------------------------------------------------------------------
    # CORS
    # -------------------------------------------------------------------------
    cors_allow_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    cors_allow_credentials: bool = Field(default=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton accessor — cache trong suốt lifetime process.

    Test có thể clear cache qua ``get_settings.cache_clear()``.
    """
    return Settings()
