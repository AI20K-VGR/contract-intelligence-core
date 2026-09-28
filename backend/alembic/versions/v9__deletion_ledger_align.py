"""v9__deletion_ledger_align — match DeletionLedgerORM; drop immutable trigger.

Revision ID: v9__deletion_ledger_align
Revises: v8__dossier_deletion
Create Date: 2026-09-24

v8 initially created an append-only ledger (actor_user_id/phase) on some
environments. The app uses one updatable row per dossier (requested_by /
purge_status). This migration realigns the table and ensures dossier
tombstone columns exist.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "v9__deletion_ledger_align"
down_revision: str | None = "v8__dossier_deletion"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    # Idempotent tombstone columns (in case an older image skipped them).
    if "dossier" in tables:
        cols = {c["name"] for c in inspector.get_columns("dossier")}
        with op.batch_alter_table("dossier") as batch:
            if "deleted_at" not in cols:
                batch.add_column(sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
            if "deleted_by" not in cols:
                batch.add_column(sa.Column("deleted_by", sa.Text(), nullable=True))
            if "purge_status" not in cols:
                batch.add_column(sa.Column("purge_status", sa.Text(), nullable=True))
            if "purge_completed_at" not in cols:
                batch.add_column(
                    sa.Column("purge_completed_at", sa.DateTime(timezone=True), nullable=True)
                )
            if "purge_error" not in cols:
                batch.add_column(sa.Column("purge_error", sa.Text(), nullable=True))
        op.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_dossier_tenant_deleted_at "
                "ON dossier (tenant_id, deleted_at)"
            )
        )

    if "deletion_ledger" not in tables:
        op.create_table(
            "deletion_ledger",
            sa.Column("id", sa.Text(), primary_key=True),
            sa.Column("tenant_id", sa.Text(), nullable=False),
            sa.Column("dossier_id", sa.Text(), nullable=False),
            sa.Column("requested_by", sa.Text(), nullable=False),
            sa.Column(
                "tombstoned_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "purge_status",
                sa.Text(),
                nullable=False,
                server_default="pending",
            ),
            sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "evidence",
                sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
                nullable=True,
            ),
            sa.UniqueConstraint("tenant_id", "dossier_id", name="uq_deletion_ledger_dossier"),
        )
        op.create_index("ix_deletion_ledger_tenant_id", "deletion_ledger", ["tenant_id"])
        op.create_index("ix_deletion_ledger_dossier_id", "deletion_ledger", ["dossier_id"])
        return

    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_immutable_deletion_ledger ON deletion_ledger"))

    cols = {c["name"] for c in inspector.get_columns("deletion_ledger")}
    if "requested_by" in cols and "actor_user_id" not in cols:
        # Already on the target schema.
        op.execute(
            sa.text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_deletion_ledger_dossier "
                "ON deletion_ledger (tenant_id, dossier_id)"
            )
        )
        return

    # Old append-only schema → one-row-per-dossier schema.
    op.rename_table("deletion_ledger", "deletion_ledger_legacy")
    op.create_table(
        "deletion_ledger",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("dossier_id", sa.Text(), nullable=False),
        sa.Column("requested_by", sa.Text(), nullable=False),
        sa.Column(
            "tombstoned_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "purge_status",
            sa.Text(),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "evidence",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.UniqueConstraint("tenant_id", "dossier_id", name="uq_deletion_ledger_dossier"),
    )
    op.create_index("ix_deletion_ledger_tenant_id", "deletion_ledger", ["tenant_id"])
    op.create_index("ix_deletion_ledger_dossier_id", "deletion_ledger", ["dossier_id"])

    # Keep the latest row per dossier; map phase → purge_status.
    op.execute(
        sa.text(
            """
            INSERT INTO deletion_ledger (
                id, tenant_id, dossier_id, requested_by, tombstoned_at,
                purge_status, purged_at, evidence
            )
            SELECT DISTINCT ON (tenant_id, dossier_id)
                id,
                tenant_id,
                dossier_id,
                actor_user_id,
                created_at,
                CASE phase
                    WHEN 'purge_completed' THEN 'completed'
                    WHEN 'purge_failed' THEN 'failed'
                    ELSE 'pending'
                END,
                CASE WHEN phase = 'purge_completed' THEN created_at ELSE NULL END,
                CASE
                    WHEN detail IS NULL THEN NULL
                    WHEN jsonb_typeof(detail::jsonb) = 'object' THEN detail::jsonb
                    ELSE NULL
                END
            FROM deletion_ledger_legacy
            ORDER BY tenant_id, dossier_id, created_at DESC
            """
        )
    )
    op.drop_table("deletion_ledger_legacy")


def downgrade() -> None:
    # Irreversible data reshape — leave schema as-is.
    pass
