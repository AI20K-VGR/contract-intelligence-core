"""Target stack settings, read from QA_* environment variables.

Defaults point at the local `docker compose up` stack and the users seeded in
keycloak/realm-export.json, so `pytest` works with no setup on a dev machine.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = Path(os.getenv("QA_REPORTS_DIR", REPO_ROOT / "qa" / "reports"))


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value else default


def _flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class User:
    role: str
    username: str
    password: str


@dataclass(frozen=True)
class Config:
    backend_url: str = _env("QA_BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
    ai2_url: str = _env("QA_AI2_URL", "http://127.0.0.1:8002").rstrip("/")
    frontend_url: str = _env("QA_FRONTEND_URL", "http://localhost:5173").rstrip("/")
    minio_url: str = _env("QA_MINIO_URL", "http://127.0.0.1:9000").rstrip("/")
    keycloak_url: str = _env("QA_KEYCLOAK_URL", "http://localhost:8080").rstrip("/")
    realm: str = _env("QA_KEYCLOAK_REALM", "contract-intelligence")
    client_id: str = _env("QA_KEYCLOAK_CLIENT_ID", "contract-intel-frontend")
    redirect_uri: str = _env("QA_KEYCLOAK_REDIRECT_URI", "http://localhost:5173/auth/callback")
    allowed_origin: str = _env("QA_ALLOWED_ORIGIN", "http://localhost:5173")
    users: dict[str, User] = field(
        default_factory=lambda: {
            "ADMINISTRATOR": User(
                "ADMINISTRATOR",
                _env("QA_ADMIN_USER", "admin@ci.local"),
                _env("QA_ADMIN_PASSWORD", "Admin@CI123"),
            ),
            "OPERATOR": User(
                "OPERATOR",
                _env("QA_OPERATOR_USER", "operator@ci.local"),
                _env("QA_OPERATOR_PASSWORD", "Operator@CI123"),
            ),
            "REVIEWER": User(
                "REVIEWER",
                _env("QA_REVIEWER_USER", "reviewer@ci.local"),
                _env("QA_REVIEWER_PASSWORD", "Reviewer@CI123"),
            ),
        }
    )
    # Target environment: "local" (default) or "prod". On prod the suite treats
    # the stack as hardened and shared: interactive docs are blocked, AI2 is not
    # reachable on its own port, a WAF (Cloudflare) may answer 403, and no load
    # test runs. Set QA_ENV=prod when pointing at contract-intelligence.tech.
    target_env: str = _env("QA_ENV", "local").strip().lower()
    # Is AI2 reachable directly on QA_AI2_URL (dev compose publishes 8002)?
    # Off on prod, where AI2 lives only inside ci-network.
    ai2_direct: bool = _env("QA_AI2_DIRECT", "0" if _env("QA_ENV", "local") == "prod" else "1") not in {"0", "false", ""}
    # A WAF in front of the API may answer injection probes with 403 instead of
    # letting the app return 404/422 — both are acceptable "handled" outcomes.
    waf_in_front: bool = _flag("QA_WAF_IN_FRONT") or _env("QA_ENV", "local") == "prod"

    # Uploading a valid PDF starts OCR + AI2. Opt-in so nobody pays for OCR by
    # running the default suite (see qa/README.md, "free mode").
    run_pipeline: bool = _flag("QA_RUN_PIPELINE")
    pipeline_timeout_s: int = int(_env("QA_PIPELINE_TIMEOUT_S", "600"))
    # Performance load shape and budgets.
    # NOTE: there is no numeric performance NFR yet — DOC-03 NFR-07 explicitly
    # defers latency/throughput commitments until a baseline exists. These
    # budgets are therefore QA-PROPOSED gates, not contractual SLOs; tune via the
    # QA_PERF_* env vars and replace with real figures once an NFR is published.
    # 500 requests keeps p99 meaningful (not just the 2nd-largest sample).
    perf_requests: int = int(_env("QA_PERF_REQUESTS", "500"))
    perf_concurrency: int = int(_env("QA_PERF_CONCURRENCY", "20"))
    perf_health_p95_ms: float = float(_env("QA_PERF_HEALTH_P95_MS", "150"))
    perf_api_p95_ms: float = float(_env("QA_PERF_API_P95_MS", "800"))
    perf_max_error_rate: float = float(_env("QA_PERF_MAX_ERROR_RATE", "0.01"))

    @property
    def is_prod(self) -> bool:
        return self.target_env == "prod"

    @property
    def oidc_base(self) -> str:
        return f"{self.keycloak_url}/realms/{self.realm}/protocol/openid-connect"


CONFIG = Config()
