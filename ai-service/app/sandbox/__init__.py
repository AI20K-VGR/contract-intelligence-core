from __future__ import annotations

import ast
from decimal import Decimal, InvalidOperation
from typing import Any

FORBIDDEN_NODES = (
    ast.Import,
    ast.ImportFrom,
    ast.Global,
    ast.Nonlocal,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.Raise,
    ast.Delete,
    ast.ClassDef,
    ast.Lambda,
    ast.Yield,
    ast.YieldFrom,
    ast.Await,
)


class SandboxError(Exception):
    pass


def _assert_safe(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if isinstance(node, FORBIDDEN_NODES):
            raise SandboxError(f"forbidden syntax: {type(node).__name__}")
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in {
                "eval",
                "exec",
                "open",
                "compile",
                "__import__",
                "input",
                "print",
            }:
                raise SandboxError(f"forbidden call: {node.func.id}")
            if isinstance(node.func, ast.Attribute) and node.func.attr.startswith("_"):
                raise SandboxError("forbidden dunder/attr call")
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            raise SandboxError("forbidden attribute")
        if isinstance(node, ast.Name) and node.id in {"__builtins__", "builtins", "os", "sys", "subprocess"}:
            raise SandboxError(f"forbidden name: {node.id}")


def run_user_code(code: str, rows: list[list[str | None]], header: list[str]) -> dict[str, Any]:
    """Execute generated table code against provided rows only."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise SandboxError(str(exc)) from exc
    _assert_safe(tree)

    def cell(r: int, c: int) -> str | None:
        if r < 0 or r >= len(rows) or c < 0 or c >= len(rows[r]):
            return None
        return rows[r][c]

    def decimal(value: str | None) -> Decimal | None:
        if value is None:
            return None
        text = str(value).strip().replace(" ", "").replace(",", "")
        if text in {"", "-", "—", "N/A", "n/a"}:
            return None
        try:
            return Decimal(text)
        except InvalidOperation:
            # Mixed text/numeric columns are valid OCR output. Preserve the
            # raw cell and let the caller mark it for review.
            return None

    env: dict[str, Any] = {
        "rows": rows,
        "header": header,
        "cell": cell,
        "Decimal": Decimal,
        "decimal": decimal,
        "result": None,
    }
    compiled = compile(tree, "<sandbox>", "exec")
    exec(compiled, {"__builtins__": {"len": len, "range": range, "enumerate": enumerate, "str": str, "int": int, "list": list, "dict": dict}}, env)
    out = env.get("result")
    if out is None:
        raise SandboxError("code must assign `result`")
    return {"rows_out": out, "errors": []}
