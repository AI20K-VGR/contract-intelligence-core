"""FastAPI entry point — lắp ráp routers từ 4 bounded context.

Chỉ import FastAPI ở đây và trong ``interfaces/`` routers.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from contract_intelligence.config.logging import configure_logging, get_logger
from contract_intelligence.config.settings import get_settings
from contract_intelligence.conflict.interfaces.api.routers import conflict_router
from contract_intelligence.contract.interfaces.api.routers import (
    contract_status_router,
    contract_upload_router,
)
from contract_intelligence.extraction.interfaces.api.routers import extraction_router
from contract_intelligence.review.interfaces.api.routers import review_router
from contract_intelligence.shared.exceptions import DomainException
from contract_intelligence.shared.responses import ErrorPayload, ErrorResponse

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging()
    logger.info("startup", env=get_settings().env)
    yield
    logger.info("shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Contract Intelligence API",
        description="Backend: OCR/IDP/Citation/Conflict/HITL pipeline — DOC-05",
        version="0.1.0",
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

    # Exception handler — map DomainException → HTTP 409/422/404
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

    # Routers — mỗi bounded context có prefix riêng
    app.include_router(contract_upload_router, prefix="/api/v1")
    app.include_router(contract_status_router, prefix="/api/v1")
    app.include_router(extraction_router)
    app.include_router(conflict_router)
    app.include_router(review_router)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

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
