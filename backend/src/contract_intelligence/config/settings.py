"""Pydantic Settings — đọc env / .env.

Một số quy ước (xem ``docs/DOC-04-architecture.md`` §5 Technology stack):

- ``DATABASE_URL`` — async DSN (dùng ``postgresql+asyncpg://``).
- ``S3_*`` / ``MINIO_*`` — endpoint, access key, secret, bucket cho file storage.
- ``KAFKA_BOOTSTRAP_SERVERS`` — Kafka broker list cho event publishing.
- ``AI_SERVICE_URL`` — base URL của ai-service (Sprint 1 polling).
- ``AI2_BASE_URL`` — AI2 processing/query HTTP adapter (AI1 is Kafka-only).
- ``OTEL_*`` — OpenTelemetry exporter config.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
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
        description=(
            "Minimum TTL for MinIO presigned GET/PUT URLs in OCR commands. The "
            "actual TTL is stretched to outlive the run's AI1 deadline."
        ),
    )
    ai1_deadline_base_seconds: int = Field(
        default=600,
        ge=60,
        description="AI1 deadline per run = base + per_page x pages in the dossier.",
    )
    ai1_deadline_per_page_seconds: float = Field(
        default=30.0,
        ge=0.0,
        description="Seconds of AI1 budget added per page (see ai1_deadline_base_seconds).",
    )
    worker_watchdog_interval_seconds: float = Field(
        default=60.0,
        ge=1.0,
        le=3600.0,
        description="How often the worker fails runs whose AI1 deadline has passed.",
    )
    ai1_ocr_engine: str = Field(
        default="mistral",
        description=(
            "OCR engine id sent in ci.ai1.ocr.commands options.engine "
            "(pymupdf | openai | gemini | mistral)."
        ),
    )
    ai1_result_max_bytes: int = Field(
        default=268_435_456,
        ge=1_048_576,
        description=(
            "Largest OCR result the worker downloads when AI1 uploads it to MinIO "
            "(payload.result_ref) instead of inlining it in the Kafka message."
        ),
    )
    kafka_max_message_bytes: int = Field(
        default=10_485_760,
        ge=1_048_576,
        description=(
            "Largest Kafka record the backend sends or fetches (producer "
            "max_request_size, consumer fetch sizes). Keep equal to the broker's "
            "message.max.bytes."
        ),
    )
    kafka_dead_letter_max_value_bytes: int = Field(
        default=262_144,
        ge=0,
        description=(
            "A dead-lettered record keeps its value only up to this size; a larger "
            "one is parked as a pointer (topic/partition/offset + size + sha256) "
            "so the DLQ publish itself cannot exceed the message limit."
        ),
    )
    kafka_dead_letter_suffix: str = Field(
        default=".dlq",
        description=(
            "A record the worker cannot process is parked on <topic><suffix> "
            "(e.g. dossier_events.dlq) before its offset is committed."
        ),
    )
    worker_handler_max_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Attempts per Kafka record before it is dead-lettered.",
    )
    worker_handler_retry_backoff_seconds: float = Field(
        default=1.0,
        ge=0.0,
        le=60.0,
        description="Base backoff between attempts (doubles each retry).",
    )
    worker_ai2_max_concurrency: int = Field(
        default=4,
        ge=1,
        le=64,
        description="AI2 submit+poll hand-offs the worker runs at once.",
    )

    # -------------------------------------------------------------------------
    # AI Service (FastAPI bên ngoài — REST polling theo DOC-05c)
    # -------------------------------------------------------------------------
    # Canonical production mode is HTTP. Stub remains an explicit compatibility
    # setting for deterministic tests/demo only.
    ai_service_mode: Literal["stub", "http"] = Field(
        default="http",
        description=('"http" — canonical AI service. "stub" — explicit compatibility only.'),
    )
    ai_service_url: str = Field(default="http://localhost:8001")
    ai_service_api_key: str | None = Field(
        default=None,
        description="X-Internal-Service-Key cho internal auth (DOC-05c §3)",
    )
    ai_service_timeout_seconds: float = Field(default=30.0, gt=0)
    # AI1 is reached only over Kafka (DOC-05d); AI2 processing + query over HTTP.
    ai2_base_url: str = Field(
        default="http://localhost:8002",
        description="AI2 canonical service base URL (POST {AI2_BASE_URL}/jobs/idp).",
    )
    ai2_service_hmac_secret: str | None = Field(
        default=None,
        description="Shared local/service secret for the canonical AI2 envelope; never commit.",
    )
    ai2_service_issuer: str = Field(default="backend-service")
    ai2_service_audience: str = Field(default="vsf-ai2")
    ai2_service_key_id: str = Field(default="default")
    ai2_deadline_base_seconds: int = Field(
        default=300,
        ge=30,
        description=(
            "AI2 processing budget per run = base + per_page x pages; sent to AI2 as "
            "max_processing_seconds and used as the worker's polling deadline."
        ),
    )
    ai2_deadline_per_page_seconds: float = Field(
        default=2.0,
        ge=0.0,
        description="Seconds of AI2 budget added per page (see ai2_deadline_base_seconds).",
    )
    ai2_poll_grace_seconds: int = Field(
        default=60,
        ge=0,
        description="The worker keeps polling this long past AI2's own budget.",
    )
    ai2_max_consecutive_errors: int = Field(
        default=5,
        ge=1,
        le=100,
        description=(
            "Transient AI2 errors (timeout, 429, 5xx, transport) tolerated in a row "
            "while submitting or polling before the run fails."
        ),
    )
    ai2_idp_poll_interval_seconds: float = Field(default=0.5, ge=0.1, le=30.0)
    ai2_idp_max_polls: int = Field(default=120, ge=1, le=10_000)
    # Dossier Q&A (POST /dossiers/{id}/search → AI2 POST /query)
    ai2_query_timeout_seconds: float = Field(
        default=20.0,
        gt=0,
        le=120.0,
        description="Max wait for AI2 /query before the search box reports AI2 as unavailable.",
    )
    ai2_query_egress_allowed: bool = Field(
        default=False,
        description=(
            "Allow AI2 to call an external LLM for dossier Q&A. Fail-closed by default: "
            "AI2 answers from deterministic citation retrieval only."
        ),
    )
    ai2_query_use_vector: bool = Field(
        default=False,
        description="Ask AI2 to use vector recall for dossier Q&A (needs embeddings configured).",
    )
    query_rate_limit_per_minute: int = Field(
        default=20,
        ge=0,
        le=10_000,
        description="Max /search|/query|/ask calls per user per minute (0 = off).",
    )
    query_daily_quota_per_tenant: int = Field(
        default=2000,
        ge=0,
        le=10_000_000,
        description="Max dossier Q&A calls per tenant in a rolling 24h window (0 = off).",
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
        description=(
            "Start the API maintenance loop (dossier purge sweep). The pipeline "
            "itself runs only in the Kafka worker process."
        ),
    )
    job_lease_seconds: int = Field(default=60, ge=10, le=3600)
    job_worker_poll_interval_seconds: float = Field(default=2.0, ge=0.2, le=60.0)
    job_reaper_interval_seconds: float = Field(default=15.0, ge=1.0, le=300.0)

    # -------------------------------------------------------------------------
    # Storage (Sprint 3: local filesystem — Sprint 4: MinIO presigned URLs)
    # -------------------------------------------------------------------------
    storage_root: str = Field(default="./var/storage")
    upload_max_file_bytes: int = Field(
        default=50 * 1024 * 1024,
        ge=1,
        description="Max size of one uploaded PDF (AI1 refuses sources above 50 MB).",
    )

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
    keycloak_admin_server_url: str | None = Field(
        default=None,
        description=(
            "Base URL process backend dùng để gọi token + Admin API. "
            "Để trống thì dùng keycloak_server_url. Trong Docker, đặt địa chỉ "
            "nội bộ (http://keycloak:8080) trong khi keycloak_server_url giữ "
            "issuer public (http://localhost:8080) để JWT từ trình duyệt vẫn khớp."
        ),
    )
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

    def keycloak_admin_base_url(self) -> str:
        """URL reachable from this process for Keycloak token + Admin API."""
        return (self.keycloak_admin_server_url or self.keycloak_server_url).rstrip("/")

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
        default="http://localhost:5173/",
        description="Trang đăng nhập sau khi người dùng đặt mật khẩu xong.",
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

    @model_validator(mode="after")
    def _refuse_dev_secrets_outside_dev(self) -> Settings:
        """Refuse to start in staging/prod with a dev default or placeholder secret.

        The defaults above let ``docker compose up`` work locally; on a server
        they would be public passwords. Only field names are reported, never
        the values.
        """
        if self.env not in _GUARDED_ENVS:
            return self
        secrets = {
            "DATABASE_URL (password)": urlsplit(self.database_url).password,
            "S3_SECRET_KEY": self.s3_secret_key,
            "MINIO_SECRET_KEY": self.minio_secret_key,
            "KEYCLOAK_ADMIN_CLIENT_SECRET": self.keycloak_admin_client_secret,
            "KEYCLOAK_WEBHOOK_SECRET": self.keycloak_webhook_secret,
            "AI2_SERVICE_HMAC_SECRET": self.ai2_service_hmac_secret,
        }
        problems = [name for name, value in secrets.items() if _is_dev_secret(value)]
        if not self.keycloak_webhook_verify_signature:
            problems.append("KEYCLOAK_WEBHOOK_VERIFY_SIGNATURE (must be true)")
        if problems:
            names = ", ".join(problems)
            msg = f"ENV={self.env} refuses dev default or placeholder settings: {names}"
            raise ValueError(msg)
        return self


# Environments reachable from outside a developer machine.
_GUARDED_ENVS = frozenset({"staging", "prod"})
# Values shipped as defaults here or as placeholders in deploy/.env.prod.example.
_DEV_SECRET_VALUES = frozenset({"password123", "changeme", "generate", "secret"})


def _is_dev_secret(value: str | None) -> bool:
    """True for a missing secret, a known default/placeholder, or a ``*_dev`` value."""
    stripped = (value or "").strip()
    return (
        not stripped or stripped.lower() in _DEV_SECRET_VALUES or stripped.lower().endswith("_dev")
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton accessor — cache trong suốt lifetime process.

    Test có thể clear cache qua ``get_settings.cache_clear()``.
    """
    return Settings()
