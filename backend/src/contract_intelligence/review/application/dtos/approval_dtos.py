"""DTOs for Approval / External Approvals — Phase 5 OpenAPI alignment."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ExternalProvider = Literal["docusign", "sap_ariba", "corporate_sso"]


class ApproveRequestDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comment: str | None = Field(default=None, max_length=2000)


class ExternalApprovalRequestDTO(BaseModel):
    """openapi.yaml: ExternalApprovalRequest."""

    model_config = ConfigDict(extra="forbid")

    provider: ExternalProvider
    approver_email: str = Field(..., min_length=3, max_length=255)
    approver_name: str | None = None
    expires_in_hours: int = Field(default=72, ge=1, le=720)
    notes: str | None = None


class ExternalApprovalGrantDTO(BaseModel):
    """openapi.yaml: ExternalApprovalGrant."""

    model_config = ConfigDict(extra="forbid")

    id: str
    dossier_id: str
    provider: str
    status: str
    approver_email: str
    external_reference_id: str | None = None
    digital_signature_hash: str | None = None
    granted_at: datetime | None = None
    created_at: datetime | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> ExternalApprovalGrantDTO:
        created = row.get("created_at")
        granted = row.get("granted_at") or row.get("responded_at")
        if isinstance(created, str):
            try:
                created = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except ValueError:
                created = None
        if isinstance(granted, str):
            try:
                granted = datetime.fromisoformat(granted.replace("Z", "+00:00"))
            except ValueError:
                granted = None
        return cls(
            id=str(row.get("id") or ""),
            dossier_id=str(row.get("dossier_id") or ""),
            provider=str(row.get("provider") or "docusign"),
            status=str(row.get("status") or "pending"),
            approver_email=str(row.get("approver_email") or row.get("recipient_email") or ""),
            external_reference_id=row.get("external_reference_id"),
            digital_signature_hash=row.get("digital_signature_hash"),
            granted_at=granted if isinstance(granted, datetime) else None,
            created_at=created if isinstance(created, datetime) else None,
        )


class ExternalApprovalCallbackDTO(BaseModel):
    """openapi.yaml: ExternalApprovalCallbackPayload."""

    model_config = ConfigDict(extra="forbid")

    grant_id: str
    status: Literal["approved", "rejected"]
    external_reference_id: str | None = None
    digital_signature_hash: str | None = None
    signature_certificate: str | None = None
    signed_at: datetime | None = None


__all__ = [
    "ApproveRequestDTO",
    "ExternalApprovalCallbackDTO",
    "ExternalApprovalGrantDTO",
    "ExternalApprovalRequestDTO",
    "ExternalProvider",
]
