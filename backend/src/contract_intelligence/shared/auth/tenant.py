"""Tenant extraction & verification — đọc X-Tenant-Id header + match với JWT claim.

Tuân thủ DOC-05b §2.2: mọi request phải có X-Tenant-Id khớp claim.tenant_id.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from contract_intelligence.shared.auth.dependencies import get_current_user
from contract_intelligence.shared.auth.exceptions import TenantMismatchError
from contract_intelligence.shared.auth.schemas import AuthenticatedUser


async def get_tenant_id(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    x_tenant_id: Annotated[str | None, Header()] = None,
) -> str:
    """Trích tenant_id từ header và verify khớp với JWT claim.

    Returns:
        Tenant ID đã verify — dùng cho mọi query DB.

    Raises:
        HTTPException 400: X-Tenant-Id header missing.
        HTTPException 403: X-Tenant-Id ≠ claim.tenant_id (cross-tenant access attempt).
    """
    if not x_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-Id header is required",
        )
    if x_tenant_id != user.tenant_id:
        raise TenantMismatchError(
            header_tenant=x_tenant_id,
            token_tenant=user.tenant_id,
        )
    return x_tenant_id


__all__ = ["get_tenant_id"]
