"""v8__dossier_deletion — tombstone columns, deletion_ledger, purge function.

Revision ID: v8__dossier_deletion
Revises: v7__copilot_review_hardening
Create Date: 2026-09-24

Two-step dossier deletion (mentor + FE contract):
  1. Tombstone — hide dossier, cancel jobs, write deletion_ledger
  2. Purge — remove contract content via SECURITY DEFINER function;
     never DELETE dossier / job / pipeline_run shells; never touch
     usage_ledger / review_action / job_event / deletion_ledger rows
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v8__dossier_deletion"
down_revision: str | None = "v7__copilot_review_hardening"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONTENT_TABLES_FOR_TRIGGER_DISABLE: tuple[str, ...] = (
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
)


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    # ---- dossier tombstone / purge columns ----
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

    # ---- document.blob_uri nullable (purged docs keep shell row) ----
    if "document" in tables:
        doc_cols = {c["name"] for c in inspector.get_columns("document")}
        if "blob_uri" in doc_cols:
            with op.batch_alter_table("document") as batch:
                batch.alter_column("blob_uri", existing_type=sa.Text(), nullable=True)

    # ---- deletion_ledger ----
    if "deletion_ledger" not in tables:
        op.create_table(
            "deletion_ledger",
            sa.Column("id", sa.Text(), primary_key=True),
            sa.Column("tenant_id", sa.Text(), nullable=False),
            sa.Column("dossier_id", sa.Text(), nullable=False),
            sa.Column("actor_user_id", sa.Text(), nullable=False),
            sa.Column("phase", sa.Text(), nullable=False),
            sa.Column("detail", sa.JSON(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
        )
        op.create_index(
            "ix_deletion_ledger_dossier_created",
            "deletion_ledger",
            ["dossier_id", "created_at"],
        )
        op.create_index(
            "ix_deletion_ledger_tenant",
            "deletion_ledger",
            ["tenant_id"],
        )

    # Append-only trigger on deletion_ledger (same pattern as v7)
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
    op.execute(
        sa.text("DROP TRIGGER IF EXISTS trg_immutable_deletion_ledger ON deletion_ledger")
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER trg_immutable_deletion_ledger
            BEFORE UPDATE OR DELETE ON deletion_ledger
            FOR EACH ROW EXECUTE PROCEDURE forbid_mutation()
            """
        )
    )

    # ---- SECURITY DEFINER purge function (Postgres) ----
    # Disable content immutability triggers, delete/redact content, re-enable.
    # Never touches usage_ledger, review_action, job_event, deletion_ledger,
    # dossier_approval rows; never DELETE dossier / job / pipeline_run shells.
    disable_blocks = "\n".join(
        f"    IF to_regclass('public.{t}') IS NOT NULL THEN "
        f"EXECUTE 'ALTER TABLE {t} DISABLE TRIGGER trg_immutable_{t}'; END IF;"
        for t in _CONTENT_TABLES_FOR_TRIGGER_DISABLE
    )
    enable_blocks = "\n".join(
        f"    IF to_regclass('public.{t}') IS NOT NULL THEN "
        f"EXECUTE 'ALTER TABLE {t} ENABLE TRIGGER trg_immutable_{t}'; END IF;"
        for t in _CONTENT_TABLES_FOR_TRIGGER_DISABLE
    )

    op.execute(
        sa.text(
            f"""
            CREATE OR REPLACE FUNCTION purge_dossier_contract_content(p_dossier_id text)
            RETURNS void
            LANGUAGE plpgsql
            SECURITY DEFINER
            SET search_path = public
            AS $$
            DECLARE
                doc_ids text[];
            BEGIN
                SELECT coalesce(array_agg(id), ARRAY[]::text[])
                  INTO doc_ids
                  FROM document
                 WHERE dossier_id = p_dossier_id;

            {disable_blocks}

                -- finding_side before finding
                IF to_regclass('public.finding_side') IS NOT NULL THEN
                    DELETE FROM finding_side
                     WHERE finding_id IN (
                        SELECT id FROM finding WHERE dossier_id = p_dossier_id
                     );
                END IF;
                IF to_regclass('public.finding') IS NOT NULL THEN
                    DELETE FROM finding WHERE dossier_id = p_dossier_id;
                END IF;
                IF to_regclass('public.annex_link') IS NOT NULL THEN
                    DELETE FROM annex_link WHERE dossier_id = p_dossier_id;
                END IF;

                IF to_regclass('public.table_cell') IS NOT NULL
                   AND to_regclass('public.doc_table') IS NOT NULL THEN
                    DELETE FROM table_cell
                     WHERE table_id IN (
                        SELECT id FROM doc_table WHERE document_id = ANY(doc_ids)
                     );
                END IF;
                IF to_regclass('public.doc_table') IS NOT NULL THEN
                    DELETE FROM doc_table WHERE document_id = ANY(doc_ids);
                END IF;
                IF to_regclass('public.clause_region') IS NOT NULL
                   AND to_regclass('public.clause_node') IS NOT NULL THEN
                    DELETE FROM clause_region
                     WHERE clause_node_id IN (
                        SELECT id FROM clause_node WHERE document_id = ANY(doc_ids)
                     );
                END IF;
                IF to_regclass('public.clause_node') IS NOT NULL THEN
                    DELETE FROM clause_node WHERE document_id = ANY(doc_ids);
                END IF;
                IF to_regclass('public.fact') IS NOT NULL THEN
                    DELETE FROM fact WHERE document_id = ANY(doc_ids);
                END IF;
                IF to_regclass('public.citation') IS NOT NULL THEN
                    DELETE FROM citation WHERE document_id = ANY(doc_ids);
                END IF;
                IF to_regclass('public.ocr_line') IS NOT NULL THEN
                    DELETE FROM ocr_line WHERE document_id = ANY(doc_ids);
                END IF;
                IF to_regclass('public.document_text') IS NOT NULL THEN
                    DELETE FROM document_text WHERE document_id = ANY(doc_ids);
                END IF;

                IF to_regclass('public.page') IS NOT NULL THEN
                    UPDATE page
                       SET render_blob_uri = NULL,
                           preview_blob_uri = NULL,
                           features = NULL
                     WHERE document_id = ANY(doc_ids);
                END IF;

                UPDATE document
                   SET filename = '[purged]',
                       blob_uri = NULL,
                       sha256 = '[purged]',
                       signing_date = NULL,
                       effective_date = NULL
                 WHERE dossier_id = p_dossier_id;

                UPDATE dossier
                   SET name = '[deleted]',
                       metadata = NULL,
                       checksum = NULL,
                       updated_at = now()
                 WHERE id = p_dossier_id;

                IF to_regclass('public.manifest') IS NOT NULL THEN
                    -- clear member filenames (notes live on metadata / items)
                    UPDATE manifest_item
                       SET filename = '[purged]'
                     WHERE manifest_id IN (
                        SELECT id FROM manifest WHERE dossier_id = p_dossier_id
                     );
                END IF;

                UPDATE job
                   SET error_code = NULL,
                       error_detail = NULL,
                       lease_owner = NULL,
                       lease_expires_at = NULL,
                       updated_at = now()
                 WHERE dossier_id = p_dossier_id;

                IF to_regclass('public.pipeline_run') IS NOT NULL THEN
                    UPDATE pipeline_run
                       SET error_code = NULL,
                           error_detail = NULL,
                           config_snapshot = NULL
                     WHERE dossier_id = p_dossier_id;
                END IF;

                IF to_regclass('public.pipeline_step') IS NOT NULL THEN
                    UPDATE pipeline_step
                       SET metrics = NULL
                     WHERE run_id IN (
                        SELECT id FROM pipeline_run WHERE dossier_id = p_dossier_id
                     );
                END IF;

                IF to_regclass('public.reocr_request') IS NOT NULL THEN
                    UPDATE reocr_request
                       SET reason = '[purged]'
                     WHERE document_id = ANY(doc_ids);
                END IF;

                -- Redact approval comment text only (keep row)
                IF to_regclass('public.dossier_approval') IS NOT NULL THEN
                    -- append-only: cannot UPDATE — leave comment as historical audit
                    NULL;
                END IF;

            {enable_blocks}
            END;
            $$;
            """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    op.execute(sa.text("DROP FUNCTION IF EXISTS purge_dossier_contract_content(text)"))

    if "deletion_ledger" in tables:
        op.execute(
            sa.text("DROP TRIGGER IF EXISTS trg_immutable_deletion_ledger ON deletion_ledger")
        )
        op.drop_index("ix_deletion_ledger_tenant", table_name="deletion_ledger")
        op.drop_index("ix_deletion_ledger_dossier_created", table_name="deletion_ledger")
        op.drop_table("deletion_ledger")

    if "dossier" in tables:
        cols = {c["name"] for c in inspector.get_columns("dossier")}
        op.execute(sa.text("DROP INDEX IF EXISTS ix_dossier_tenant_deleted_at"))
        with op.batch_alter_table("dossier") as batch:
            for col in (
                "purge_error",
                "purge_completed_at",
                "purge_status",
                "deleted_by",
                "deleted_at",
            ):
                if col in cols:
                    batch.drop_column(col)

    if "document" in tables:
        with op.batch_alter_table("document") as batch:
            batch.alter_column("blob_uri", existing_type=sa.Text(), nullable=False)
