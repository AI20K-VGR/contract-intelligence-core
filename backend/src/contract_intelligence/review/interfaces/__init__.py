"""Review bounded context — interfaces (HTTP layer)."""

from contract_intelligence.review.interfaces.api.dependencies import (
    ReviewServiceDep,
    get_review_service,
)
from contract_intelligence.review.interfaces.api.dependencies_approval import (
    ApprovalServiceDep,
    get_approval_service,
)
from contract_intelligence.review.interfaces.api.routers.approval_router import (
    router as approval_router,
)
from contract_intelligence.review.interfaces.api.routers.review_full_router import (
    router as review_full_router,
)

__all__ = [
    "ApprovalServiceDep",
    "ReviewServiceDep",
    "approval_router",
    "get_approval_service",
    "get_review_service",
    "review_full_router",
]
