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
    # AI Service (FastAPI bên ngoài — REST polling theo DOC-05c)
    # -------------------------------------------------------------------------
    # Mode chọn client: "stub" (default — canned responses) hoặc "http" (gọi thật).
    # Khi ai-service team ready, set AI_SERVICE_MODE=http qua env.
    ai_service_mode: Literal["stub", "http"] = Field(
        default="stub",
        description=(
            '"stub" — in-memory canned responses (mặc định Sprint 3). '
            '"http" — gọi HTTP thật tới ai_service_url khi ai-service sẵn sàng.'
        ),
    )
    ai_service_url: str = Field(default="http://localhost:8001")
    ai_service_api_key: str | None = Field(
        default=None,
        description="X-Internal-Service-Key cho internal auth (DOC-05c §3)",
    )
    ai_service_timeout_seconds: float = Field(default=30.0, gt=0)
    # Background dispatcher tuning
    ai_dispatcher_poll_interval_seconds: float = Field(default=1.5, ge=0.1, le=60.0)
    ai_dispatcher_max_polls: int = Field(default=200, ge=10, le=10_000)
    ai_dispatcher_max_attempts: int = Field(default=3, ge=1, le=10)

    # -------------------------------------------------------------------------
    # Storage (Sprint 3: local filesystem — Sprint 4: MinIO presigned URLs)
    # -------------------------------------------------------------------------
    storage_root: str = Field(default="./var/storage")

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

    # -------------------------------------------------------------------------
    # Authentication — Sprint 1 (local HS256) / Production (Keycloak OIDC)
    # -------------------------------------------------------------------------
    auth_mode: Literal["local", "keycloak"] = Field(
        default="local",
        description=(
            '"local": self-issued HS256 JWT (Sprint 1). '
            '"keycloak": RS256 JWT verified via Keycloak JWKS (production).'
        ),
    )
    jwt_secret_key: str = Field(
        default="dev-secret-change-me-in-prod-32chars!!",
        description="Secret key cho HS256 JWT signing. PHẢI đổi trong production.",
    )
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_token_expire_minutes: int = Field(default=60, ge=5, le=1440)
    jwt_refresh_token_expire_days: int = Field(default=7, ge=1, le=30)

    # Keycloak (production — dùng khi auth_mode = "keycloak")
    keycloak_server_url: str | None = Field(
        default=None,
        description="VD: https://sso.company.com — auto-detect .well-known nếu None",
    )
    keycloak_realm: str = Field(default="contract-intelligence")
    keycloak_client_id: str = Field(default="ci-backend")
    keycloak_jwks_uri: str | None = Field(
        default=None,
        description=(
            "URL tới JWKS endpoint. "
            "Nếu None, tự build từ keycloak_server_url/realms/{realm}/protocol/openid-connect/certs"
        ),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton accessor — cache trong suốt lifetime process.

    Test có thể clear cache qua ``get_settings.cache_clear()``.
    """
    return Settings()
