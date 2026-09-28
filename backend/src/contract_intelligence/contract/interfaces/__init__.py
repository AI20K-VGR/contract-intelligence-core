"""Contract bounded context — interfaces (HTTP layer)."""

from contract_intelligence.contract.interfaces.api.dependencies import (
    ContractServiceDep,
    get_contract_service,
)
from contract_intelligence.contract.interfaces.api.routers.contract_router import (
    router as contract_router,
)

__all__ = [
    "ContractServiceDep",
    "contract_router",
    "get_contract_service",
]
