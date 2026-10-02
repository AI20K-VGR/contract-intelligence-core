from __future__ import annotations

import os
import threading
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url


def database_url() -> str | None:
    return os.getenv("AI2_DATABASE_URL") or None


def validate_database_config() -> None:
    if os.getenv("AI2_REQUIRE_DATABASE", "false").casefold() in {"1", "true", "yes", "on"} and not database_url():
        raise RuntimeError("AI2_REQUIRE_DATABASE requires AI2_DATABASE_URL")
    if database_url() and make_url(database_url()).get_backend_name() != "postgresql":
        raise RuntimeError("AI2_DATABASE_URL must select PostgreSQL")


@lru_cache(maxsize=8)
def get_engine(url: str | None = None) -> Engine:
    resolved = url or database_url()
    if not resolved:
        raise RuntimeError("AI2_DATABASE_URL is required for PostgreSQL persistence")
    parsed = make_url(resolved)
    if parsed.get_backend_name() != "postgresql":
        raise ValueError("AI2 persistence requires PostgreSQL")
    parsed = parsed.set(drivername="postgresql+psycopg")
    return create_engine(parsed, pool_pre_ping=True, pool_size=5, max_overflow=5,
                         connect_args={"connect_timeout": 10}, hide_parameters=True)


_ready: set[Engine] = set()
_ready_lock = threading.Lock()


def ensure_database(engine: Engine) -> None:
    with _ready_lock:
        if engine not in _ready:
            from app.db.migrate import migrate
            migrate(engine)
            _ready.add(engine)


class SqlRow:
    """Both positional and named access for the existing durable store codecs."""

    def __init__(self, row):
        self.row = row

    def __getitem__(self, key):
        return self.row._mapping[key] if isinstance(key, str) else self.row[key]


class SqlResult:
    def __init__(self, result):
        self.result = result
        self.rowcount = result.rowcount

    def fetchone(self):
        row = self.result.fetchone()
        return SqlRow(row) if row is not None else None

    def fetchall(self):
        return [SqlRow(row) for row in self.result.fetchall()]


class DurableConnection:
    """Bind portable durable-store statements through SQLAlchemy Core.

    SQL is owned by the store; values always remain bound parameters. Migration
    and dialect-specific operations stay outside this boundary.
    """

    def __init__(self, engine: Engine):
        self.connection = engine.connect()
        self.connection.execute(text("SET LOCAL search_path TO ai2, public"))

    def execute(self, statement: str, parameters=()) -> SqlResult:
        parts = statement.split("?")
        if len(parts) - 1 != len(parameters):
            raise ValueError("durable statement binding count mismatch")
        query = parts[0]
        for index, part in enumerate(parts[1:]):
            query += f":p{index}" + part
        return SqlResult(self.connection.execute(text(query), {f"p{i}": value for i, value in enumerate(parameters)}))

    def commit(self) -> None:
        self.connection.commit()
        self.connection.execute(text("SET LOCAL search_path TO ai2, public"))

    def rollback(self) -> None:
        self.connection.rollback()

    def close(self) -> None:
        self.connection.close()


def postgres_connection() -> DurableConnection:
    engine = get_engine()
    ensure_database(engine)
    return DurableConnection(engine)
