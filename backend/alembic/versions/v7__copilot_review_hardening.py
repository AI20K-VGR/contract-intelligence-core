"""v7__copilot_review_hardening — immutability triggers + grant table rename.

Revision ID: v7__copilot_review_hardening
Revises: v6__manifest_confirmation
Create Date: 2026-09-22

- Enforce append-only on review_action (and peer audit/machine tables) via
  forbid_mutation() triggers from DOC-04b.
- Rename external_approval → external_approval_grant to match DOC-04b schema.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v7__copilot_review_hardening"
down_revision: str | None = "v6__manifest_confirmation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_IMMUTABLE_TABLES: tuple[str, ...] = (
    "document_text",
    "ocr_line",
    "citation",
    "clause_node",
    "clause_region",
    "doc_table",
    "table_cell",
    "fact",
    "annex_link",
    "finding",
    "finding_side",
    "review_action",
    "job_event",
    "usage_ledger",
    "dossier_approval",
)


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    # ---- rename legacy grant table if present ----
    if "external_approval" in tables and "external_approval_grant" not in tables:
        op.rename_table("external_approval", "external_approval_grant")
        tables.discard("external_approval")
        tables.add("external_approval_grant")

    # ---- append-only enforcement (DOC-04b §11) ----
    # Use EXECUTE PROCEDURE for broad Postgres compatibility with older images;
    # Keycloak/backend stack uses Postgres 16 which accepts EXECUTE FUNCTION too.
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

    for table in _IMMUTABLE_TABLES:
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
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    for table in _IMMUTABLE_TABLES:
        if table not in tables:
            continue
        trigger = f"trg_immutable_{table}"
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS {trigger} ON {table}"))

    op.execute(sa.text("DROP FUNCTION IF EXISTS forbid_mutation()"))

    if "external_approval_grant" in tables and "external_approval" not in tables:
        op.rename_table("external_approval_grant", "external_approval")
