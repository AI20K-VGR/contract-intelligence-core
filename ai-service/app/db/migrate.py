from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DBAPIError

MIGRATION_LOCK = 261002064
logger = logging.getLogger(__name__)


def migrate(engine: Engine) -> None:
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    with engine.connect() as cx:
        cx.execute(text("SELECT pg_advisory_lock(:key)"), {"key": MIGRATION_LOCK})
        cx.commit()
        try:
            with cx.begin():
                # CREATE SCHEMA IF NOT EXISTS still needs CREATE on the database,
                # which the #52 ``ai2`` role (owner of a pre-made schema) lacks.
                if cx.execute(text("SELECT to_regnamespace('ai2')")).scalar() is None:
                    cx.execute(text("CREATE SCHEMA ai2"))
                config.attributes["connection"] = cx
                command.upgrade(config, "head")
                ensure_vector_column(cx)
        finally:
            if cx.in_transaction():
                cx.rollback()
            cx.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": MIGRATION_LOCK})
            cx.commit()


def _vector_schema(cx: Connection) -> str | None:
    return cx.execute(text("""SELECT n.nspname FROM pg_extension e
        JOIN pg_namespace n ON n.oid = e.extnamespace WHERE e.extname = 'vector'""")).scalar()


def ensure_vector_column(cx: Connection) -> bool:
    """Re-check pgvector on every boot; revision 0002 runs only once.

    The extension may be installed after AI2's first boot (image swap or a DBA
    grant), so the embedding column cannot live only in alembic history. Any
    failure leaves vector recall degraded (``VECTOR_EXTENSION_UNAVAILABLE``)
    without failing the migration transaction.
    """
    schema = _vector_schema(cx)
    if schema is None:
        if not cx.execute(text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")).scalar():
            logger.warning("ai2.vector_unavailable reason_code=VECTOR_EXTENSION_UNAVAILABLE cause=not_installable")
            return False
        try:
            with cx.begin_nested():
                cx.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        except DBAPIError as exc:
            logger.warning("ai2.vector_unavailable reason_code=VECTOR_EXTENSION_UNAVAILABLE cause=%s",
                           type(exc.orig).__name__)
            return False
        schema = _vector_schema(cx)
    present = cx.execute(text("""SELECT 1 FROM information_schema.columns WHERE table_schema = 'ai2'
        AND table_name = 'vector_segments' AND column_name = 'embedding'""")).scalar()
    if not present:
        vector_type = f"{cx.dialect.identifier_preparer.quote(schema)}.vector"
        cx.execute(text(f"ALTER TABLE ai2.vector_segments ADD COLUMN IF NOT EXISTS embedding {vector_type}"))
        logger.info("ai2.vector_column_added extension_schema=%s", schema)
    return True
