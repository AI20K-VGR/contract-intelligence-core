"""v4__create_core_schema — create all business tables from SQLAlchemy ORM.

Revision ID: v4__create_core_schema
Revises: v3__keycloak_sso_refactor
Create Date: 2026-09-21

Sprint 2: ``v1__init`` was a no-op placeholder. This revision materialises every
ORM table registered on ``Base.metadata`` (dossier, document, job, extraction,
review, conflict, batch, optimization, …). ``app_user`` already exists from
v2/v3 and is skipped via ``checkfirst=True``.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "v4__create_core_schema"
down_revision: str | None = "v3__keycloak_sso_refactor"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tables owned by earlier revisions — never drop on downgrade of this rev.
_PRESERVE_ON_DOWNGRADE = frozenset({"app_user", "alembic_version"})


def upgrade() -> None:
    from contract_intelligence.shared.persistence.base import Base
    from contract_intelligence.shared.persistence.orm_registry import import_all_models

    import_all_models()
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    from contract_intelligence.shared.persistence.base import Base
    from contract_intelligence.shared.persistence.orm_registry import import_all_models

    import_all_models()
    bind = op.get_bind()
    # Drop in reverse dependency order; keep identity table from v2/v3.
    for table in reversed(Base.metadata.sorted_tables):
        if table.name in _PRESERVE_ON_DOWNGRADE:
            continue
        table.drop(bind=bind, checkfirst=True)
