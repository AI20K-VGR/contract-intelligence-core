"""Contract bounded context — interfaces (HTTP layer)."""

from contract_intelligence.contract.interfaces.api.dependencies import (
    ContractServiceDep,
    get_contract_service,
)
from contract_intelligence.contract.interfaces.api.routers.contract_router import (
    router as contract_router,
)
from contract_intelligence.contract.interfaces.api.routers.contract_upload_router import (
    router as contract_upload_router,
)

__all__ = [
    "ContractServiceDep",
    "contract_router",
    "contract_upload_router",
    "get_contract_service",
]
