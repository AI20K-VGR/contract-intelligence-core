"""Safety contract: live rollback must not destroy AI2 state or diagnostics."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = (
    ROOT / "alembic/versions/v20__ai2_schema.py",
    ROOT / "alembic/versions/v21__tenant_lexicon.py",
    ROOT / "alembic/versions/v22__reprocess_idempotency.py",
    ROOT / "alembic/versions/v23__service_logs_and_purge_fix.py",
)
FORBIDDEN = {
    "execute",
    "drop_column",
    "drop_constraint",
    "drop_table",
    "drop_schema",
    "drop_index",
}


def _downgrade_calls(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "downgrade")
    calls: set[str] = set()
    for node in ast.walk(function):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if isinstance(node.func.value, ast.Name) and node.func.value.id == "op":
            calls.add(node.func.attr)
        elif isinstance(node.func.value, ast.Name) and node.func.value.id == "batch":
            calls.add(node.func.attr)
    return calls


def test_ai2_related_downgrades_are_non_destructive():
    for path in MIGRATIONS:
        assert not (_downgrade_calls(path) & FORBIDDEN), path.name
