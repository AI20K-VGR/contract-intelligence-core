"""FastAPI routers cho conflict."""

from contract_intelligence.conflict.interfaces.api.routers.conflict_full_router import (
    router as conflict_router,
)

__all__ = ["conflict_router"]
