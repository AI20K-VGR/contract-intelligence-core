"""DTOs — input/output cho application layer.

DTO dùng Pydantic. Đây là ranh giới giữa "trong" (domain entity dataclass) và
"ngoài" (HTTP request/response JSON).
"""

from contract_intelligence.contract.application.dtos.batch_dtos import (
    BatchCreatedDTO,
    BatchDetailDTO,
    BatchListItemDTO,
)
from contract_intelligence.contract.application.dtos.contract_status_response import (
    ContractStatusResponse,
)
from contract_intelligence.contract.application.dtos.contract_upload_request import (
    ContractUploadRequest,
)
from contract_intelligence.contract.application.dtos.document_dtos import (
    DocumentDetailDTO,
    DocumentListItemDTO,
)
from contract_intelligence.contract.application.dtos.dossier_dtos import (
    DocumentSummaryDTO,
    DossierCreatedDTO,
    DossierDetailDTO,
    DossierSummaryDTO,
)
from contract_intelligence.contract.application.dtos.optimization_dtos import (
    CreateCampaignRequestDTO,
    CreateCandidateRequestDTO,
    CreateExperimentRequestDTO,
    ExperimentResultDTO,
    OptimizationCampaignDTO,
    OptimizationCandidateDTO,
    OptimizationExperimentDTO,
)

__all__ = [
    "BatchCreatedDTO",
    "BatchDetailDTO",
    "BatchListItemDTO",
    "ContractUploadRequest",
    "ContractStatusResponse",
    "CreateCampaignRequestDTO",
    "CreateCandidateRequestDTO",
    "CreateExperimentRequestDTO",
    "DocumentDetailDTO",
    "DocumentListItemDTO",
    "DocumentSummaryDTO",
    "DossierCreatedDTO",
    "DossierDetailDTO",
    "DossierSummaryDTO",
    "ExperimentResultDTO",
    "OptimizationCampaignDTO",
    "OptimizationCandidateDTO",
    "OptimizationExperimentDTO",
]
