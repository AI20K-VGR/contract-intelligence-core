"""Repository abstract — domain định nghĩa, infrastructure impl.

Application layer chỉ phụ thuộc Protocol/ABC ở đây, không biết SQLAlchemy.
"""

from contract_intelligence.contract.domain.repositories.document_repository import (
    DocumentRepository,
)
from contract_intelligence.contract.domain.repositories.dossier_repository import DossierRepository
from contract_intelligence.contract.domain.repositories.job_repository import JobRepository
from contract_intelligence.contract.domain.repositories.manifest_repository import (
    ManifestRepository,
)

__all__ = [
    "DossierRepository",
    "DocumentRepository",
    "JobRepository",
    "ManifestRepository",
]
