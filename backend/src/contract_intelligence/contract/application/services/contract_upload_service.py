"""Use case: upload hợp đồng + phụ lục, tạo Dossier + Job mới.

Flow:
1. Validate input (size, mime).
2. Upload file PDF lên MinIO.
3. Sinh Document entities (role contract + annex).
4. Persist Dossier + Documents + Job.
5. Enqueue task xử lý (qua TaskQueue Protocol).
"""

from __future__ import annotations

from dataclasses import dataclass

from contract_intelligence.contract.application.dtos.contract_upload_request import (
    ContractUploadRequest,
)
from contract_intelligence.contract.domain.entities.document import Document, DocumentRole
from contract_intelligence.contract.domain.entities.dossier import Dossier
from contract_intelligence.contract.domain.entities.job import Job, JobStatus
from contract_intelligence.contract.domain.repositories.document_repository import (
    DocumentRepository,
)
from contract_intelligence.contract.domain.repositories.dossier_repository import (
    DossierRepository,
)
from contract_intelligence.contract.domain.repositories.job_repository import JobRepository
from contract_intelligence.shared.exceptions import ValidationError


@dataclass
class _BlobStoragePort:
    """Anti-corruption layer cho MinIO — định nghĩa Protocol, impl ở infrastructure.

    Application không import MinIO. Triển khai cụ thể ở
    ``infrastructure/storage/minio_adapter.py`` implement Protocol này.
    """


class ContractUploadService:
    """Use case — POST /dossiers (multipart)."""

    def __init__(
        self,
        *,
        dossier_repo: DossierRepository,
        document_repo: DocumentRepository,
        job_repo: JobRepository,
        blob_storage: object,  # Protocol: BlobStoragePort
        task_queue: object,  # Protocol: TaskQueuePort
    ) -> None:
        self._dossier_repo = dossier_repo
        self._document_repo = document_repo
        self._job_repo = job_repo
        self._blob_storage = blob_storage  # noqa: ANN001 — Protocol injection
        self._task_queue = task_queue  # noqa: ANN001 — Protocol injection

    async def execute(self, request: ContractUploadRequest) -> str:
        """Trả về dossier_id."""
        self._validate(request)

        # 1. Tạo Dossier
        dossier = Dossier(name=request.name, batch_id=request.batch_id)
        await self._dossier_repo.add(dossier)

        # 2. Upload từng file + tạo Document
        await self._ingest_one(
            dossier_id=dossier.id,
            file=request.contract_file,
            role=DocumentRole.CONTRACT,
            order_index=0,
        )
        for idx, annex_file in enumerate(request.annex_files, start=1):
            await self._ingest_one(
                dossier_id=dossier.id,
                file=annex_file,
                role=DocumentRole.ANNEX,
                order_index=idx,
            )

        # 3. Tạo Job bắt đầu ở UPLOADED
        job = Job(dossier_id=dossier.id, batch_id=dossier.batch_id, status=JobStatus.UPLOADED)
        await self._job_repo.add(job)

        # 4. Enqueue task xử lý (qua port — impl ở infrastructure)
        await self._task_queue.enqueue(  # type: ignore[attr-defined]
            kind="dossier.process",
            payload={"dossier_id": dossier.id, "job_id": job.id},
            priority=100,
        )

        return dossier.id

    # -------------------------------------------------------------------------
    # Internal
    # -------------------------------------------------------------------------
    def _validate(self, req: ContractUploadRequest) -> None:
        if not req.name.strip():
            raise ValidationError("Dossier name không được rỗng", field="name")
        if req.contract_file is None:
            raise ValidationError("Phải có ít nhất 1 file hợp đồng", field="contract_file")

    async def _ingest_one(
        self,
        *,
        dossier_id: str,
        file: object,
        role: DocumentRole,
        order_index: int,
    ) -> Document:
        # Stub — implementation đầy đủ sẽ upload MinIO, tính sha256, tạo Document
        # và persist. Giữ chỗ này cho Sprint 2.
        raise NotImplementedError("Sprint 2 — wiring MinIO upload + sha256")
