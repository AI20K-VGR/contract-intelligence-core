"""Conflict bounded context — interfaces (HTTP layer)."""

from contract_intelligence.conflict.interfaces.api.dependencies import (
    ConflictServiceDep,
    get_conflict_service,
)
from contract_intelligence.conflict.interfaces.api.routers.conflict_full_router import (
    router as conflict_full_router,
)

__all__ = [
    "ConflictServiceDep",
    "conflict_full_router",
    "get_conflict_service",
]
