"""Approval application service — lock/approve dossier + external approval grants.

Layer: application — orchestrates dossier repo + external approval ORM.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.contract.application.dtos.dossier_dtos import DossierDetailDTO
from contract_intelligence.contract.infrastructure.persistence.repository_impl import (
    DocumentRepositoryImpl,
    DossierRepositoryImpl,
)
from contract_intelligence.review.application.dtos.approval_dtos import (
    ExternalApprovalGrantDTO,
)
from contract_intelligence.review.infrastructure.persistence.orm import ReviewItemORM
from contract_intelligence.review.infrastructure.persistence.orm_approval import (
    DossierApprovalORM,
    ExternalApprovalORM,
)
from contract_intelligence.shared.base import new_ulid, utcnow
from contract_intelligence.shared.exceptions import (
    InvalidStateTransition,
    NotFoundError,
    ValidationError,
)


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

    async def lock_dossier(self, dossier_id: str) -> DossierDetailDTO:
        flags = await self._dossier_repo.get_flags(dossier_id)
        if flags is None:
            raise NotFoundError(entity_type="Dossier", entity_id=dossier_id)
        if flags.get("is_locked"):
            raise InvalidStateTransition(
                from_state="locked",
                to_state="locked",
                entity="Dossier",
            )
        await self._dossier_repo.lock(dossier_id, locked=True)
        return await self._dossier_detail(dossier_id)

    async def approve_dossier(
        self,
        dossier_id: str,
        user_id: str,
        *,
        comment: str | None = None,
    ) -> DossierDetailDTO:
        flags = await self._dossier_repo.get_flags(dossier_id)
        if flags is None:
            raise NotFoundError(entity_type="Dossier", entity_id=dossier_id)
        if flags.get("is_approved"):
            raise InvalidStateTransition(
                from_state="approved",
                to_state="approved",
                entity="Dossier",
            )
        status = str(flags.get("status") or "")
        if status != "reviewed":
            raise InvalidStateTransition(
                from_state=status or "unknown",
                to_state="approved",
                entity="Dossier",
            )

        open_count = await self._count_open_review_items(dossier_id)
        if open_count > 0:
            raise InvalidStateTransition(
                from_state=f"open_review_items={open_count}",
                to_state="approved",
                entity="Dossier",
            )

        documents = await self._document_repo.list_by_dossier(dossier_id)
        h = hashlib.sha256()
        for doc in sorted(documents, key=lambda d: d.id):
            h.update(doc.id.encode())
            h.update(doc.sha256.encode())
        checksum = h.hexdigest()

        approval = DossierApprovalORM(
            id=new_ulid("apr_"),
            tenant_id=self._tenant_id,
            dossier_id=dossier_id,
            approved_by=user_id,
            checksum=checksum,
            comment=comment,
        )
        self._session.add(approval)
        await self._session.flush()

        await self._dossier_repo.approve(dossier_id, checksum)
        return await self._dossier_detail(dossier_id)

    async def create_external_approval(
        self,
        *,
        dossier_id: str,
        provider: str,
        approver_email: str,
        approver_name: str | None,
        created_by: str,
        expires_in_hours: int = 72,
        notes: str | None = None,
    ) -> ExternalApprovalGrantDTO:
        flags = await self._dossier_repo.get_flags(dossier_id)
        if flags is None:
            raise NotFoundError(entity_type="Dossier", entity_id=dossier_id)
        if not flags.get("is_approved"):
            raise InvalidStateTransition(
                from_state=str(flags.get("status") or "unapproved"),
                to_state="external_approval",
                entity="Dossier",
            )

        pending = await self._session.execute(
            select(func.count())
            .select_from(ExternalApprovalORM)
            .where(
                ExternalApprovalORM.dossier_id == dossier_id,
                ExternalApprovalORM.tenant_id == self._tenant_id,
                ExternalApprovalORM.status == "pending",
            )
        )
        if int(pending.scalar() or 0) > 0:
            raise InvalidStateTransition(
                from_state="pending_grant",
                to_state="pending",
                entity="ExternalApproval",
            )

        token = secrets.token_urlsafe(32)
        ext = ExternalApprovalORM(
            id=new_ulid("eag_"),
            tenant_id=self._tenant_id,
            dossier_id=dossier_id,
            token=token,
            provider=provider,
            recipient_email=approver_email,
            recipient_name=approver_name,
            status="pending",
            expires_at=utcnow() + timedelta(hours=expires_in_hours),
            created_by=created_by,
            response_payload=json.dumps({"notes": notes}) if notes else None,
        )
        self._session.add(ext)
        await self._session.flush()
        return ExternalApprovalGrantDTO.from_row(self._ext_to_row(ext))

    async def list_external_approvals(self, dossier_id: str) -> list[ExternalApprovalGrantDTO]:
        flags = await self._dossier_repo.get_flags(dossier_id)
        if flags is None:
            raise NotFoundError(entity_type="Dossier", entity_id=dossier_id)
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
            ExternalApprovalGrantDTO.from_row(self._ext_to_row(e)) for e in result.scalars().all()
        ]

    async def handle_external_callback(
        self,
        *,
        grant_id: str,
        status: str,
        external_reference_id: str | None = None,
        digital_signature_hash: str | None = None,
        signature_certificate: str | None = None,
        signed_at: Any | None = None,
    ) -> ExternalApprovalGrantDTO:
        """Webhook từ DocuSign/SAP/ERP — cập nhật grant theo grant_id."""
        if status not in ("approved", "rejected"):
            raise ValidationError(f"Invalid status {status!r}")

        stmt = select(ExternalApprovalORM).where(
            ExternalApprovalORM.id == grant_id,
            ExternalApprovalORM.tenant_id == self._tenant_id,
        )
        result = await self._session.execute(stmt)
        ext = result.scalar_one_or_none()
        if ext is None:
            raise NotFoundError(entity_type="ExternalApproval", entity_id=grant_id)

        ext.status = status
        ext.responded_at = signed_at or utcnow()
        if external_reference_id is not None:
            ext.external_reference_id = external_reference_id
        if digital_signature_hash is not None:
            ext.digital_signature_hash = digital_signature_hash
        if signature_certificate is not None:
            ext.signature_certificate = signature_certificate
        await self._session.flush()
        return ExternalApprovalGrantDTO.from_row(self._ext_to_row(ext))

    async def _dossier_detail(self, dossier_id: str) -> DossierDetailDTO:
        dossier = await self._dossier_repo.get(dossier_id)
        if dossier is None:
            raise NotFoundError(entity_type="Dossier", entity_id=dossier_id)
        documents = await self._document_repo.list_by_dossier(dossier_id)
        flags = await self._dossier_repo.get_flags(dossier_id) or {}
        status = str(flags.get("status") or "")
        from contract_intelligence.contract.domain.entities.job import JobStatus

        latest_status = None
        try:
            latest_status = JobStatus(status) if status else None
        except ValueError:
            latest_status = None
        return DossierDetailDTO.from_domain(
            dossier,
            documents=documents,
            latest_job_status=latest_status,
        )

    async def _count_open_review_items(self, dossier_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(ReviewItemORM)
            .where(
                ReviewItemORM.dossier_id == dossier_id,
                ReviewItemORM.tenant_id == self._tenant_id,
                ReviewItemORM.status == "open",
            )
        )
        result = await self._session.execute(stmt)
        return int(result.scalar() or 0)

    @staticmethod
    def _ext_to_row(ext: ExternalApprovalORM) -> dict[str, Any]:
        return {
            "id": ext.id,
            "dossier_id": ext.dossier_id,
            "provider": ext.provider,
            "status": ext.status,
            "approver_email": ext.recipient_email,
            "recipient_email": ext.recipient_email,
            "external_reference_id": ext.external_reference_id,
            "digital_signature_hash": ext.digital_signature_hash,
            "granted_at": ext.responded_at,
            "responded_at": ext.responded_at,
            "created_at": ext.created_at,
        }


__all__ = ["ApprovalService"]
