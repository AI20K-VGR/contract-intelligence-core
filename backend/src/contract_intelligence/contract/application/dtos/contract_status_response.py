"""Output DTO cho GET /dossiers/{id}."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from contract_intelligence.contract.domain.entities.dossier import Dossier
from contract_intelligence.contract.domain.entities.job import Job
from contract_intelligence.contract.domain.entities.job import JobStatus


class ContractStatusResponse(BaseModel):
    """Status snapshot cho 1 dossier."""

    model_config = ConfigDict(extra="forbid")

    dossier_id: str
    name: str
    batch_id: str | None
    has_conflicts: bool
    latest_job_id: str | None
    latest_job_status: JobStatus | None
    document_count: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, *, dossier: Dossier, latest_job: Job | None) -> "ContractStatusResponse":
        return cls(
            dossier_id=dossier.id,
            name=dossier.name,
            batch_id=dossier.batch_id,
            has_conflicts=dossier.has_conflicts,
            latest_job_id=latest_job.id if latest_job else None,
            latest_job_status=latest_job.status if latest_job else None,
            document_count=len(dossier.documents),
            created_at=dossier.created_at,
            updated_at=dossier.updated_at,
        )
