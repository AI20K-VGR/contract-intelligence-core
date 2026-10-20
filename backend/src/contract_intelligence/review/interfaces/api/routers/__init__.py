"""FastAPI routers cho review."""

from contract_intelligence.review.interfaces.api.routers.review_full_router import (
    router as review_router,
)

__all__ = ["review_router"]
