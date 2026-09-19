r"""FastAPI Depends() factories cho auth — extract JWT, verify role, check tenant.

File này ĐƯỢC PHÉP import FastAPI vì nằm trong shared/auth/.
Mọi bounded context import từ đây, không tự implement auth logic.

Usage pattern:
    from contract_intelligence.shared.auth import get_current_user, require_role

    @router.get("/items")
    async def list_items(
        user: AuthenticatedUser = Depends(get_current_user()),
    ):
        ...

    @router.post("/admin-only")
    async def admin_action(
        user: AuthenticatedUser = Depends(require_role("ADMINISTRATOR")),
    ):
        ...

    @router.get("/tenants/{tenant_id}/items")
    async def tenant_items(
        user: AuthenticatedUser = Depends(require_tenant()),
        tenant_id: str = Path(...),
    ):
        # tenant_id param phải khớp với JWT claim
        if tenant_id != user.tenant_id:
            raise PermissionError("Tenant access denied")
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException, Request, status

from contract_intelligence.shared.auth.exceptions import (
    AuthenticationError,
)
from contract_intelligence.shared.auth.jwt_service import get_jwt_service
from contract_intelligence.shared.auth.schemas import AuthenticatedUser

# -----------------------------------------------------------------------------
# Header constants
# -----------------------------------------------------------------------------

_AUTH_HEADER: str = "Authorization"
_BEARER_PREFIX: str = "Bearer "
_TENANT_HEADER: str = "X-Tenant-Id"


# -----------------------------------------------------------------------------
# get_current_user — extract & validate JWT from Authorization header
# -----------------------------------------------------------------------------


async def get_current_user(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> AuthenticatedUser:
    """FastAPI dependency: extract JWT from Authorization header, decode & validate.

    Raises:
        HTTPException 401: Token hết hạn, sai secret, hoặc không có token.

    Usage:
        async def endpoint(user: AuthenticatedUser = Depends(get_current_user())):
            ...
    """
    # Extract token
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not authorization.startswith(_BEARER_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format — expected 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization[len(_BEARER_PREFIX) :]

    # Decode & validate
    try:
        jwt_svc = get_jwt_service()
        user = jwt_svc.decode_and_validate_access(token)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    # Attach to request state for downstream access
    request.state.authenticated_user = user

    return user


# -----------------------------------------------------------------------------
# require_role — factory trả dependency kiểm tra RBAC role
# -----------------------------------------------------------------------------


def require_role(*allowed_roles: str) -> Any:
    """Factory trả FastAPI dependency kiểm tra user.role ∈ allowed_roles.

    Args:
        *allowed_roles: Danh sách vai trò được phép, vd "ADMINISTRATOR", "REVIEWER"

    Usage:
        @router.post("/approve")
        async def approve(
            user: AuthenticatedUser = Depends(require_role("ADMINISTRATOR")),
        ):
            ...

        # Multiple roles (any match)
        async def edit(
            user: AuthenticatedUser = Depends(
                require_role("ADMINISTRATOR", "OPERATOR")
            ),
        ):
            ...
    """

    async def _role_checker(
        user: AuthenticatedUser = Depends(get_current_user),
    ) -> AuthenticatedUser:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Insufficient role — required one of {list(allowed_roles)}, got {user.role!r}"
                ),
            )
        return user

    return _role_checker


# -----------------------------------------------------------------------------
# require_tenant — verify X-Tenant-Id header matches JWT claim
# -----------------------------------------------------------------------------


async def require_tenant(
    request: Request,
    x_tenant_id: Annotated[str | None, Header()] = None,
    user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    """FastAPI dependency: verify X-Tenant-Id header == JWT tenant_id claim.

    Raises:
        HTTPException 403: Header tenant khác JWT tenant.

    Usage (per-route):
        @router.get("/tenants/{tenant_id}/items")
        async def items(
            tenant_id: str = Path(...),
            user: AuthenticatedUser = Depends(require_tenant()),
        ):
            ...
            assert tenant_id == user.tenant_id  # đã verified

    Note:
        Dùng cái này cho endpoint có path param tenant_id.
        Endpoint không có tenant_id param không cần gọi cái này
        (user.tenant_id đã đúng vì token được phát cho tenant đó).
    """
    if x_tenant_id is not None and x_tenant_id != user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "type": "https://api.contract-ai.io/errors/TENANT_MISMATCH",
                "title": "Tenant Mismatch",
                "status": 403,
                "detail": (
                    f"X-Tenant-Id header ({x_tenant_id!r}) does not match "
                    f"authenticated tenant ({user.tenant_id!r})"
                ),
            },
        )
    return user


# -----------------------------------------------------------------------------
# Type alias for clean dependency injection signatures
# -----------------------------------------------------------------------------

CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


def role_required(*roles: str) -> Any:
    """Shorthand: ``RoleRequired("ADMINISTRATOR")`` thay cho ``Depends(require_role(...))``."""
    return Depends(require_role(*roles))
