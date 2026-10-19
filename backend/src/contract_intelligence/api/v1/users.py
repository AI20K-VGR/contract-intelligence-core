"""User Management APIs — B2B SaaS admin CRUD via Keycloak Admin API.

RBAC: ADMINISTRATOR only, except ``GET /users/directory`` and ``GET /users/lookup``
(OPERATOR too), which find who a dossier can be shared with.
Guards: no self-modification; protect the last ADMINISTRATOR.
"""

from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.admin.activity_feed import record_activity
from contract_intelligence.identity.interfaces.api.dependencies import UserRepositoryDep
from contract_intelligence.infrastructure import keycloak_admin as kc
from contract_intelligence.schemas.users import (
    UserCreateRequest,
    UserDirectoryEntryDTO,
    UserDTO,
    UserPatchRequest,
    UserRole,
    UserStatus,
)
from contract_intelligence.shared.auth import AuthenticatedUser, require_role
from contract_intelligence.shared.persistence import get_async_session
from contract_intelligence.shared.responses import ApiMeta, ApiResponse, ErrorPayload, ErrorResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/users", tags=["Users"])

AdminUser = Annotated[AuthenticatedUser, Depends(require_role("ADMINISTRATOR"))]
# Whoever may share a dossier (shared/acl.py DOSSIER_MANAGE): OPERATOR, ADMINISTRATOR.
SharingUser = Annotated[AuthenticatedUser, Depends(require_role("OPERATOR", "ADMINISTRATOR"))]

# An OPERATOR must search the directory; an empty or 1-2 character query would list
# (almost) the whole tenant. ADMINISTRATOR already sees everyone through GET /users.
DIRECTORY_MIN_QUERY = 3

_ROLE_VI = {
    "OPERATOR": "Vận hành",
    "REVIEWER": "Thẩm định",
    "ADMINISTRATOR": "Quản trị",
}


async def _record(
    session: AsyncSession,
    *,
    tenant_id: str,
    title: str,
    actor_display_name: str,
    detail: str | None,
    kind: str,
) -> None:
    """Best-effort overview event. A feed failure must not undo the admin action."""
    try:
        await record_activity(
            session,
            tenant_id=tenant_id,
            title=title,
            actor_display_name=actor_display_name,
            detail=detail,
            kind=kind,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("activity.record_failed", kind=kind, error=str(exc))


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


@router.get(
    "/directory",
    response_model=ApiResponse[list[UserDirectoryEntryDTO]],
    summary="Tenant members a dossier can be shared with",
)
async def list_directory(
    user: SharingUser,
    q: Annotated[str | None, Query(description="Search email / display name")] = None,
    role: Annotated[UserRole | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ApiResponse[list[UserDirectoryEntryDTO]] | JSONResponse:
    """RBAC: OPERATOR, ADMINISTRATOR. Active members of the caller's tenant only.

    Returns ``id``, ``email``, ``display_name`` and ``role``; nothing an
    administrator manages (status, invite, last login). Unlike ``GET /users``,
    a user without a ``tenant_id`` attribute in Keycloak is not listed. An
    OPERATOR must send ``q`` with at least ``DIRECTORY_MIN_QUERY`` characters
    (422 ``directory_query_required``), so the API does not list the whole tenant.
    """
    if user.role != "ADMINISTRATOR" and len((q or "").strip()) < DIRECTORY_MIN_QUERY:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(
                error=ErrorPayload(
                    code="directory_query_required",
                    message=f"Nhập ít nhất {DIRECTORY_MIN_QUERY} ký tự để tìm người dùng.",
                    details={"min_length": DIRECTORY_MIN_QUERY},
                )
            ).model_dump(mode="json"),
        )
    try:
        result = await kc.list_users(
            q=q,
            role=role,
            status="active",
            limit=limit,
            offset=offset,
            tenant_id=user.tenant_id or None,
            with_last_login=False,
            strict_tenant=True,
        )
    except kc.UserAdminError as exc:
        return _error_response(exc)

    return ApiResponse(
        data=[
            UserDirectoryEntryDTO(
                id=item.id, email=item.email, display_name=item.display_name, role=item.role
            )
            for item in result.items
        ],
        meta=ApiMeta(
            page=(offset // limit) + 1,
            page_size=limit,
            total=result.total,
        ),
    )


@router.get(
    "/lookup",
    response_model=ApiResponse[UserDirectoryEntryDTO],
    responses={404: {"model": ErrorResponse, "description": "user_not_found"}},
    summary="Find the one tenant member with this exact email (for sharing)",
)
async def lookup_user(
    user: SharingUser,
    email: Annotated[str, Query(min_length=3, max_length=320, description="Exact email")],
) -> ApiResponse[UserDirectoryEntryDTO] | JSONResponse:
    """RBAC: OPERATOR, ADMINISTRATOR. Exact, case-insensitive email match.

    Returns ``{id, email, display_name, role}`` when exactly one active user of the
    caller's tenant has this email; otherwise 404 ``user_not_found`` (another tenant,
    disabled, not yet activated, or no such user all look the same).
    """
    try:
        member = await kc.lookup_tenant_member(tenant_id=user.tenant_id, email=email)
    except kc.UserAdminError as exc:
        return _error_response(exc)
    if member is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ErrorResponse(
                error=ErrorPayload(
                    code="user_not_found",
                    message="Không tìm thấy người dùng với email này trong đơn vị của bạn.",
                )
            ).model_dump(mode="json"),
        )
    return ApiResponse(
        data=UserDirectoryEntryDTO(
            id=member.id,
            email=member.email,
            display_name=member.display_name,
            role=member.role or "OPERATOR",
        )
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
    session: Annotated[AsyncSession, Depends(get_async_session)],
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

    await _record(
        session,
        tenant_id=admin.tenant_id,
        title=f"Mời thành viên {dto.display_name}",
        actor_display_name=admin.email or admin.display_name,
        detail=dto.email,
        kind="user.invited",
    )
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
    session: Annotated[AsyncSession, Depends(get_async_session)],
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

    await _record(
        session,
        tenant_id=admin.tenant_id,
        title=f"Đổi vai trò của {dto.display_name} thành {_ROLE_VI.get(dto.role, dto.role)}",
        actor_display_name=admin.email or admin.display_name,
        detail=dto.email,
        kind="user.role_changed",
    )
    return ApiResponse(data=dto)


@router.post(
    "/{id}/disable",
    response_model=ApiResponse[UserDTO],
    summary="Disable user in Keycloak",
)
async def disable_user(
    admin: AdminUser,
    repo: UserRepositoryDep,
    session: Annotated[AsyncSession, Depends(get_async_session)],
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

    await _record(
        session,
        tenant_id=admin.tenant_id,
        title=f"Khóa tài khoản {dto.display_name}",
        actor_display_name=admin.email or admin.display_name,
        detail=dto.email,
        kind="user.disabled",
    )
    return ApiResponse(data=dto)


@router.post(
    "/{id}/enable",
    response_model=ApiResponse[UserDTO],
    summary="Enable user in Keycloak",
)
async def enable_user(
    admin: AdminUser,
    repo: UserRepositoryDep,
    session: Annotated[AsyncSession, Depends(get_async_session)],
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

    await _record(
        session,
        tenant_id=admin.tenant_id,
        title=f"Mở khóa tài khoản {dto.display_name}",
        actor_display_name=admin.email or admin.display_name,
        detail=dto.email,
        kind="user.enabled",
    )
    return ApiResponse(data=dto)


@router.post(
    "/{id}/invite",
    response_model=ApiResponse[UserDTO],
    summary="Resend UPDATE_PASSWORD invite email",
)
async def resend_invite(
    admin: AdminUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    id: Annotated[str, Path(min_length=1)],  # noqa: A002
) -> ApiResponse[UserDTO] | JSONResponse:
    """RBAC: ADMINISTRATOR. Only allowed when user status is ``invited``."""
    try:
        dto = await kc.resend_invite(user_id=id)
    except kc.UserAdminError as exc:
        return _error_response(exc)

    await _record(
        session,
        tenant_id=admin.tenant_id,
        title=f"Gửi lại lời mời cho {dto.display_name}",
        actor_display_name=admin.email or admin.display_name,
        detail=dto.email,
        kind="user.invite_resent",
    )
    return ApiResponse(data=dto)
