"""Secret-safe release smoke checks for the local full stack.

The script never prints or persists an access token. Authenticated dossier
checks are reported as NOT_RUN when no token and dossier id are supplied.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Check:
    name: str
    status: str
    detail: str


def get_json(
    url: str,
    token: str | None = None,
    tenant_id: str | None = None,
    accept: str = "application/json",
) -> tuple[int, object]:
    request = urllib.request.Request(url, headers={"Accept": accept})
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    if tenant_id:
        request.add_header("X-Tenant-Id", tenant_id)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            body = response.read().decode("utf-8", errors="replace")
            try:
                return response.status, json.loads(body)
            except json.JSONDecodeError:
                return response.status, body[:200]
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, body[:200]
    except (OSError, urllib.error.URLError) as exc:
        return 0, str(exc)


def tenant_id_from_token(token: str) -> str | None:
    """Read the tenant claim for routing; the backend still verifies the JWT."""

    try:
        segment = token.split(".")[1]
        padded = segment.replace("-", "+").replace("_", "/")
        padded += "=" * ((4 - len(padded) % 4) % 4)
        claims = json.loads(base64.b64decode(padded).decode("utf-8"))
    except (IndexError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    value = claims.get("tenant_id") if isinstance(claims, dict) else None
    return value if isinstance(value, str) and value else None


def run(args: argparse.Namespace) -> dict[str, object]:
    checks: list[Check] = []

    for name, url in (
        ("backend-health", f"{args.backend_url.rstrip('/')}/health"),
        ("ai2-health", f"{args.ai2_url.rstrip('/')}/health"),
        ("frontend-root", args.frontend_url.rstrip('/') + "/"),
    ):
        status, body = get_json(
            url,
            accept="text/html" if name == "frontend-root" else "application/json",
        )
        if name == "frontend-root" and status == 200:
            checks.append(Check(name, "PASS", "frontend returned HTTP 200"))
        elif name != "frontend-root" and status == 200 and isinstance(body, dict):
            checks.append(Check(name, "PASS", str(body.get("status", "ok"))))
        else:
            checks.append(Check(name, "FAIL", f"HTTP {status}: {body}"))

    if not args.token or not args.dossier_id:
        checks.append(
            Check(
                "authenticated-dossier-flow",
                "NOT_RUN",
                "requires --token-stdin and --dossier-id; token is never written to the report",
            )
        )
    else:
        dossier_url = f"{args.backend_url.rstrip('/')}/api/v1/dossiers/{args.dossier_id}"
        status, body = get_json(
            dossier_url,
            args.token,
            tenant_id_from_token(args.token),
        )
        if status == 200:
            checks.append(Check("authenticated-dossier-flow", "PASS", "dossier detail returned"))
        else:
            checks.append(Check("authenticated-dossier-flow", "FAIL", f"HTTP {status}: {body}"))

    return {
        "schema": "vsf/ai2-release-smoke/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checks": [asdict(check) for check in checks],
        "summary": {
            "pass": sum(check.status == "PASS" for check in checks),
            "fail": sum(check.status == "FAIL" for check in checks),
            "not_run": sum(check.status == "NOT_RUN" for check in checks),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend-url", default="http://127.0.0.1:8000")
    parser.add_argument("--ai2-url", default="http://127.0.0.1:8002")
    parser.add_argument("--frontend-url", default="http://127.0.0.1:5173")
    parser.add_argument(
        "--token-stdin",
        action="store_true",
        help="read the bearer token from stdin; never pass it in argv",
    )
    parser.add_argument("--dossier-id")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    args.token = sys.stdin.read().strip() if args.token_stdin else None
    report = run(args)
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 1 if report["summary"]["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
