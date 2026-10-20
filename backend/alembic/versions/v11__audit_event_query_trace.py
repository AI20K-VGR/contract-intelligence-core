"""v11__audit_event_query_trace — pipeline audit trail + durable QueryTrace.

Revision ID: v11__audit_event_query_trace
Revises: v10__ai2_pipeline_cols
Create Date: 2026-09-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v11__audit_event_query_trace"
down_revision: str | None = "v10__ai2_pipeline_cols"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())

    if "audit_event" not in tables:
        op.create_table(
            "audit_event",
            sa.Column("id", sa.Text(), primary_key=True),
            sa.Column("tenant_id", sa.Text(), nullable=False),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("actor_id", sa.Text(), nullable=False),
            sa.Column("action", sa.Text(), nullable=False),
            sa.Column("entity_type", sa.Text(), nullable=False),
            sa.Column("entity_id", sa.Text(), nullable=False),
            sa.Column("dossier_id", sa.Text(), nullable=True),
            sa.Column("run_id", sa.Text(), nullable=True),
            sa.Column("from_state", sa.Text(), nullable=True),
            sa.Column("to_state", sa.Text(), nullable=True),
            sa.Column("detail", sa.Text(), nullable=True),
        )
        op.create_index("ix_audit_event_tenant_id", "audit_event", ["tenant_id"])
        op.create_index("ix_audit_event_action", "audit_event", ["action"])
        op.create_index("ix_audit_event_dossier_id", "audit_event", ["dossier_id"])
        op.create_index("ix_audit_event_run_id", "audit_event", ["run_id"])

    if "query_trace" not in tables:
        op.create_table(
            "query_trace",
            sa.Column("id", sa.Text(), primary_key=True),
            sa.Column("tenant_id", sa.Text(), nullable=False),
            sa.Column("dossier_id", sa.Text(), nullable=False),
            sa.Column("actor_id", sa.Text(), nullable=False),
            sa.Column("endpoint", sa.Text(), nullable=False),
            sa.Column("query", sa.Text(), nullable=False),
            sa.Column("snapshot_version", sa.Text(), nullable=False),
            sa.Column("snapshot_digest", sa.Text(), nullable=True),
            sa.Column("query_contract_version", sa.Text(), nullable=False),
            sa.Column("state", sa.Text(), nullable=True),
            sa.Column("citations", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("acl_decision", sa.Text(), nullable=False),
            sa.Column("dropped_citations", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_code", sa.Text(), nullable=True),
            sa.Column("latency_ms", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_query_trace_tenant_id", "query_trace", ["tenant_id"])
        op.create_index("ix_query_trace_dossier_id", "query_trace", ["dossier_id"])
        op.create_index("ix_query_trace_actor_id", "query_trace", ["actor_id"])
        op.create_index("ix_query_trace_created_at", "query_trace", ["created_at"])


def downgrade() -> None:
    op.drop_table("query_trace")
    op.drop_table("audit_event")
