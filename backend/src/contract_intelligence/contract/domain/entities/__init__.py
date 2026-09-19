"""Domain entities cho bounded context contract.

Mỗi entity là ``@dataclass`` plain Python — không phụ thuộc SQLAlchemy.
ORM mapping được thực hiện trong ``infrastructure/persistence/``.
"""

from contract_intelligence.contract.domain.entities.document import Document, DocumentRole
from contract_intelligence.contract.domain.entities.dossier import Dossier
from contract_intelligence.contract.domain.entities.job import Job, JobStatus
from contract_intelligence.contract.domain.entities.manifest import Manifest, ManifestItem

__all__ = [
    "Dossier",
    "Document",
    "DocumentRole",
    "Job",
    "JobStatus",
    "Manifest",
    "ManifestItem",
]
