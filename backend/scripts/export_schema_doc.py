"""Write the database schema reference (docs/ban-giao/02b-csdl-chi-tiet.md) from a live database.

The handover document must match what the migrations really create, so this
reads PostgreSQL's catalog instead of the ORM: run both migration chains on an
empty database first, then point this script at it.

    docker run -d --rm --name ci-pg-doc -e POSTGRES_USER=ci -e POSTGRES_PASSWORD=ci \\
        -e POSTGRES_DB=contract_intel -p 55434:5432 pgvector/pgvector:pg16
    docker exec ci-pg-doc psql -U ci -d contract_intel -c "CREATE EXTENSION vector"
    cd backend && DATABASE_URL=postgresql+asyncpg://ci:ci@127.0.0.1:55434/contract_intel \\
        uv run alembic upgrade head
    cd ai-service && uv run python -c "from sqlalchemy import create_engine; \\
        from app.db.migrate import migrate; \\
        migrate(create_engine('postgresql+psycopg://ci:ci@127.0.0.1:55434/contract_intel'))"
    cd backend && uv run python scripts/export_schema_doc.py \\
        postgresql://ci:ci@127.0.0.1:55434/contract_intel ../docs/ban-giao/02b-csdl-chi-tiet.md

Only structure is read (tables, columns, keys, indexes, triggers): no rows.
"""

from __future__ import annotations

import asyncio
import sys
from collections import defaultdict
from pathlib import Path

import asyncpg

SCHEMAS = ("public", "ai2")
SCHEMA_TITLES = {
    "public": "Schema `public`: backend (Alembic `backend/alembic/versions`)",
    "ai2": "Schema `ai2`: AI2 (Alembic `ai-service/app/db/migrations`)",
}


async def _rows(cx: asyncpg.Connection, sql: str) -> list[asyncpg.Record]:
    return list(await cx.fetch(sql, list(SCHEMAS)))


async def collect(dsn: str) -> dict[str, object]:
    cx = await asyncpg.connect(dsn)
    try:
        tables = await _rows(
            cx,
            """
            SELECT n.nspname AS schema, c.relname AS name,
                   obj_description(c.oid, 'pg_class') AS comment
              FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE c.relkind IN ('r', 'p') AND n.nspname = ANY($1::text[])
             ORDER BY 1, 2
            """,
        )
        columns = await _rows(
            cx,
            """
            SELECT n.nspname AS schema, c.relname AS table, a.attname AS name,
                   format_type(a.atttypid, a.atttypmod) AS type, a.attnotnull AS not_null,
                   pg_get_expr(d.adbin, d.adrelid) AS default,
                   col_description(c.oid, a.attnum) AS comment
              FROM pg_attribute a
              JOIN pg_class c ON c.oid = a.attrelid
              JOIN pg_namespace n ON n.oid = c.relnamespace
              LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
             WHERE c.relkind IN ('r', 'p') AND n.nspname = ANY($1::text[])
               AND a.attnum > 0 AND NOT a.attisdropped
             ORDER BY 1, 2, a.attnum
            """,
        )
        constraints = await _rows(
            cx,
            """
            SELECT n.nspname AS schema, c.relname AS table, k.conname AS name,
                   k.contype::text AS kind, pg_get_constraintdef(k.oid) AS definition,
                   rn.nspname AS ref_schema, rc.relname AS ref_table
              FROM pg_constraint k
              JOIN pg_class c ON c.oid = k.conrelid
              JOIN pg_namespace n ON n.oid = c.relnamespace
              LEFT JOIN pg_class rc ON rc.oid = k.confrelid
              LEFT JOIN pg_namespace rn ON rn.oid = rc.relnamespace
             WHERE n.nspname = ANY($1::text[])
             ORDER BY 1, 2, k.contype, 3
            """,
        )
        indexes = await _rows(
            cx,
            """
            SELECT i.schemaname AS schema, i.tablename AS table, i.indexname AS name,
                   i.indexdef AS definition
              FROM pg_indexes i
             WHERE i.schemaname = ANY($1::text[])
               AND NOT EXISTS (
                   SELECT 1 FROM pg_constraint k
                    JOIN pg_class ic ON ic.oid = k.conindid
                   WHERE ic.relname = i.indexname)
             ORDER BY 1, 2, 3
            """,
        )
        triggers = await _rows(
            cx,
            """
            SELECT n.nspname AS schema, c.relname AS table, t.tgname AS name,
                   pg_get_triggerdef(t.oid) AS definition
              FROM pg_trigger t
              JOIN pg_class c ON c.oid = t.tgrelid
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE NOT t.tgisinternal AND n.nspname = ANY($1::text[])
             ORDER BY 1, 2, 3
            """,
        )
        versions = {}
        for schema in SCHEMAS:
            try:
                versions[schema] = await cx.fetchval(
                    f"SELECT version_num FROM {schema}.alembic_version"  # noqa: S608 - fixed names
                )
            except asyncpg.UndefinedTableError:
                versions[schema] = None
        server = await cx.fetchval("SHOW server_version")
    finally:
        await cx.close()
    return {
        "tables": tables,
        "columns": columns,
        "constraints": constraints,
        "indexes": indexes,
        "triggers": triggers,
        "versions": versions,
        "server": server,
    }


def _cell(value: object) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def render(data: dict[str, object]) -> str:
    tables: list = data["tables"]  # type: ignore[assignment]
    by_table: dict[tuple[str, str], dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for kind in ("columns", "constraints", "indexes", "triggers"):
        for row in data[kind]:  # type: ignore[attr-defined]
            by_table[(row["schema"], row["table"])][kind].append(row)

    versions: dict = data["versions"]  # type: ignore[assignment]
    out: list[str] = [
        "# Phụ lục 02b · Chi tiết schema cơ sở dữ liệu",
        "",
        "> **Tệp sinh tự động** bởi `backend/scripts/export_schema_doc.py` từ PostgreSQL đã chạy "
        "hết migration. Không sửa tay: sửa migration rồi chạy lại script (cách chạy ở đầu script).",
        "",
        f"- PostgreSQL: `{data['server']}`",
        f"- Backend (`public.alembic_version`): `{versions.get('public')}`",
        f"- AI2 (`ai2.alembic_version`): `{versions.get('ai2')}`",
        f"- Số bảng: `public` {sum(t['schema'] == 'public' for t in tables)}, "
        f"`ai2` {sum(t['schema'] == 'ai2' for t in tables)} (kể cả `alembic_version`)",
        "",
        "Ký hiệu cột **Null**: `NOT NULL` hoặc để trống (cho phép NULL). "
        "Ràng buộc: `PK` khoá chính, `FK` khoá ngoại, `UQ` duy nhất, `CK` kiểm tra.",
        "",
    ]
    for schema in SCHEMAS:
        names = [t for t in tables if t["schema"] == schema]
        out += [f"## {SCHEMA_TITLES[schema]}", ""]
        out += ["| Bảng | Số cột | Khoá ngoại tới |", "|---|---|---|"]
        for t in names:
            parts = by_table[(schema, t["name"])]
            refs = sorted({c["ref_table"] for c in parts["constraints"] if c["kind"] == "f"})
            out.append(
                f"| [`{t['name']}`](#{schema}-{t['name']}) | {len(parts['columns'])} | "
                f"{', '.join(f'`{r}`' for r in refs)} |"
            )
        out.append("")

        edges = [
            c
            for t in names
            for c in by_table[(schema, t["name"])]["constraints"]
            if c["kind"] == "f" and c["ref_table"]
        ]
        if edges:
            out += [
                f"### Sơ đồ khoá ngoại (`{schema}`)",
                "",
                "```mermaid",
                "erDiagram",
            ]
            seen = set()
            for c in edges:
                key = (c["ref_table"], c["table"], c["name"])
                if key in seen:
                    continue
                seen.add(key)
                out.append(f'    {c["ref_table"]} ||--o{{ {c["table"]} : "{c["name"]}"')
            out += ["```", ""]

        for t in names:
            parts = by_table[(schema, t["name"])]
            out += [f'### <a id="{schema}-{t["name"]}"></a>`{schema}.{t["name"]}`', ""]
            if t["comment"]:
                out += [_cell(t["comment"]), ""]
            out += ["| Cột | Kiểu | Null | Mặc định | Ghi chú |", "|---|---|---|---|---|"]
            for col in parts["columns"]:
                out.append(
                    f"| `{col['name']}` | `{_cell(col['type'])}` | "
                    f"{'NOT NULL' if col['not_null'] else ''} | "
                    f"{('`' + _cell(col['default']) + '`') if col['default'] else ''} | "
                    f"{_cell(col['comment'])} |"
                )
            kinds = {"p": "PK", "f": "FK", "u": "UQ", "c": "CK", "x": "EXCLUDE"}
            if parts["constraints"]:
                out += ["", "Ràng buộc:", ""]
                out += [
                    f"- {kinds.get(c['kind'], c['kind'])} `{c['name']}`: `{_cell(c['definition'])}`"
                    for c in parts["constraints"]
                ]
            if parts["indexes"]:
                out += ["", "Index:", ""]
                out += [f"- `{_cell(i['definition'])}`" for i in parts["indexes"]]
            if parts["triggers"]:
                out += ["", "Trigger:", ""]
                out += [f"- `{_cell(tr['definition'])}`" for tr in parts["triggers"]]
            out.append("")
    return "\n".join(out).rstrip() + "\n"


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    dsn, target = sys.argv[1], Path(sys.argv[2])
    data = asyncio.run(collect(dsn))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(data), encoding="utf-8", newline="\n")
    print(f"wrote {target} ({len(data['tables'])} tables)")  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
