"""Create or refresh the ``ai2`` login role (ADR-14, issue #52).

Run by ``scripts/entrypoint.sh`` after ``alembic upgrade heads``, as the
backend superuser. Every step is idempotent, so the password follows
``AI2_DB_PASSWORD`` at each start. The role only owns schema ``ai2``
(migration v20): it has no grant on business tables, and EXECUTE on the
backend's SECURITY DEFINER functions is withdrawn from PUBLIC so the role
cannot run them either.

``AI2_DB_PASSWORD`` unset or empty: nothing is done (AI2 then keeps its
temporary ``ci`` connection).
"""

from __future__ import annotations

import asyncio
import os
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from contract_intelligence.config.settings import get_settings

ROLE = "ai2"
SCHEMA = "ai2"

_CREATE_ROLE = f"""
DO $$
BEGIN
    CREATE ROLE {ROLE} LOGIN;
EXCEPTION WHEN duplicate_object THEN
    NULL;
END
$$;
"""

# Backend SECURITY DEFINER functions in public, outside any extension.
_SECURITY_DEFINER_FUNCTIONS = """
SELECT p.oid::regprocedure::text
  FROM pg_proc p
 WHERE p.pronamespace = 'public'::regnamespace
   AND p.prosecdef
   AND NOT EXISTS (
       SELECT 1 FROM pg_depend d
        WHERE d.classid = 'pg_proc'::regclass AND d.objid = p.oid AND d.deptype = 'e'
   )
"""


# Objects in schema ai2 another role still owns: AI2 used the backend's ``ci``
# connection before this role existed, so its tables (alembic_version included)
# belong to ``ci``. Owning the schema does not let ai2 read them. Indexes and
# sequences tied to a table follow ALTER TABLE; extension members stay put.
_FOREIGN_OWNED_OBJECTS = f"""
SELECT format('ALTER %s %I.%I OWNER TO {ROLE}',
              CASE c.relkind WHEN 'v' THEN 'VIEW' WHEN 'm' THEN 'MATERIALIZED VIEW'
                             WHEN 'S' THEN 'SEQUENCE' ELSE 'TABLE' END,
              n.nspname, c.relname)
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = '{SCHEMA}'
   AND c.relkind IN ('r', 'p', 'v', 'm', 'S')
   AND c.relowner <> '{ROLE}'::regrole
   AND NOT EXISTS (
       SELECT 1 FROM pg_depend d
        WHERE d.classid = 'pg_class'::regclass AND d.objid = c.oid
          AND (d.deptype = 'e' OR (c.relkind = 'S' AND d.deptype IN ('a', 'i')))
   )
UNION ALL
SELECT format('ALTER TYPE %I.%I OWNER TO {ROLE}', n.nspname, t.typname)
  FROM pg_type t
  JOIN pg_namespace n ON n.oid = t.typnamespace
 WHERE n.nspname = '{SCHEMA}'
   AND t.typtype IN ('e', 'd')
   AND t.typowner <> '{ROLE}'::regrole
   AND NOT EXISTS (
       SELECT 1 FROM pg_depend d
        WHERE d.classid = 'pg_type'::regclass AND d.objid = t.oid AND d.deptype = 'e'
   )
UNION ALL
SELECT format('ALTER ROUTINE %s OWNER TO {ROLE}', p.oid::regprocedure)
  FROM pg_proc p
 WHERE p.pronamespace = '{SCHEMA}'::regnamespace
   AND p.proowner <> '{ROLE}'::regrole
   AND NOT EXISTS (
       SELECT 1 FROM pg_depend d
        WHERE d.classid = 'pg_proc'::regclass AND d.objid = p.oid AND d.deptype = 'e'
   )
"""


async def ensure_ai2_role(connection: AsyncConnection, password: str) -> None:
    """Create the role if missing, then reset its attributes, password and schema."""
    await connection.execute(text(_CREATE_ROLE))
    # Passwords cannot be bound parameters in DDL; format(%L) quotes the literal.
    alter_role = (
        await connection.execute(
            text(
                f"SELECT format('ALTER ROLE {ROLE} LOGIN NOSUPERUSER NOCREATEDB "
                "NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L', CAST(:password AS text))"
            ),
            {"password": password},
        )
    ).scalar_one()
    await connection.execute(text(alter_role))
    await connection.execute(text(f"ALTER ROLE {ROLE} SET search_path = {SCHEMA}, public"))
    await connection.execute(text(f"ALTER SCHEMA {SCHEMA} OWNER TO {ROLE}"))
    for statement in (await connection.execute(text(_FOREIGN_OWNED_OBJECTS))).scalars().all():
        await connection.execute(text(statement))
    functions = (await connection.execute(text(_SECURITY_DEFINER_FUNCTIONS))).scalars().all()
    for function in functions:
        await connection.execute(text(f"REVOKE EXECUTE ON FUNCTION {function} FROM PUBLIC"))


async def _main() -> int:
    password = os.environ.get("AI2_DB_PASSWORD", "")
    if not password:
        print("[ai2-db-role] AI2_DB_PASSWORD not set; skipping the ai2 role")
        return 0
    engine = create_async_engine(get_settings().database_url)
    try:
        async with engine.begin() as connection:
            await ensure_ai2_role(connection, password)
    finally:
        await engine.dispose()
    print(f"[ai2-db-role] role {ROLE} ready (owns schema {SCHEMA})")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
