"""Generate the initial migration's frozen DDL description (run once at authoring)."""

import json
from pathlib import Path

from sqlalchemy import CheckConstraint, UniqueConstraint

from app import models  # noqa: F401
from app.db import Base

tables = []
for table in Base.metadata.sorted_tables:
    tables.append(
        {
            "name": table.name,
            "columns": [
                {
                    "name": col.name,
                    "type": str(col.type).split("(")[0],
                    "pk": col.primary_key,
                    "nullable": col.nullable,
                    "fk": next((f.target_fullname for f in col.foreign_keys), None),
                }
                for col in table.columns
            ],
            "unique": [
                [c.name for c in constraint.columns]
                for constraint in table.constraints
                if isinstance(constraint, UniqueConstraint)
            ],
            "checks": [str(c.sqltext) for c in table.constraints if isinstance(c, CheckConstraint)],
            "indexes": [
                {"name": i.name, "columns": [c.name for c in i.columns], "unique": i.unique}
                for i in table.indexes
            ],
        }
    )
Path("migrations/versions/0001_schema.json").write_text(json.dumps(tables, indent=2) + "\n")
