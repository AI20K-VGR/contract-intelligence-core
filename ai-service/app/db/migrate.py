from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import Engine

MIGRATION_LOCK = 261002064


def migrate(engine: Engine) -> None:
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    with engine.connect() as cx:
        cx.execute(text("SELECT pg_advisory_lock(:key)"), {"key": MIGRATION_LOCK})
        cx.commit()
        try:
            with cx.begin():
                cx.execute(text("CREATE SCHEMA IF NOT EXISTS ai2"))
                config.attributes["connection"] = cx
                command.upgrade(config, "head")
        finally:
            if cx.in_transaction():
                cx.rollback()
            cx.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": MIGRATION_LOCK})
            cx.commit()
