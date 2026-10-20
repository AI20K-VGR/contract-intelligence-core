from __future__ import annotations

from app.contracts.models import (
    HandoffIssue,
    LifecycleState,
    PageSnapshot,
    ReviewState,
    StructuralNode,
    TableSnapshot,
    TenantProfile,
    ValidatedHandoff,
    VersionPins,
)

REQUIRED_PIN_FIELDS = (
    "manifest_version",
    "source_snapshot_digest",
    "tenant_profile_version",
    "policy_version",
    "ocr_run_version",
    "reconstruction_version",
    "extraction_version",
)


class HandoffValidator:
    def validate(
        self,
        *,
        tenant_id: str,
        dossier_id: str,
        pins: VersionPins,
        pages: list[PageSnapshot],
        nodes: list[StructuralNode],
        tables: list[TableSnapshot],
        profile: TenantProfile,
        expected_page_count: int | None = None,
        lifecycle: LifecycleState = LifecycleState.ACTIVE,
        pdf_bytes: bytes | None = None,
    ) -> ValidatedHandoff:
        issues: list[HandoffIssue] = []
        blocked = False
        if pdf_bytes is not None:
            issues.append(
                HandoffIssue(
                    code="NO_PDF_BYTES",
                    message="AI2 must not read PDF bytes",
                    review_state=ReviewState.BLOCKED,
                )
            )
            blocked = True
        if lifecycle in {LifecycleState.SOFT_DELETED, LifecycleState.PURGED, LifecycleState.PURGE_PENDING}:
            issues.append(
                HandoffIssue(
                    code="LIFECYCLE",
                    message="dossier not active",
                    review_state=ReviewState.BLOCKED,
                )
            )
            blocked = True
        for name in REQUIRED_PIN_FIELDS:
            if getattr(pins, name) in (None, "", 0):
                issues.append(
                    HandoffIssue(
                        code="MISSING_PIN",
                        message=name,
                        review_state=ReviewState.BLOCKED,
                    )
                )
                blocked = True
        if expected_page_count is not None and len(pages) != expected_page_count:
            issues.append(
                HandoffIssue(
                    code="PAGE_INVENTORY",
                    message=f"expected {expected_page_count} pages, got {len(pages)}",
                    review_state=ReviewState.NEEDS_REVIEW,
                )
            )
        for page in pages:
            if page.quality == "FAILED":
                issues.append(
                    HandoffIssue(
                        code="PAGE_FAILED",
                        message=page.page_revision_id,
                        review_state=ReviewState.BLOCKED,
                    )
                )
                blocked = True
            elif page.quality == "ENCRYPTED":
                issues.append(
                    HandoffIssue(
                        code="PAGE_QUALITY",
                        message=page.page_revision_id,
                        review_state=ReviewState.BLOCKED,
                    )
                )
                blocked = True
            elif page.quality == "EMPTY":
                issues.append(
                    HandoffIssue(
                        code="PAGE_QUALITY",
                        message=page.page_revision_id,
                        review_state=ReviewState.NEEDS_REVIEW,
                    )
                )
            elif page.quality == "LOW":
                issues.append(
                    HandoffIssue(
                        code="PAGE_QUALITY",
                        message=page.page_revision_id,
                        review_state=ReviewState.NEEDS_REVIEW,
                    )
                )
        for node in nodes:
            if node.status != "CONFIRMED":
                issues.append(
                    HandoffIssue(
                        code="NODE_STATUS",
                        message=f"{node.node_id}:{node.status}",
                        review_state=ReviewState.NEEDS_REVIEW,
                    )
                )
        return ValidatedHandoff(
            tenant_id=tenant_id,
            dossier_id=dossier_id,
            pins=pins,
            pages=pages,
            nodes=nodes,
            tables=tables,
            profile=profile,
            issues=issues,
            blocked=blocked,
        )
