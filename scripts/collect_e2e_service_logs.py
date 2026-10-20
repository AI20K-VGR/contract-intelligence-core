"""Collect a secret-safe, cross-service log receipt for one E2E run.

The collector intentionally reads Docker stdout rather than application data.
It normalizes Backend/AI2 lines, performs a frontend HTTP smoke check, and can
optionally ingest the same receipt through the operator log API.  It never
prints or stores bearer tokens, API keys, or passwords.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ID_RE = re.compile(
    r"(?P<kind>dossier|run|job|trace|request)(?:_id)?[=: ]+(?P<value>[A-Za-z0-9_-]+)"
    r"|(?P<prefix>dos|run|job|qtr|req)_[A-Za-z0-9]+"
)
_SECRET_RE = re.compile(
    r"(?i)(?:bearer\s+|api[_-]?key\s*[=:]\s*|(?:password|passwd|secret)\s*[=:]\s*|sk-[a-z0-9_-]{8,})[^\s,;]*"
)
_LEVEL_RE = re.compile(r"\b(DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL)\b", re.IGNORECASE)


def _redact(text: str) -> str:
    return _SECRET_RE.sub("[REDACTED]", text)


def _service_for_line(line: str) -> str:
    lowered = line.casefold()
    if "ai1-worker" in lowered or "ai1." in lowered:
        return "ai1"
    if "ai2-service" in lowered or "ai2." in lowered:
        return "ai2"
    if "frontend" in lowered or "vite" in lowered:
        return "frontend"
    return "backend"


def _ids(line: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for match in _ID_RE.finditer(line):
        if match.group("kind"):
            found[match.group("kind")] = match.group("value")
        elif match.group("prefix"):
            prefix = match.group("prefix")
            found[{"dos": "dossier", "qtr": "trace"}.get(prefix, prefix)] = match.group(0)
    return found


def normalize_line(line: str, *, source: str = "docker") -> dict[str, Any]:
    safe = _redact(line.strip())
    level_match = _LEVEL_RE.search(safe)
    level = level_match.group(1).upper() if level_match else "INFO"
    ids = _ids(safe)
    return {
        "service": _service_for_line(safe),
        "source": source,
        "level": "WARNING" if level == "WARN" else level,
        "event": "e2e.log.line",
        "message": safe[:4000],
        "dossier_id": ids.get("dossier"),
        "run_id": ids.get("run"),
        "job_id": ids.get("job"),
        "trace_id": ids.get("trace"),
        "request_id": ids.get("request"),
        "occurred_at": datetime.now(UTC).isoformat(),
        "payload": {"raw_prefix": safe[:240]},
    }


def docker_logs(project: str, since: str, compose_file: str | None = None) -> list[str]:
    command = ["docker", "compose", "--project-name", project]
    if compose_file:
        command.extend(["--file", compose_file])
    command.extend(
        [
            "logs",
            "--no-color",
            "--since",
            since,
            "backend",
            "backend-worker",
            "ai1-worker",
            "ai2-service",
        ]
    )
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return [line for line in completed.stdout.splitlines() if line.strip()]


def frontend_smoke(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "vsf-e2e-log-collector/1"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return {
                "service": "frontend",
                "source": "http-smoke",
                "level": "INFO",
                "event": "frontend.http_smoke",
                "message": f"GET {url} -> {response.status}",
                "occurred_at": datetime.now(UTC).isoformat(),
                "payload": {"url": url, "status_code": response.status},
            }
    except (OSError, urllib.error.URLError) as exc:
        return {
            "service": "frontend",
            "source": "http-smoke",
            "level": "ERROR",
            "event": "frontend.http_smoke",
            "message": f"GET {url} failed: {type(exc).__name__}",
            "occurred_at": datetime.now(UTC).isoformat(),
            "payload": {"url": url, "error_type": type(exc).__name__},
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default="contract-intelligence-stack")
    parser.add_argument("--compose-file", help="Compose file used to collect service logs")
    parser.add_argument("--since", default="30m")
    parser.add_argument("--frontend-url", default="http://localhost:5173/")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    events = [normalize_line(line) for line in docker_logs(args.project, args.since, args.compose_file)]
    events.append(frontend_smoke(args.frontend_url))
    report = {
        "schema_version": "vsf.e2e.service-log-receipt.v1",
        "project": args.project,
        "since": args.since,
        "collected_at": datetime.now(UTC).isoformat(),
        "counts": {
            service: sum(1 for event in events if event.get("service") == service)
            for service in ("backend", "ai1", "ai2", "frontend")
        },
        "error_count": sum(1 for event in events if event.get("level") in {"ERROR", "CRITICAL"}),
        "events": events,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "counts": report["counts"], "error_count": report["error_count"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
