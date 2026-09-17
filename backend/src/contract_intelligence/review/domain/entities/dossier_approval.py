"""DossierApproval — snapshot ký duyệt cuối cùng (append-only)."""

from __future__ import annotations

from dataclasses import dataclass, field

from contract_intelligence.shared.base import BaseEntity, new_ulid


@dataclass(eq=False)
class DossierApproval(BaseEntity[str]):
    id: str = field(default_factory=lambda: new_ulid("apr_"))
    dossier_id: str = ""
    run_id: str = ""
    approved_by: str = ""
    snapshot_sha256: str = ""
    comment: str | None = None
