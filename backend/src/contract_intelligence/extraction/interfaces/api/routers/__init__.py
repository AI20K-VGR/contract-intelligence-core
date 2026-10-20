"""FastAPI routers cho extraction."""

from contract_intelligence.extraction.interfaces.api.routers.extraction_full_router import (
    router as extraction_router,
)

__all__ = ["extraction_router"]
