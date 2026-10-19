"""Write the API reference from the running FastAPI app (docs/ban-giao/03b, 03c).

Reads the routes FastAPI actually serves, so the handover list cannot drift
from the code:

- ``03b-api-endpoints.md``: every endpoint with its method, the roles allowed
  (from ``require_role``), summary and documented status codes;
- ``03c-openapi-backend.json``: the OpenAPI document FastAPI generates.
  Staging/production publish no ``/docs``; this file is the copy for the team.

    cd backend && uv run python scripts/export_api_doc.py ../docs/ban-giao
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

ROLE_LABELS = {"OPERATOR": "Vận hành", "REVIEWER": "Thẩm định", "ADMINISTRATOR": "Quản trị"}
METHOD_ORDER = {"GET": 0, "POST": 1, "PUT": 2, "PATCH": 3, "DELETE": 4}


def _walk(dependant: Dependant) -> list[Dependant]:
    found = [dependant]
    for sub in dependant.dependencies:
        found.extend(_walk(sub))
    return found


def _routes(app: Any) -> list[Any]:
    """APIRoutes, including those behind FastAPI 0.14x's included-router wrappers."""
    found: list[Any] = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            found.append(route)
        elif hasattr(route, "effective_route_contexts"):
            found.extend(
                ctx for ctx in route.effective_route_contexts() if getattr(ctx, "dependant", None)
            )
    return found


def _access(route: Any) -> str:
    """Roles from require_role(...), else whether a signed-in user is needed."""
    roles: set[str] = set()
    signed_in = False
    for dep in _walk(route.dependant):
        call = dep.call
        name = getattr(call, "__name__", "")
        if name == "_role_checker" and call.__closure__:  # type: ignore[union-attr]
            for cell in call.__closure__:  # type: ignore[union-attr]
                value = cell.cell_contents
                if isinstance(value, tuple) and all(isinstance(v, str) for v in value):
                    roles.update(value)
        if name in {"get_current_user", "get_tenant_id"}:
            signed_in = True
    if roles:
        # ADMINISTRATOR always passes require_role (role hierarchy).
        allowed = roles | {"ADMINISTRATOR"}
        ordered = [r for r in ("OPERATOR", "REVIEWER", "ADMINISTRATOR") if r in allowed]
        return ", ".join(ROLE_LABELS[r] for r in ordered)
    if signed_in:
        return "Đã đăng nhập (quyền theo hồ sơ)"
    return "Không cần token"


def _group(path: str) -> str:
    parts = [p for p in path.split("/") if p and not p.startswith("{")]
    if parts[:2] == ["api", "v1"]:
        parts = parts[2:]
    return parts[0] if parts else "(gốc)"


def build(app: Any) -> tuple[str, dict[str, Any]]:
    spec = app.openapi()
    rows: list[tuple[str, str, int, str, str, str, str]] = []
    for route in _routes(app):
        if not route.include_in_schema:
            continue
        op = spec["paths"].get(route.path_format, {})
        for method in sorted(route.methods, key=lambda m: METHOD_ORDER.get(m, 9)):
            detail = op.get(method.lower(), {})
            codes = ", ".join(sorted(detail.get("responses", {}).keys()))
            summary = detail.get("summary") or route.summary or route.name or ""
            summary = summary.replace("|", "\\|")
            rows.append(
                (
                    _group(route.path_format),
                    route.path_format,
                    METHOD_ORDER.get(method, 9),
                    method,
                    _access(route),
                    summary,
                    codes,
                )
            )
    rows.sort(key=lambda r: (r[0], r[1], r[2]))

    out = [
        "# Phụ lục 03b · Danh sách endpoint của backend",
        "",
        "> **Tệp sinh tự động** bởi `backend/scripts/export_api_doc.py` từ chính ứng dụng FastAPI. "
        "Không sửa tay: sửa code rồi chạy lại script.",
        "",
        f"- Phiên bản backend: `{spec['info'].get('version')}`",
        f"- Số endpoint: {len(rows)}",
        "- Cột **Quyền**: vai trò được gọi (Quản trị luôn được). "
        '"Quyền theo hồ sơ" nghĩa là cần đăng nhập, còn được làm gì do ACL '
        "của từng hồ sơ quyết định (chủ hồ sơ, người được chia sẻ, Quản trị).",
        "- Mọi endpoint có token cần header `Authorization: Bearer <access_token>` "
        "và `X-Tenant-Id`.",
        "- Request/response chi tiết: [03c-openapi-backend.json](03c-openapi-backend.json) "
        "(mở bằng Swagger Editor hoặc import vào Postman).",
        "",
    ]
    current = None
    for group, path, _, method, access, summary, codes in rows:
        if group != current:
            out += ["", f"## `{group}`", ""]
            out += ["| Method | Đường dẫn | Quyền | Mô tả | Mã trả về |", "|---|---|---|---|---|"]
            current = group
        out.append(f"| `{method}` | `{path}` | {access} | {summary} | {codes} |")
    return "\n".join(out).rstrip() + "\n", spec


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    from contract_intelligence.main import app

    target = Path(sys.argv[1])
    target.mkdir(parents=True, exist_ok=True)
    markdown, spec = build(app)
    (target / "03b-api-endpoints.md").write_text(markdown, encoding="utf-8", newline="\n")
    (target / "03c-openapi-backend.json").write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"wrote {target}/03b-api-endpoints.md and 03c-openapi-backend.json")


if __name__ == "__main__":
    main()
