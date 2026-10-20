"""v26__upload_session — chunked dossier upload sessions (issue #145).

Revision ID: v26__upload_session
Revises: v25__revoked_session
Create Date: 2026-10-19

Cloudflare Free cuts a request still sending its body after ~125 s, so a large
dossier is sent as numbered chunks. ``upload_session`` holds what was declared
(files, sizes, metadata) and, once completed, the dossier it became;
``upload_session_chunk`` holds one row per stored chunk (MinIO object under
``uploads/{tenant_id}/{upload_id}/``). Sessions expire after
``upload_session_ttl_seconds`` and are swept with their chunks.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "v26__upload_session"
down_revision: str | None = "v25__revoked_session"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("upload_session"):
        op.create_table(
            "upload_session",
            sa.Column("id", sa.Text(), primary_key=True),
            sa.Column("tenant_id", sa.Text(), nullable=False),
            sa.Column("user_id", sa.Text(), nullable=False),
            sa.Column("status", sa.Text(), nullable=False),
            sa.Column("dossier_metadata", _JSON, nullable=False),
            sa.Column("files", _JSON, nullable=False),
            sa.Column("chunk_bytes", sa.Integer(), nullable=False),
            sa.Column("dossier_id", sa.Text(), nullable=True),
            sa.Column("job_id", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint(
                "status IN ('open', 'completing', 'completed', 'cancelled')",
                name="ck_upload_session_status",
            ),
        )
        op.create_index("ix_upload_session_expires_at", "upload_session", ["expires_at"])
        op.create_index(
            "ix_upload_session_owner", "upload_session", ["tenant_id", "user_id", "status"]
        )
    if not inspector.has_table("upload_session_chunk"):
        op.create_table(
            "upload_session_chunk",
            sa.Column(
                "upload_id",
                sa.Text(),
                sa.ForeignKey("upload_session.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column("file_index", sa.Integer(), primary_key=True),
            sa.Column("chunk_no", sa.Integer(), primary_key=True),
            sa.Column("size_bytes", sa.Integer(), nullable=False),
            sa.Column("sha256", sa.Text(), nullable=False),
            sa.Column("object_path", sa.Text(), nullable=False),
            sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("upload_session_chunk")
    op.drop_index("ix_upload_session_owner", table_name="upload_session")
    op.drop_index("ix_upload_session_expires_at", table_name="upload_session")
    op.drop_table("upload_session")
