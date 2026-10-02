"""Dossier ACL for routes addressed by any id inside a dossier.

Same decision as the contract routes (:func:`shared.acl.dossier_access_decision`):
tenant, role, owner or a live share grant, and ``permission="edit"`` for
changes. Every id kind below resolves to its dossier first:

- ``run_id``, ``finding_id`` → the row's ``dossier_id``;
- ``document_id`` → the document's dossier;
- ``page_id``, ``fact_id``, ``citation_id``, re-OCR ``request_id`` → their
  document, then its dossier.

The ``acl_*`` functions are FastAPI dependencies for read routes
(``dependencies=[Depends(acl_document)]``); write routes call
:func:`require_dossier_action` with the action they need. The M-07 suite
(tests/integration/test_tenant_isolation.py) checks every dossier-scoped route.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.conflict.infrastructure.persistence.orm import FindingORM
from contract_intelligence.contract.infrastructure.persistence.orm import (
    DocumentORM,
    DossierORM,
)
from contract_intelligence.extraction.infrastructure.persistence.orm import (
    CitationORM,
    FactORM,
    PageORM,
    PipelineRunORM,
)
from contract_intelligence.extraction.infrastructure.persistence.orm_reocr import ReOcrRequestORM
from contract_intelligence.shared.acl import (
    AclAction,
    dossier_access_decision,
    dossier_denied_message,
)
from contract_intelligence.shared.auth import AuthenticatedUser, get_current_user
from contract_intelligence.shared.persistence import get_async_session

_BY_DOSSIER: dict[str, Any] = {"run_id": PipelineRunORM, "finding_id": FindingORM}
_BY_DOCUMENT: dict[str, Any] = {
    "page_id": PageORM,
    "fact_id": FactORM,
    "citation_id": CitationORM,
    "request_id": ReOcrRequestORM,
}


async def _dossier_id_for(
    session: AsyncSession, tenant_id: str, kind: str, value: str
) -> str | None:
    if kind == "dossier_id":
        return value
    if kind in _BY_DOSSIER:
        model = _BY_DOSSIER[kind]
        found = await session.scalar(
            select(model.dossier_id).where(model.id == value, model.tenant_id == tenant_id)
        )
        return str(found) if found else None
    document_id = value
    if kind in _BY_DOCUMENT:
        model = _BY_DOCUMENT[kind]
        found = await session.scalar(
            select(model.document_id).where(model.id == value, model.tenant_id == tenant_id)
        )
        if not found:
            return None
        document_id = str(found)
    elif kind != "document_id":
        raise ValueError(f"unknown id kind {kind!r}")
    found = await session.scalar(
        select(DocumentORM.dossier_id).where(
            DocumentORM.id == document_id, DocumentORM.tenant_id == tenant_id
        )
    )
    return str(found) if found else None


async def require_dossier_action(
    session: AsyncSession,
    user: AuthenticatedUser,
    *,
    action: AclAction,
    dossier_id: str | None = None,
    run_id: str | None = None,
    document_id: str | None = None,
    **other_ids: str,
) -> DossierORM:
    """Resolve the dossier behind the one id given and enforce ``action`` on it.

    404 when the id does not exist in the caller's tenant or the dossier is
    deleted — the same answer as for an id that never existed, so nothing
    outside the caller's tenant can be probed; 403 when the caller has no
    live grant allowing ``action``.
    """
    given = {
        key: value
        for key, value in (
            ("dossier_id", dossier_id),
            ("run_id", run_id),
            ("document_id", document_id),
            *other_ids.items(),
        )
        if value is not None
    }
    if len(given) != 1:
        raise ValueError(f"pass exactly one id, got {sorted(given)}")
    ((kind, value),) = given.items()
    resolved = await _dossier_id_for(session, user.tenant_id, kind, value)
    dossier = await session.get(DossierORM, resolved) if resolved else None
    if dossier is None or dossier.deleted_at is not None or dossier.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    decision: dict[str, Any] = {
        "action": action,
        "principal": user,
        "dossier_id": dossier.id,
        "dossier_tenant_id": dossier.tenant_id,
        "metadata": dossier.metadata_json,
    }
    if not dossier_access_decision(**decision):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=dossier_denied_message(**decision),
        )
    return dossier


Session = Annotated[AsyncSession, Depends(get_async_session)]
User = Annotated[AuthenticatedUser, Depends(get_current_user)]


async def acl_dossier(
    dossier_id: Annotated[str, Path(min_length=1)], session: Session, user: User
) -> None:
    await require_dossier_action(session, user, action=AclAction.QUERY, dossier_id=dossier_id)


async def acl_document(
    document_id: Annotated[str, Path(min_length=1)], session: Session, user: User
) -> None:
    await require_dossier_action(session, user, action=AclAction.QUERY, document_id=document_id)


async def acl_run(run_id: Annotated[str, Path(min_length=1)], session: Session, user: User) -> None:
    await require_dossier_action(session, user, action=AclAction.QUERY, run_id=run_id)


async def acl_page(
    page_id: Annotated[str, Path(min_length=1)], session: Session, user: User
) -> None:
    await require_dossier_action(session, user, action=AclAction.QUERY, page_id=page_id)


async def acl_fact(
    fact_id: Annotated[str, Path(min_length=1)], session: Session, user: User
) -> None:
    await require_dossier_action(session, user, action=AclAction.QUERY, fact_id=fact_id)


async def acl_citation(
    citation_id: Annotated[str, Path(min_length=1)], session: Session, user: User
) -> None:
    await require_dossier_action(
        session, user, action=AclAction.CITATION_READ, citation_id=citation_id
    )


async def acl_finding(
    finding_id: Annotated[str, Path(min_length=1)], session: Session, user: User
) -> None:
    await require_dossier_action(
        session, user, action=AclAction.FINDING_READ, finding_id=finding_id
    )


async def acl_dossier_findings(
    dossier_id: Annotated[str, Path(min_length=1)], session: Session, user: User
) -> None:
    await require_dossier_action(
        session, user, action=AclAction.FINDING_READ, dossier_id=dossier_id
    )


async def acl_reocr_request(
    request_id: Annotated[str, Path(min_length=1)], session: Session, user: User
) -> None:
    await require_dossier_action(session, user, action=AclAction.QUERY, request_id=request_id)


__all__ = [
    "acl_citation",
    "acl_document",
    "acl_dossier",
    "acl_dossier_findings",
    "acl_fact",
    "acl_finding",
    "acl_page",
    "acl_reocr_request",
    "acl_run",
    "require_dossier_action",
]
