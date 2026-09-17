"""Initial core schema. Schema frozen in 0001_schema.json alongside this revision."""

import json
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None


def upgrade():
    schema = json.loads(Path(__file__).with_name("0001_schema.json").read_text())
    metadata = sa.MetaData()
    for table in schema:
        columns = []
        for col in table["columns"]:
            typ = {"VARCHAR": sa.String, "INTEGER": sa.Integer, "FLOAT": sa.Float, "JSON": sa.JSON}[
                col["type"]
            ]
            args = [sa.ForeignKey(col["fk"])] if col.get("fk") else []
            columns.append(
                sa.Column(
                    col["name"], typ(), *args, primary_key=col["pk"], nullable=col["nullable"]
                )
            )
        constraints = [sa.UniqueConstraint(*keys) for keys in table["unique"]]
        constraints += [sa.CheckConstraint(sql) for sql in table["checks"]]
        built = sa.Table(table["name"], metadata, *columns, *constraints)
        for index in table["indexes"]:
            sa.Index(
                index["name"], *(built.c[name] for name in index["columns"]), unique=index["unique"]
            )
    metadata.create_all(op.get_bind())
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""CREATE FUNCTION reject_immutable_change() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'immutable record'; END; $$ LANGUAGE plpgsql""")
        for table in ("documents", "snapshots", "review_events", "approvals"):
            op.execute(
                f"CREATE TRIGGER immutable_{table} BEFORE UPDATE OR DELETE ON {table} "
                "FOR EACH ROW EXECUTE FUNCTION reject_immutable_change()"
            )


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; restore a verified backup instead.")
