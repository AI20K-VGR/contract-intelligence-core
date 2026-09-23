"""User Management APIs — B2B SaaS admin CRUD via Keycloak Admin API.

RBAC: ADMINISTRATOR only.
Guards: no self-modification; protect the last ADMINISTRATOR.
"""

from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.responses import JSONResponse

from contract_intelligence.identity.interfaces.api.dependencies import UserRepositoryDep
from contract_intelligence.infrastructure import keycloak_admin as kc
from contract_intelligence.schemas.users import (
    UserCreateRequest,
    UserDTO,
    UserPatchRequest,
    UserRole,
    UserStatus,
)
from contract_intelligence.shared.auth import AuthenticatedUser, require_role
from contract_intelligence.shared.responses import ApiMeta, ApiResponse, ErrorPayload, ErrorResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/users", tags=["Users"])

AdminUser = Annotated[AuthenticatedUser, Depends(require_role("ADMINISTRATOR"))]


def _error_response(exc: kc.UserAdminError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=ErrorPayload(code=exc.code, message=exc.message, details=exc.details),
        ).model_dump(mode="json"),
    )


def _forbid_self(actor: AuthenticatedUser, target_user_id: str, action: str) -> None:
    if actor.user_id == target_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cannot {action} your own account",
        )


async def _sync_app_user(
    repo: UserRepositoryDep,
    dto: UserDTO,
    *,
    tenant_id: str,
    is_active: bool | None = None,
) -> None:
    """Best-effort local ``app_user`` cache sync after Keycloak mutations."""
    active = is_active if is_active is not None else dto.status != "disabled"
    user = await repo.upsert_from_keycloak(
        keycloak_sub=dto.id,
        tenant_id=tenant_id,
        email=dto.email,
        display_name=dto.display_name,
        role=dto.role,
    )
    if user.is_active != active:
        if active:
            user.activate()
        else:
            user.deactivate()
        await repo.save(user)


@router.get(
    "",
    response_model=ApiResponse[list[UserDTO]],
    summary="List / search users",
)
async def list_users(
    _admin: AdminUser,
    q: Annotated[str | None, Query(description="Search email / display name")] = None,
    role: Annotated[UserRole | None, Query()] = None,
    status_filter: Annotated[
        UserStatus | None,
        Query(alias="status", description="invited | active | disabled"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ApiResponse[list[UserDTO]] | JSONResponse:
    """RBAC: ADMINISTRATOR. Supports ``q``, ``role``, ``status``, ``limit``, ``offset``."""
    try:
        result = await kc.list_users(
            q=q,
            role=role,
            status=status_filter,
            limit=limit,
            offset=offset,
            tenant_id=_admin.tenant_id or None,
        )
    except kc.UserAdminError as exc:
        return _error_response(exc)

    return ApiResponse(
        data=result.items,
        meta=ApiMeta(
            page=(offset // limit) + 1,
            page_size=limit,
            total=result.total,
        ),
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[UserDTO],
    summary="Create user and send password-set invite",
)
async def create_user(
    body: UserCreateRequest,
    admin: AdminUser,
    repo: UserRepositoryDep,
) -> ApiResponse[UserDTO] | JSONResponse:
    """Create Keycloak user, assign role, send UPDATE_PASSWORD email, sync ``app_user``."""
    if body.role == "ADMINISTRATOR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrators are created in Keycloak",
        )
    try:
        dto = await kc.create_user(
            email=str(body.email),
            display_name=body.display_name,
            role=body.role,
            tenant_id=admin.tenant_id,
        )
    except kc.UserAdminError as exc:
        return _error_response(exc)

    try:
        await _sync_app_user(repo, dto, tenant_id=admin.tenant_id, is_active=True)
    except Exception as exc:  # noqa: BLE001 — Keycloak succeeded; log local sync failure
        logger.exception("users.create.app_user_sync_failed", user_id=dto.id, error=str(exc))

    return ApiResponse(data=dto)


@router.patch(
    "/{id}",
    response_model=ApiResponse[UserDTO],
    summary="Update user role",
)
async def patch_user(
    body: UserPatchRequest,
    admin: AdminUser,
    repo: UserRepositoryDep,
    id: Annotated[str, Path(min_length=1, description="Keycloak user id")],  # noqa: A002
) -> ApiResponse[UserDTO] | JSONResponse:
    """RBAC: ADMINISTRATOR. Blocks self-role-change and demoting the last admin."""
    if body.role == "ADMINISTRATOR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrators are created in Keycloak",
        )
    _forbid_self(admin, id, "change the role of")
    try:
        dto = await kc.update_user_role(user_id=id, role=body.role)
    except kc.UserAdminError as exc:
        return _error_response(exc)

    try:
        await _sync_app_user(repo, dto, tenant_id=admin.tenant_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("users.patch.app_user_sync_failed", user_id=dto.id, error=str(exc))

    return ApiResponse(data=dto)


@router.post(
    "/{id}/disable",
    response_model=ApiResponse[UserDTO],
    summary="Disable user in Keycloak",
)
async def disable_user(
    admin: AdminUser,
    repo: UserRepositoryDep,
    id: Annotated[str, Path(min_length=1)],  # noqa: A002
) -> ApiResponse[UserDTO] | JSONResponse:
    """RBAC: ADMINISTRATOR. Blocks self-disable and disabling the last admin."""
    _forbid_self(admin, id, "disable")
    try:
        dto = await kc.disable_user(user_id=id)
    except kc.UserAdminError as exc:
        return _error_response(exc)

    try:
        await _sync_app_user(repo, dto, tenant_id=admin.tenant_id, is_active=False)
    except Exception as exc:  # noqa: BLE001
        logger.exception("users.disable.app_user_sync_failed", user_id=dto.id, error=str(exc))

    return ApiResponse(data=dto)


@router.post(
    "/{id}/enable",
    response_model=ApiResponse[UserDTO],
    summary="Enable user in Keycloak",
)
async def enable_user(
    admin: AdminUser,
    repo: UserRepositoryDep,
    id: Annotated[str, Path(min_length=1)],  # noqa: A002
) -> ApiResponse[UserDTO] | JSONResponse:
    """RBAC: ADMINISTRATOR."""
    _forbid_self(admin, id, "enable")
    try:
        dto = await kc.enable_user(user_id=id)
    except kc.UserAdminError as exc:
        return _error_response(exc)

    try:
        await _sync_app_user(repo, dto, tenant_id=admin.tenant_id, is_active=True)
    except Exception as exc:  # noqa: BLE001
        logger.exception("users.enable.app_user_sync_failed", user_id=dto.id, error=str(exc))

    return ApiResponse(data=dto)


@router.post(
    "/{id}/invite",
    response_model=ApiResponse[UserDTO],
    summary="Resend UPDATE_PASSWORD invite email",
)
async def resend_invite(
    admin: AdminUser,
    id: Annotated[str, Path(min_length=1)],  # noqa: A002
) -> ApiResponse[UserDTO] | JSONResponse:
    """RBAC: ADMINISTRATOR. Only allowed when user status is ``invited``."""
    _ = admin  # authz already enforced by AdminUser dependency
    try:
        dto = await kc.resend_invite(user_id=id)
    except kc.UserAdminError as exc:
        return _error_response(exc)

    return ApiResponse(data=dto)
