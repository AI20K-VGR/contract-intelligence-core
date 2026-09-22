"""v6__manifest_confirmation — version/included/relations for Manifest confirm API.

Revision ID: v6__manifest_confirmation
Revises: v5__job_lease_columns
Create Date: 2026-09-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v6__manifest_confirmation"
down_revision: str | None = "v5__job_lease_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "manifest" in tables:
        cols = {c["name"] for c in inspector.get_columns("manifest")}
        if "version" not in cols:
            op.add_column(
                "manifest",
                sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            )
        # Normalize legacy status values if present
        op.execute(
            sa.text(
                "UPDATE manifest SET status = 'pending' "
                "WHERE lower(status) IN ('draft', 'pending')"
            )
        )
        op.execute(
            sa.text(
                "UPDATE manifest SET status = 'confirmed' "
                "WHERE lower(status) IN ('confirmed', 'confirm')"
            )
        )

    if "manifest_item" in tables:
        cols = {c["name"] for c in inspector.get_columns("manifest_item")}
        if "included" not in cols:
            op.add_column(
                "manifest_item",
                sa.Column("included", sa.Boolean(), nullable=False, server_default="true"),
            )
        if "page_count" not in cols:
            op.add_column(
                "manifest_item",
                sa.Column("page_count", sa.Integer(), nullable=False, server_default="0"),
            )
        if "file_size_bytes" not in cols:
            op.add_column(
                "manifest_item",
                sa.Column(
                    "file_size_bytes", sa.Integer(), nullable=False, server_default="0"
                ),
            )

    if "manifest_relation" not in tables:
        op.create_table(
            "manifest_relation",
            sa.Column("id", sa.Text(), primary_key=True),
            sa.Column(
                "manifest_id",
                sa.Text(),
                sa.ForeignKey("manifest.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("source_document_id", sa.Text(), nullable=False),
            sa.Column("target_document_id", sa.Text(), nullable=False),
            sa.Column("relation_type", sa.Text(), nullable=False),
            sa.Column(
                "confirmation",
                sa.Text(),
                nullable=False,
                server_default="unconfirmed",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
        )
        op.create_index(
            "ix_manifest_relation_manifest_id",
            "manifest_relation",
            ["manifest_id"],
        )
        op.create_index(
            "ix_manifest_relation_pair",
            "manifest_relation",
            [
                "manifest_id",
                "source_document_id",
                "target_document_id",
                "relation_type",
            ],
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "manifest_relation" in tables:
        op.drop_table("manifest_relation")

    if "manifest_item" in tables:
        cols = {c["name"] for c in inspector.get_columns("manifest_item")}
        for col in ("file_size_bytes", "page_count", "included"):
            if col in cols:
                op.drop_column("manifest_item", col)

    if "manifest" in tables:
        cols = {c["name"] for c in inspector.get_columns("manifest")}
        if "version" in cols:
            op.drop_column("manifest", "version")
