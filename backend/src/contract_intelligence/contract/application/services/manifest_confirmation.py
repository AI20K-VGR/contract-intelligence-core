"""Manifest confirmation application helpers — validation + DTO mapping."""

from __future__ import annotations

from contract_intelligence.contract.application.dtos.manifest_dtos import (
    ConfirmManifestRequest,
    ManifestDocumentRole,
    ManifestDTO,
    ManifestMemberDTO,
    ManifestRelationDTO,
    ManifestStatus,
    RelationConfirmation,
    RelationType,
    normalize_document_role,
    normalize_manifest_status,
)
from contract_intelligence.contract.domain.entities.document import Document
from contract_intelligence.contract.domain.entities.manifest import (
    Manifest,
    ManifestItem,
    ManifestRelation,
)
from contract_intelligence.shared.base import new_ulid
from contract_intelligence.shared.exceptions import (
    DomainErrorCode,
    ManifestValidationError,
    ManifestVersionConflict,
)


def build_manifest_dto(
    manifest: Manifest,
    *,
    latest_job_status: str | None,
    documents_by_id: dict[str, Document] | None = None,
) -> ManifestDTO:
    """Map domain Manifest (+ optional live document stats) → ManifestDTO."""
    docs = documents_by_id or {}
    members: list[ManifestMemberDTO] = []
    for item in sorted(manifest.items, key=lambda i: i.order_index):
        doc = docs.get(item.document_id)
        page_count = item.page_count or (doc.page_count if doc else 0)
        file_size = item.file_size_bytes or (doc.file_size_bytes if doc else 0)
        filename = item.filename or (doc.filename if doc else "")
        members.append(
            ManifestMemberDTO(
                document_id=item.document_id,
                filename=filename,
                role=normalize_document_role(item.doc_type),
                included=bool(item.included),
                order_index=item.order_index,
                page_count=page_count,
                file_size_bytes=file_size,
            )
        )

    relations = [
        ManifestRelationDTO(
            id=rel.id,
            source_document_id=rel.source_document_id,
            target_document_id=rel.target_document_id,
            relation_type=RelationType(rel.relation_type),
            confirmation=RelationConfirmation(rel.confirmation),
        )
        for rel in manifest.relations
    ]

    return ManifestDTO(
        dossier_id=manifest.dossier_id,
        status=normalize_manifest_status(manifest.status),
        version=int(manifest.version or 1),
        latest_job_status=latest_job_status,
        members=members,
        relations=relations,
        confirmed_at=manifest.confirmed_at,
    )


def validate_and_prepare_confirmation(
    *,
    manifest: Manifest,
    request: ConfirmManifestRequest,
    dossier_documents: list[Document],
) -> tuple[list[ManifestItem], list[ManifestRelation]]:
    """Validate confirm payload; return membership + relations ready to persist.

    Raises:
        ManifestVersionConflict: client version ≠ current.
        ManifestValidationError: any 422 rule violation.
    """
    status = normalize_manifest_status(manifest.status)
    if status is ManifestStatus.CONFIRMED:
        raise ManifestValidationError(
            DomainErrorCode.MANIFEST_ALREADY_CONFIRMED,
            "Manifest is already confirmed",
            dossier_id=manifest.dossier_id,
            status=status.value,
        )

    current_version = int(manifest.version or 1)
    if request.version != current_version:
        raise ManifestVersionConflict(
            dossier_id=manifest.dossier_id,
            expected_version=request.version,
            current_version=current_version,
        )

    dossier_doc_ids = {d.id for d in dossier_documents}
    member_ids = [m.document_id for m in request.members]
    member_id_set = set(member_ids)

    # member_unknown — payload references documents outside the dossier
    unknown = sorted(member_id_set - dossier_doc_ids)
    if unknown:
        raise ManifestValidationError(
            DomainErrorCode.MEMBER_UNKNOWN,
            "One or more members are not part of this dossier",
            document_ids=unknown,
        )

    # member_missing — every dossier document must appear in members[]
    missing = sorted(dossier_doc_ids - member_id_set)
    if missing:
        raise ManifestValidationError(
            DomainErrorCode.MEMBER_MISSING,
            "Manifest members omit one or more dossier documents",
            document_ids=missing,
        )

    # member_role_invalid
    for member in request.members:
        try:
            ManifestDocumentRole(member.role)
        except ValueError as exc:
            raise ManifestValidationError(
                DomainErrorCode.MEMBER_ROLE_INVALID,
                f"Invalid member role for document {member.document_id!r}",
                document_id=member.document_id,
                role=str(member.role),
            ) from exc

    # contract_required — at least one included contract
    has_included_contract = any(
        m.included and m.role == ManifestDocumentRole.CONTRACT for m in request.members
    )
    if not has_included_contract:
        raise ManifestValidationError(
            DomainErrorCode.CONTRACT_REQUIRED,
            "At least one included member with role 'contract' is required",
        )

    # relation_missing — every persisted relation id must be present in body
    persisted_ids = {r.id for r in manifest.relations if r.id}
    body_ids = {r.id for r in request.relations if r.id}
    omitted = sorted(persisted_ids - body_ids)
    if omitted:
        raise ManifestValidationError(
            DomainErrorCode.RELATION_MISSING,
            "One or more previously stored relations were omitted",
            relation_ids=omitted,
        )

    # relations_unconfirmed — body must not leave/send unconfirmed
    if any(r.confirmation == RelationConfirmation.UNCONFIRMED for r in request.relations):
        raise ManifestValidationError(
            DomainErrorCode.RELATIONS_UNCONFIRMED,
            "All relations must be confirmed or rejected before confirming the manifest",
        )

    included_ids = {m.document_id for m in request.members if m.included}
    seen_pairs: set[tuple[str, str, str]] = set()

    prepared_relations: list[ManifestRelation] = []
    for rel in request.relations:
        # relation_type_invalid (Pydantic usually catches; keep defensive)
        try:
            rel_type = RelationType(rel.relation_type)
        except ValueError as exc:
            raise ManifestValidationError(
                DomainErrorCode.RELATION_TYPE_INVALID,
                f"Invalid relation_type {rel.relation_type!r}",
                relation_type=str(rel.relation_type),
            ) from exc

        if rel.source_document_id == rel.target_document_id:
            raise ManifestValidationError(
                DomainErrorCode.RELATION_SELF,
                "Relation source and target must be different documents",
                source_document_id=rel.source_document_id,
            )

        if (
            rel.source_document_id not in included_ids
            or rel.target_document_id not in included_ids
        ):
            raise ManifestValidationError(
                DomainErrorCode.RELATION_MEMBER_INVALID,
                "Relation endpoints must reference included members",
                source_document_id=rel.source_document_id,
                target_document_id=rel.target_document_id,
            )

        pair = (rel.source_document_id, rel.target_document_id, rel_type.value)
        if pair in seen_pairs:
            raise ManifestValidationError(
                DomainErrorCode.RELATION_DUPLICATE,
                "Duplicate relation detected",
                source_document_id=rel.source_document_id,
                target_document_id=rel.target_document_id,
                relation_type=rel_type.value,
            )
        seen_pairs.add(pair)

        prepared_relations.append(
            ManifestRelation(
                id=rel.id or new_ulid("mrel_"),
                manifest_id=manifest.id,
                source_document_id=rel.source_document_id,
                target_document_id=rel.target_document_id,
                relation_type=rel_type.value,
                confirmation=RelationConfirmation(rel.confirmation).value,
            )
        )

    docs_by_id = {d.id: d for d in dossier_documents}
    prepared_members: list[ManifestItem] = []
    for member in request.members:
        doc = docs_by_id.get(member.document_id)
        prepared_members.append(
            ManifestItem(
                id=new_ulid("mfi_"),
                manifest_id=manifest.id,
                document_id=member.document_id,
                filename=member.filename or (doc.filename if doc else ""),
                doc_type=ManifestDocumentRole(member.role).value,
                sha256=doc.sha256 if doc else "",
                confidence="1.0",
                order_index=member.order_index,
                included=member.included,
                page_count=member.page_count
                if member.page_count
                else (doc.page_count if doc else 0),
                file_size_bytes=member.file_size_bytes
                if member.file_size_bytes
                else (doc.file_size_bytes if doc else 0),
            )
        )

    return prepared_members, prepared_relations


__all__ = [
    "build_manifest_dto",
    "validate_and_prepare_confirmation",
]
