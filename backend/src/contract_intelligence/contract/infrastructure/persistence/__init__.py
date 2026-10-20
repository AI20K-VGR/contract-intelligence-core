"""SQLAlchemy persistence — triển khai concrete cho các repository Protocol.

Module này import ``sqlalchemy``/``alembic`` — được phép vì infrastructure
**phụ thuộc** framework (đúng Dependency Rule).
"""

from contract_intelligence.contract.infrastructure.persistence.document_repository_impl import (
    SqlDocumentRepository,
)
from contract_intelligence.contract.infrastructure.persistence.dossier_repository_impl import (
    SqlDossierRepository,
)
from contract_intelligence.contract.infrastructure.persistence.job_repository_impl import (
    SqlJobRepository,
)

__all__ = ["SqlDossierRepository", "SqlDocumentRepository", "SqlJobRepository"]
