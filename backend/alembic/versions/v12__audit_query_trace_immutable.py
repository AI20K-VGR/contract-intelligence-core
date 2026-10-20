"""v12__audit_query_trace_immutable — append-only triggers on audit_event + query_trace.

Revision ID: v12__audit_query_trace_immutable
Revises: v11__audit_event_query_trace
Create Date: 2026-09-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v12__audit_query_trace_immutable"
down_revision: str | None = "v11__audit_event_query_trace"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES: tuple[str, ...] = ("audit_event", "query_trace")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    tables = set(sa.inspect(bind).get_table_names())
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION forbid_mutation() RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION
                    'Bảng % là bất biến (append-only), không được phép UPDATE hoặc DELETE',
                    TG_TABLE_NAME;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )
    for table in _TABLES:
        if table not in tables:
            continue
        trigger = f"trg_immutable_{table}"
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS {trigger} ON {table}"))
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER {trigger}
                BEFORE UPDATE OR DELETE ON {table}
                FOR EACH ROW EXECUTE PROCEDURE forbid_mutation()
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    tables = set(sa.inspect(bind).get_table_names())
    for table in _TABLES:
        if table in tables:
            op.execute(sa.text(f"DROP TRIGGER IF EXISTS trg_immutable_{table} ON {table}"))
