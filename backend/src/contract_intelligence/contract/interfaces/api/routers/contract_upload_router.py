"""POST /dossiers — upload hợp đồng + phụ lục."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile, status

from contract_intelligence.contract.application.dtos.contract_upload_request import (
    ContractUploadRequest,
)
from contract_intelligence.shared.responses import ApiResponse

router = APIRouter()


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=ApiResponse[str])
async def upload_dossier(
    name: str = Form(..., min_length=1, max_length=255),
    batch_id: str | None = Form(None),
    contract_file: UploadFile = File(...),
    annex_files: list[UploadFile] = File(default_factory=list),
    # service: ContractUploadService = Depends(get_contract_upload_service),  # Sprint 2
) -> ApiResponse[str]:
    """Upload multipart — 1 contract + 0..n annex.

    Sprint 2 sẽ wire dependency injection. Hiện tại chỉ trả 202 stub.
    """
    _ = ContractUploadRequest(
        name=name,
        batch_id=batch_id,
        contract_file=contract_file,
        annex_files=annex_files,
    )
    # dossier_id = await service.execute(req)
    return ApiResponse(data="dos_placeholder")
