"""FastAPI entry point — lắp ráp tất cả routers từ bounded contexts.

Sprint 3 wiring:
    - 8 bounded context routers (auth, contract, extraction, conflict,
      review, approval, reocr, admin)
    - AI service client (stub | http) qua shared.ai
    - Backend headers middleware (X-Backend-Version + X-Request-Id)
    - DB engine lifecycle qua shared.persistence
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from contract_intelligence.config.logging import configure_logging, get_logger
from contract_intelligence.config.settings import get_settings
from contract_intelligence.conflict.interfaces.api.routers.conflict_full_router import (
    router as conflict_router,
)
from contract_intelligence.contract.interfaces.api.routers.admin_router import (
    router as admin_router,
)
from contract_intelligence.contract.interfaces.api.routers.contract_router import (
    router as contract_router,
)
from contract_intelligence.contract.interfaces.api.routers.contract_upload_router import (
    router as contract_upload_router,
)
from contract_intelligence.extraction.interfaces.api.routers.events_router import (
    router as events_router,
)
from contract_intelligence.extraction.interfaces.api.routers.extraction_full_router import (
    router as extraction_router,
)
from contract_intelligence.extraction.interfaces.api.routers.reocr_router import (
    router as reocr_router,
)
from contract_intelligence.identity.interfaces.api.auth_router import (
    router as auth_router,
)
from contract_intelligence.identity.interfaces.api.webhook_router import (
    router as webhook_router,
)
from contract_intelligence.review.interfaces.api.routers.approval_router import (
    router as approval_router,
)
from contract_intelligence.review.interfaces.api.routers.review_full_router import (
    router as review_router,
)
from contract_intelligence.shared.ai import (
    get_ai_service_client,
    get_background_dispatcher,
    reset_ai_service_client,
    reset_background_dispatcher,
)
from contract_intelligence.shared.ai.health_router import router as ai_health_router
from contract_intelligence.shared.auth.exceptions import (
    AuthenticationError,
    InsufficientRoleError,
    TenantMismatchError,
    UserDeactivatedError,
)
from contract_intelligence.shared.exceptions import DomainException
from contract_intelligence.shared.middleware import BackendHeadersMiddleware
from contract_intelligence.shared.persistence import (
    bind_engine,
    create_async_engine,
    reset_engine,
)
from contract_intelligence.shared.responses import ErrorPayload, ErrorResponse
from contract_intelligence.shared.versioning import full_version

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """App startup / shutdown lifecycle."""
    configure_logging()
    settings = get_settings()
    logger.info(
        "startup",
        env=settings.env,
        version=full_version(),
        ai_service_mode=settings.ai_service_mode,
    )

    # Bind database engine — dùng bởi get_async_session dependency
    engine = create_async_engine()
    bind_engine(engine)
    logger.info("db_engine_bound", url=split_url(settings.database_url))

    # Initialize AI service client (singleton) — verify connectivity
    ai_client = get_ai_service_client()
    if await ai_client.healthcheck():
        logger.info("ai_client.ready")
    else:
        logger.warning("ai_client.healthcheck_failed")

    # Initialize background dispatcher
    _dispatcher = get_background_dispatcher()
    logger.info("dispatcher.ready")

    yield

    # Shutdown
    logger.info("shutdown")
    reset_background_dispatcher()
    reset_ai_service_client()
    reset_engine()
    await engine.dispose()


def split_url(url: str) -> str:
    """Hide password trong DSN cho logging."""
    try:
        scheme, rest = url.split("://", 1)
        if "@" in rest:
            _, host = rest.split("@", 1)
            return f"{scheme}://***@{host}"
        return url
    except ValueError:
        return url


def create_app() -> FastAPI:
    """Compose FastAPI app với tất cả routers + middleware + exception handlers."""
    settings = get_settings()
    app = FastAPI(
        title="Contract Intelligence API",
        description=(
            "Backend: OCR/IDP/Citation/Conflict/HITL pipeline — DOC-05b v1.0.0 + DOC-05c v1.0.0. "
            "Tất cả endpoints trả về envelope `{ data, meta }` + header `X-Backend-Version`."
        ),
        version=full_version(),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Backend headers — X-Backend-Version + X-Request-Id
    app.add_middleware(BackendHeadersMiddleware)

    # Exception handlers
    @app.exception_handler(DomainException)
    async def domain_exception_handler(_: Request, exc: DomainException) -> JSONResponse:
        return JSONResponse(
            status_code=_domain_exc_to_http.get(type(exc).__name__, 409),
            content=ErrorResponse(
                error=ErrorPayload(
                    code=exc.code.value,
                    message=exc.message,
                    details=exc.details,
                ),
            ).model_dump(mode="json"),
        )

    @app.exception_handler(AuthenticationError)
    async def auth_exception_handler(_: Request, exc: AuthenticationError) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content=ErrorResponse(
                error=ErrorPayload(code="UNAUTHORIZED", message=str(exc)),
            ).model_dump(mode="json"),
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(UserDeactivatedError)
    async def user_deactivated_handler(_: Request, exc: UserDeactivatedError) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content=ErrorResponse(
                error=ErrorPayload(
                    code="USER_DEACTIVATED",
                    message=str(exc),
                    details={"user_id": exc.user_id},
                ),
            ).model_dump(mode="json"),
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(InsufficientRoleError)
    async def insufficient_role_handler(_: Request, exc: InsufficientRoleError) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content=ErrorResponse(
                error=ErrorPayload(
                    code="FORBIDDEN",
                    message=str(exc),
                    details={"required": exc.required},
                ),
            ).model_dump(mode="json"),
        )

    @app.exception_handler(TenantMismatchError)
    async def tenant_mismatch_handler(_: Request, exc: TenantMismatchError) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content=ErrorResponse(
                error=ErrorPayload(
                    code="TENANT_MISMATCH",
                    message=str(exc),
                    details={
                        "header_tenant": exc.header_tenant,
                        "token_tenant": exc.token_tenant,
                    },
                ),
            ).model_dump(mode="json"),
        )

    # Routers — theo DOC-05b §5 (10 màn hình frontend)
    app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])
    app.include_router(
        webhook_router, prefix="/api/v1/auth", tags=["Authentication"]
    )  # → /api/v1/auth/webhooks/keycloak
    app.include_router(contract_router, prefix="/api/v1", tags=["Contract"])
    app.include_router(contract_upload_router, prefix="/api/v1", tags=["Contract-Upload"])
    app.include_router(extraction_router, prefix="/api/v1", tags=["Extraction"])
    app.include_router(conflict_router, prefix="/api/v1", tags=["Conflict"])
    app.include_router(review_router, prefix="/api/v1", tags=["Review"])
    app.include_router(approval_router, prefix="/api/v1", tags=["Approval"])
    app.include_router(reocr_router, prefix="/api/v1", tags=["ReOCR"])
    app.include_router(admin_router, prefix="/api/v1", tags=["Admin/Ops"])

    # Real-time events (SSE) — DOC-05b §7 chiến lược realtime
    app.include_router(events_router, prefix="/api/v1", tags=["Events"])

    # AI service health + proxy — DOC-05c §4.7
    # /healthz + /readyz + /ai/jobs/{id}
    app.include_router(ai_health_router, prefix="/api/v1", tags=["AI-Service"])

    # Backend liveness (root — không qua /api/v1)
    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": full_version()}

    return app


_domain_exc_to_http: dict[str, int] = {
    "NotFoundError": 404,
    "ValidationError": 422,
    "ReviewVersionConflict": 409,
    "InvalidStateTransition": 409,
    "InvariantViolation": 409,
}


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("contract_intelligence.main:app", reload=True)
