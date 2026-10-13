"""Verify the browser can load the PDF.js worker as an ES module."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen


def _get(url: str) -> tuple[str, str]:
    with urlopen(Request(url, method="GET"), timeout=5) as response:
        return response.headers.get("Content-Type", ""), response.read().decode(
            "utf-8", errors="ignore"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:5173")
    parser.add_argument(
        "--dist",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "frontend" / "dist",
    )
    args = parser.parse_args()

    worker_names = {
        path.name for path in sorted((args.dist / "assets").glob("pdf.worker*.mjs"))
    }
    if not worker_names:
        try:
            _, html = _get(args.base_url.rstrip("/") + "/")
            scripts = re.findall(r'<script[^>]+src=["\']([^"\']+\.js)["\']', html)
            for script in scripts:
                _, bundle = _get(args.base_url.rstrip("/") + "/" + script.lstrip("/"))
                worker_names.update(
                    re.findall(r"(?:/|assets/)(pdf\.worker[^\"'`]+\.mjs)", bundle)
                )
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL: cannot discover PDF.js worker asset: {exc}", file=sys.stderr)
            return 1
    if not worker_names:
        print("FAIL: no built pdf.worker*.mjs asset found", file=sys.stderr)
        return 1

    errors: list[str] = []
    for worker_name in sorted(worker_names):
        url = f"{args.base_url.rstrip('/')}/assets/{worker_name}"
        try:
            content_type, body = _get(url)
            if "javascript" not in content_type.lower():
                errors.append(f"{worker_name}: Content-Type={content_type!r}")
            elif body.lstrip().startswith("<!doctype html"):
                errors.append(f"{worker_name}: server returned the SPA fallback")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{worker_name}: {exc}")

    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(f"PASS: {len(worker_names)} PDF.js worker asset(s) are served as JavaScript")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
