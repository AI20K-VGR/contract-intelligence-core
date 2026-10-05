"""Additive tenant lexicon governance; immutable records cannot be rewritten."""

from __future__ import annotations

from alembic import op
from sqlalchemy import inspect

revision = "v21__tenant_lexicon"
down_revision = "v20__ai2_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from contract_intelligence.shared.ai.tenant_lexicon_store import LEXICON_TABLES

    bind = op.get_bind()
    inspector = inspect(bind)
    for table in LEXICON_TABLES:
        if inspector.has_table(table.name):
            # v4 creates current ORM metadata on fresh installs. Validate every
            # governance constraint before accepting those pre-created tables.
            actual_columns = inspector.get_columns(table.name)
            expected_columns = {
                (column.name, str(column.type.compile(dialect=bind.dialect)), column.nullable)
                for column in table.columns
            }
            observed_columns = {
                (
                    column["name"],
                    str(column["type"].compile(dialect=bind.dialect)),
                    column["nullable"],
                )
                for column in actual_columns
            }
            actual_pk = inspector.get_pk_constraint(table.name)["constrained_columns"]
            expected_pk = [column.name for column in table.primary_key.columns]
            expected_fks = {
                (
                    tuple(element.parent.name for element in fk.elements),
                    next(iter(fk.elements)).column.table.name,
                    tuple(element.column.name for element in fk.elements),
                )
                for fk in table.foreign_key_constraints
            }
            observed_fks = {
                (
                    tuple(fk["constrained_columns"]),
                    fk["referred_table"],
                    tuple(fk["referred_columns"]),
                )
                for fk in inspector.get_foreign_keys(table.name)
            }
            if (
                observed_columns != expected_columns
                or actual_pk != expected_pk
                or observed_fks != expected_fks
                or inspector.get_unique_constraints(table.name)
                or inspector.get_indexes(table.name)
            ):
                raise RuntimeError(f"Pre-existing governance schema mismatch: {table.name}")
        table.create(bind, checkfirst=True)
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""CREATE OR REPLACE FUNCTION tenant_lexicon_immutable() RETURNS trigger AS $$
            BEGIN RAISE EXCEPTION 'tenant lexicon history is immutable'; END;
            $$ LANGUAGE plpgsql""")
        for table in LEXICON_TABLES:
            if table.name != "tenant_lexicon_head":
                op.execute(f"DROP TRIGGER IF EXISTS {table.name}_immutable ON {table.name}")
                op.execute(
                    f"CREATE TRIGGER {table.name}_immutable BEFORE UPDATE OR DELETE "
                    f"ON {table.name} FOR EACH ROW EXECUTE FUNCTION tenant_lexicon_immutable()"
                )


def downgrade() -> None:
    # Consumer v20 ignores additive tables. Rollback disables router/activation
    # in code, retaining history and append-only protection. Re-upgrade validates
    # and reuses the retained schema rather than discarding approved profiles.
    pass
