"""Approval application service — lock/approve dossier + external approval tokens.

Layer: application — orchestrates dossier repo + external approval ORM.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.contract.infrastructure.persistence.repository_impl import (
    DocumentRepositoryImpl,
    DossierRepositoryImpl,
)
from contract_intelligence.review.infrastructure.persistence.orm_approval import (
    DossierApprovalORM,
    ExternalApprovalORM,
)
from contract_intelligence.shared.base import new_ulid, utcnow
from contract_intelligence.shared.exceptions import NotFoundError


class ApprovalService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        tenant_id: str,
        dossier_repo: DossierRepositoryImpl,
        document_repo: DocumentRepositoryImpl,
    ) -> None:
        self._session = session
        self._tenant_id = tenant_id
        self._dossier_repo = dossier_repo
        self._document_repo = document_repo

    async def lock_dossier(self, dossier_id: str) -> dict[str, Any]:
        dossier = await self._dossier_repo.get(dossier_id)
        if dossier is None:
            raise NotFoundError(entity_type="Dossier", entity_id=dossier_id)
        await self._dossier_repo.lock(dossier_id, locked=True)
        return {"id": dossier_id, "is_locked": True}

    async def approve_dossier(
        self, dossier_id: str, user_id: str
    ) -> dict[str, Any]:
        dossier = await self._dossier_repo.get(dossier_id)
        if dossier is None:
            raise NotFoundError(entity_type="Dossier", entity_id=dossier_id)

        # Compute checksum từ documents (SHA-256 concatenated)
        documents = await self._document_repo.list_by_dossier(dossier_id)
        h = hashlib.sha256()
        for doc in sorted(documents, key=lambda d: d.id):
            h.update(doc.id.encode())
            h.update(doc.sha256.encode())
        checksum = h.hexdigest()

        approval = DossierApprovalORM(
            id=new_ulid("dapr_"),
            tenant_id=self._tenant_id,
            dossier_id=dossier_id,
            approved_by=user_id,
            checksum=checksum,
        )
        self._session.add(approval)
        await self._session.flush()

        await self._dossier_repo.approve(dossier_id, checksum)
        return {
            "id": approval.id,
            "dossier_id": dossier_id,
            "checksum": checksum,
            "approved_at": approval.approved_at.isoformat(),
        }

    async def create_external_approval(
        self,
        *,
        dossier_id: str,
        recipient_email: str,
        recipient_name: str | None,
        created_by: str,
        expires_in_days: int = 7,
    ) -> dict[str, Any]:
        dossier = await self._dossier_repo.get(dossier_id)
        if dossier is None:
            raise NotFoundError(entity_type="Dossier", entity_id=dossier_id)

        token = secrets.token_urlsafe(32)
        ext = ExternalApprovalORM(
            id=new_ulid("ext_"),
            tenant_id=self._tenant_id,
            dossier_id=dossier_id,
            token=token,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            status="pending",
            expires_at=utcnow() + timedelta(days=expires_in_days),
            created_by=created_by,
        )
        self._session.add(ext)
        await self._session.flush()
        return {
            "id": ext.id,
            "token": token,
            "dossier_id": dossier_id,
            "recipient_email": recipient_email,
            "status": ext.status,
            "expires_at": ext.expires_at.isoformat(),
            "approval_url": f"/external-approvals/{token}",
        }

    async def list_external_approvals(self, dossier_id: str) -> list[dict[str, Any]]:
        stmt = (
            select(ExternalApprovalORM)
            .where(
                ExternalApprovalORM.dossier_id == dossier_id,
                ExternalApprovalORM.tenant_id == self._tenant_id,
            )
            .order_by(ExternalApprovalORM.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [
            {
                "id": e.id,
                "recipient_email": e.recipient_email,
                "recipient_name": e.recipient_name,
                "status": e.status,
                "expires_at": e.expires_at.isoformat(),
                "responded_at": e.responded_at.isoformat() if e.responded_at else None,
            }
            for e in result.scalars().all()
        ]

    async def handle_external_callback(
        self,
        *,
        token: str,
        status: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Webhook từ DocuSign/SAP/ERP — cập nhật trạng thái token."""
        stmt = select(ExternalApprovalORM).where(
            ExternalApprovalORM.token == token,
            ExternalApprovalORM.tenant_id == self._tenant_id,
        )
        result = await self._session.execute(stmt)
        ext = result.scalar_one_or_none()
        if ext is None:
            raise NotFoundError(entity_type="ExternalApproval", entity_id=token)
        if status not in ("approved", "rejected"):
            raise ValueError(f"Invalid status {status!r}")
        ext.status = status
        ext.responded_at = utcnow()
        ext.response_payload = json.dumps(payload or {})
        await self._session.flush()
        return {"token": token, "status": ext.status}


__all__ = ["ApprovalService"]
