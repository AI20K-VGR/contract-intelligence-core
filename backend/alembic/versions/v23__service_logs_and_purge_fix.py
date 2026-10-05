"""Durable cross-service diagnostics and safe multi-document purge.

The local E2E path needs one place where a Backend/AI2/Frontend log receipt
can be stored and queried by an operator.  The same migration also repairs the
PostgreSQL purge function: ``document(dossier_id, sha256)`` is unique, so the
old ``sha256='[purged]'`` assignment failed whenever a dossier had two files.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "v23__service_logs_and_purge_fix"
down_revision: str | None = "v22__reprocess_idempotency"
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


def _replace_purge_function() -> None:
    """Install the v8 function with a unique redaction marker per document."""

    disable_blocks = "\n".join(
        f"    IF to_regclass('public.{table}') IS NOT NULL THEN "
        f"EXECUTE 'ALTER TABLE {table} DISABLE TRIGGER trg_immutable_{table}'; END IF;"
        for table in _CONTENT_TABLES_FOR_TRIGGER_DISABLE
    )
    enable_blocks = "\n".join(
        f"    IF to_regclass('public.{table}') IS NOT NULL THEN "
        f"EXECUTE 'ALTER TABLE {table} ENABLE TRIGGER trg_immutable_{table}'; END IF;"
        for table in _CONTENT_TABLES_FOR_TRIGGER_DISABLE
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
                       sha256 = '[purged]:' || id,
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

            {enable_blocks}
            END;
            $$;
            """
        )
    )


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if "service_log_event" not in tables:
        op.create_table(
            "service_log_event",
            sa.Column("id", sa.Text(), primary_key=True),
            sa.Column("tenant_id", sa.Text(), nullable=True),
            sa.Column("service", sa.Text(), nullable=False),
            sa.Column("source", sa.Text(), nullable=False, server_default="docker"),
            sa.Column("level", sa.Text(), nullable=False, server_default="INFO"),
            sa.Column("event", sa.Text(), nullable=False),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("dossier_id", sa.Text(), nullable=True),
            sa.Column("run_id", sa.Text(), nullable=True),
            sa.Column("job_id", sa.Text(), nullable=True),
            sa.Column("trace_id", sa.Text(), nullable=True),
            sa.Column("request_id", sa.Text(), nullable=True),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "payload",
                sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
                nullable=True,
            ),
        )
        op.create_index(
            "ix_service_log_event_service_occurred",
            "service_log_event",
            ["service", "occurred_at"],
        )
        op.create_index(
            "ix_service_log_event_dossier_occurred",
            "service_log_event",
            ["dossier_id", "occurred_at"],
        )
        op.create_index(
            "ix_service_log_event_run_occurred",
            "service_log_event",
            ["run_id", "occurred_at"],
        )

    # The function exists from v8 on every supported database.  CREATE OR
    # REPLACE keeps this migration safe on databases that skipped a legacy
    # revision during an earlier bootstrap.
    _replace_purge_function()


def downgrade() -> None:
    # Keep diagnostics and the corrected purge function on rollback. Dropping
    # service logs would erase the audit trail, while restoring the previous
    # purge function would reintroduce duplicate-SHA data loss.
    return
