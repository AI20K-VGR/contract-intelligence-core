"""Pydantic Settings — đọc env / .env.

Một số quy ước (xem ``docs/DOC-04-architecture.md`` §5 Technology stack):

- ``DATABASE_URL`` — async DSN (dùng ``postgresql+asyncpg://``).
- ``S3_*`` / ``MINIO_*`` — endpoint, access key, secret, bucket cho file storage.
- ``KAFKA_BOOTSTRAP_SERVERS`` — Kafka broker list cho event publishing.
- ``AI_SERVICE_URL`` — base URL của ai-service (Sprint 1 polling).
- ``AI1_BASE_URL`` / ``AI2_BASE_URL`` — OCR / Semantics HTTP adapters.
- ``OTEL_*`` — OpenTelemetry exporter config.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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
        default="postgresql+asyncpg://ci:ci_secret_dev@localhost:5434/contract_intelligence",
        description="Async SQLAlchemy DSN — dùng postgresql+asyncpg driver",
    )
    database_pool_size: int = Field(default=10, ge=1, le=100)
    database_max_overflow: int = Field(default=20, ge=0, le=200)
    database_echo: bool = Field(default=False)

    # -------------------------------------------------------------------------
    # MinIO / S3-compatible object storage
    # -------------------------------------------------------------------------
    s3_endpoint_url: str = Field(default="http://localhost:9000")
    s3_access_key: str = Field(default="admin")
    s3_secret_key: str = Field(default="password123")
    s3_bucket_name: str = Field(default="dossiers")
    # Legacy MinIO_* aliases (kept for existing LocalFileStorage / adapters)
    minio_endpoint: str = Field(default="localhost:9000")
    minio_access_key: str = Field(default="admin")
    minio_secret_key: str = Field(default="password123")
    minio_bucket_pdf: str = Field(default="dossiers")
    minio_bucket_render: str = Field(default="ci-render")
    minio_secure: bool = Field(default=False)

    # -------------------------------------------------------------------------
    # Kafka (event bus)
    # -------------------------------------------------------------------------
    kafka_bootstrap_servers: str = Field(default="localhost:9093")
    kafka_ai1_ocr_commands_topic: str = Field(
        default="ci.ai1.ocr.commands",
        description="Backend → AI1 OCR command topic (DOC-05d).",
    )
    kafka_ai1_ocr_results_topic: str = Field(
        default="ci.ai1.ocr.results",
        description="AI1 → Backend OCR result topic (DOC-05d).",
    )
    kafka_backend_ai1_results_group_id: str = Field(
        default="ci-backend-ai1-results",
        description="Consumer group for AI1 OCR results.",
    )
    kafka_dossier_events_topic: str = Field(
        default="dossier_events",
        description="Internal domain events (dossier.uploaded).",
    )
    kafka_orchestrator_group_id: str = Field(
        default="ci-backend-orchestrator",
        description="Consumer group for dossier_events orchestrator.",
    )
    kafka_presign_expires_seconds: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="TTL for MinIO presigned GET/PUT URLs embedded in OCR commands.",
    )
    ai1_ocr_engine: str = Field(
        default="mistral",
        description=(
            "OCR engine id sent in ci.ai1.ocr.commands options.engine "
            "(pymupdf | openai | gemini | mistral)."
        ),
    )

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
    # External AI1 (OCR) / AI2 (Semantics) base URLs for Kafka-worker HTTP adapters.
    ai1_base_url: str = Field(
        default="http://localhost:8001/api/v1",
        description="AI1 OCR service base URL (POST {AI1_BASE_URL}/jobs).",
    )
    ai2_base_url: str = Field(
        default="http://localhost:8002/api/v1",
        description="AI2 Semantics service base URL (POST {AI2_BASE_URL}/process).",
    )
    # Background dispatcher tuning
    ai_dispatcher_poll_interval_seconds: float = Field(default=1.5, ge=0.1, le=60.0)
    ai_dispatcher_max_polls: int = Field(default=200, ge=10, le=10_000)
    ai_dispatcher_max_attempts: int = Field(default=3, ge=1, le=10)

    # -------------------------------------------------------------------------
    # Postgres job queue (no Redis / Celery)
    # -------------------------------------------------------------------------
    job_queue_enabled: bool = Field(
        default=True,
        description="Start in-process worker + lease reaper on app lifespan.",
    )
    job_lease_seconds: int = Field(default=60, ge=10, le=3600)
    job_worker_poll_interval_seconds: float = Field(default=2.0, ge=0.2, le=60.0)
    job_reaper_interval_seconds: float = Field(default=15.0, ge=1.0, le=300.0)

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
    cors_allow_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )
    cors_allow_credentials: bool = Field(default=True)

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _parse_cors_allow_origins(cls, v: object) -> object:
        """Accept BOTH JSON array AND comma-separated string từ env.

        Design contract (xem ``.env.example``):
            CORS_ALLOW_ORIGINS=http://localhost:3000,http://localhost:5173

        Field được annotate với ``NoDecode`` để pydantic-settings KHÔNG tự
        JSON-decode env value (mặc định 2.x treat ``list[str]`` như complex
        type → bắt buộc JSON, fail với comma-separated). Validator này xử lý
        cả hai format để vẫn tương thích với JSON-array users.
        """
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                # JSON array — parse thủ công rồi trả về list[str]
                import json

                parsed = json.loads(stripped)
                if not isinstance(parsed, list):
                    raise ValueError(
                        f"cors_allow_origins phải là list, nhận: {type(parsed).__name__}"
                    )
                return [str(origin).strip() for origin in parsed if str(origin).strip()]
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        return v

    # -------------------------------------------------------------------------
    # Authentication — Keycloak SSO (single source of truth cho token issuance)
    #
    # Backend TUYỆT ĐỐI KHÔNG issue Access Token / Refresh Token.
    # Frontend gọi thẳng Keycloak để login + refresh, mang JWT đã verify
    # tới backend. Backend chỉ làm nhiệm vụ decode + verify chữ ký RS256
    # thông qua Keycloak JWKS endpoint.
    #
    # Luồng chuẩn:
    #   1. User đăng nhập trên frontend (React) qua Keycloak login page
    #   2. Keycloak trả access_token (RS256) + refresh_token cho frontend
    #   3. Frontend giữ refresh_token, gửi access_token trong header:
    #          Authorization: Bearer <access_token>
    #   4. Backend verify chữ ký bằng public key từ Keycloak JWKS
    #   5. Khi access_token hết hạn, frontend gọi thẳng Keycloak refresh
    #      endpoint để lấy access_token mới (KHÔNG qua backend).
    # -------------------------------------------------------------------------
    auth_mode: Literal["keycloak"] = Field(
        default="keycloak",
        description=(
            'Chế độ xác thực. Hiện chỉ hỗ trợ "keycloak" — backend verify JWT '
            "qua Keycloak JWKS, không issue token."
        ),
    )

    # Keycloak OIDC — bắt buộc
    keycloak_server_url: str = Field(
        default="https://sso.company.com",
        description="VD: https://sso.company.com — base URL của Keycloak server.",
    )
    keycloak_realm: str = Field(
        default="contract-intelligence",
        description="Keycloak realm name.",
    )
    keycloak_client_id: str = Field(
        default="ci-backend",
        description=(
            "Client ID đăng ký trong Keycloak cho backend này. Dùng để verify `aud` claim."
        ),
    )
    keycloak_jwks_uri: str | None = Field(
        default=None,
        description=(
            "URL tới JWKS endpoint. "
            "Nếu None, tự build từ keycloak_server_url/realms/{realm}/protocol/openid-connect/certs"
        ),
    )
    keycloak_audience: str | None = Field(
        default=None,
        description=(
            "Expected `aud` claim. Nếu None, skip audience check "
            "(khuyến nghị: set = keycloak_client_id)."
        ),
    )
    keycloak_role_map: dict[str, str] = Field(
        default_factory=lambda: {
            "ci_operator": "OPERATOR",
            "ci_reviewer": "REVIEWER",
            "ci_administrator": "ADMINISTRATOR",
        },
        description=(
            "Map Keycloak realm_access.roles[] → RBAC role nội bộ. "
            "Key là Keycloak role name, value là RBAC role trong backend."
        ),
    )
    keycloak_jwks_cache_ttl_seconds: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="TTL cache cho JWKS public keys (giây). Default 1 giờ.",
    )

    # -------------------------------------------------------------------------
    # Keycloak Admin REST API — dùng để fetch full user profile khi nhận
    # raw webhook event từ Phase Two keycloak-events extension.
    #
    # Backend sử dụng Client Credentials Grant (Service Account) để lấy
    # access token cho Admin API, sau đó gọi GET /admin/realms/{realm}/users/{id}.
    #
    # Service account phải có realm-management client role `view-users` —
    # xem ``keycloak/realm-export.json`` (servicesAccountsEnabled + role grant).
    # -------------------------------------------------------------------------
    keycloak_admin_client_id: str = Field(
        default="contract-intel-backend",
        description=(
            "Client ID cho Service Account dùng để gọi Admin REST API. "
            "Mặc định trùng với keycloak_client_id vì contract-intel-backend "
            "đã có serviceAccountsEnabled=true."
        ),
    )
    keycloak_admin_client_secret: str = Field(
        default="backend_secret_dev",
        description="Client secret cho Service Account — lấy từ Keycloak Admin Console.",
    )
    keycloak_admin_token_ttl_seconds: int = Field(
        default=300,
        ge=60,
        le=3600,
        description=(
            "TTL cache cho Admin API access token (giây). Token Keycloak cấp "
            "qua Client Credentials có lifespan mặc định 5 phút; refresh trước "
            "khi hết hạn bằng cách giữ TTL < lifespan thực tế."
        ),
    )
    keycloak_admin_http_timeout_seconds: float = Field(
        default=10.0,
        gt=0,
        le=60,
        description="Timeout cho HTTP call tới Keycloak Admin REST API (giây).",
    )

    # -------------------------------------------------------------------------
    # Keycloak invite email (execute-actions-email / UPDATE_PASSWORD)
    # -------------------------------------------------------------------------
    keycloak_invite_client_id: str = Field(
        default="contract-intel-frontend",
        description="OIDC client_id embedded in the invite / password-set email link.",
    )
    keycloak_invite_lifespan_seconds: int = Field(
        default=43200,
        ge=300,
        le=604800,
        description="Invite link lifespan in seconds (default 12h).",
    )
    keycloak_invite_redirect_uri: str = Field(
        default="http://localhost:5173/auth/callback",
        description="redirect_uri after the user completes UPDATE_PASSWORD.",
    )

    # -------------------------------------------------------------------------
    # Keycloak → backend webhook signature verification
    #
    # Phase Two keycloak-events extension ký mọi webhook payload bằng
    # HMAC-SHA256 với shared secret (env WEBHOOK_SECRET trong docker-compose).
    # Backend verify chữ ký trước khi parse + xử lý event.
    # -------------------------------------------------------------------------
    keycloak_webhook_secret: str = Field(
        default="ci_webhook_shared_secret_dev",
        description=(
            "HMAC shared secret — PHẢI khớp với WEBHOOK_SECRET env var "
            "trên Keycloak container (docker-compose.yml)."
        ),
    )
    keycloak_webhook_verify_signature: bool = Field(
        default=True,
        description=(
            "Bật/tắt HMAC verification. Set false CHỈ trong local debugging. "
            "Production BẮT BUỘC phải bật."
        ),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton accessor — cache trong suốt lifetime process.

    Test có thể clear cache qua ``get_settings.cache_clear()``.
    """
    return Settings()
