"""DTOs for dossier deletion (2-step tombstone + purge)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DossierDeletedDTO(BaseModel):
    """Response body for DELETE /dossiers/{id} (202 Accepted)."""

    model_config = ConfigDict(extra="forbid")

    dossier_id: str
    deleted_at: datetime
    purge_status: str
