"""DTOs — input/output cho application layer.

DTO dùng Pydantic. Đây là ranh giới giữa "trong" (domain entity dataclass) và
"ngoài" (HTTP request/response JSON).
"""

from contract_intelligence.contract.application.dtos.contract_upload_request import (
    ContractUploadRequest,
)
from contract_intelligence.contract.application.dtos.contract_status_response import (
    ContractStatusResponse,
)

__all__ = ["ContractUploadRequest", "ContractStatusResponse"]
