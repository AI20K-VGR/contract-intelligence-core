"""FastAPI API namespace cho contract — routers."""

from contract_intelligence.contract.interfaces.api.routers.contract_status_router import (
    router as status_router,
)
from contract_intelligence.contract.interfaces.api.routers.contract_upload_router import (
    router as upload_router,
)

__all__ = ["upload_router", "status_router"]
