"""v19__purge_unique_sha — purge a dossier that holds several documents.

Revision ID: v19__purge_unique_sha
Revises: v18__query_answer
Create Date: 2026-09-29

purge_dossier_contract_content (v8) set document.sha256 = '[purged]' on every
document of the dossier, but (dossier_id, sha256) is unique: purging a dossier
with a contract and an annex failed. The function is redefined from its current
definition with a per-document marker '[purged]:<document id>' instead.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v19__purge_unique_sha"
down_revision: str | None = "v18__query_answer"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD = "sha256 = ''[purged]''"
_NEW = "sha256 = ''[purged]:'' || id"


def _rewrite(old: str, new: str) -> None:
    op.execute(
        sa.text(
            f"""
            DO $$
            DECLARE
                definition text;
            BEGIN
                IF to_regprocedure('purge_dossier_contract_content(text)') IS NULL THEN
                    RETURN;
                END IF;
                definition := pg_get_functiondef(
                    'purge_dossier_contract_content(text)'::regprocedure
                );
                EXECUTE replace(definition, '{old}', '{new}');
            END
            $$;
            """
        )
    )


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        _rewrite(_OLD, _NEW)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        _rewrite(_NEW, _OLD)
