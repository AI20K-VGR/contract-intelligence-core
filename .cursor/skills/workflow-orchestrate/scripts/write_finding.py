#!/usr/bin/env python3
"""Early-write one finding to a run's refs dir — append-only, one file per group.

A spawned agent's output lives only in its return value until the orchestrator
consolidates; a stalled or oversized consolidation loses it. This helper lets a
step flush a finding to disk the moment it lands, grouped so a batch accumulates
into `<base>/<run-id>/<group>.md` instead of one file per finding.

Append-only: never rewrites an existing finding, only adds a section. Emits the
path as JSON so the caller can cite it.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def resolve_base(refs_base: str, product: bool) -> str:
    return "docs/product/_refs" if product else refs_base.rstrip("/")


def main() -> None:
    ap = argparse.ArgumentParser(description="Append one finding to a run's group file.")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--group", required=True, help="group key -> <group>.md")
    ap.add_argument("--title", required=True)
    ap.add_argument("--body", default=None, help="finding body (else read stdin)")
    ap.add_argument("--refs-base", default="plans/reports")
    ap.add_argument("--product", action="store_true")
    ap.add_argument("--ts", default=None, help="override timestamp (tests); default = now UTC")
    args = ap.parse_args()

    body = args.body if args.body is not None else sys.stdin.read()
    ts = args.ts or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    base = resolve_base(args.refs_base, args.product)
    path = Path(base) / args.run_id / f"{args.group}.md"
    path.parent.mkdir(parents=True, exist_ok=True)

    appended = path.exists()
    header = "" if appended else f"# {args.run_id} — {args.group}\n\n"
    section = f"## {args.title}\n\n_{ts}_\n\n{body.rstrip()}\n\n"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(header + section)

    json.dump({"path": str(path), "group": args.group, "appended": appended},
              sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
