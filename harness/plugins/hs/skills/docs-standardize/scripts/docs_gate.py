#!/usr/bin/env python3
"""GATE (lớp 2) — đọc artifact docs-check.json, exit 2 nếu có finding severity=error.

  python3 docs_gate.py [--artifact harness/state/docs-check.json] [--fresh]

--fresh: chạy lại check_docs trước khi gate (đảm bảo artifact mới).
Tách biệt analyzer: gate KHÔNG validate lại logic, chỉ đọc số → quyết.
"""
import argparse
import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[6]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact", default=str(REPO / "harness" / "state" / "docs-check.json"))
    ap.add_argument("--docs", default=str(REPO / "docs"))
    ap.add_argument("--fresh", action="store_true")
    a = ap.parse_args()
    if a.fresh:
        subprocess.run([sys.executable, str(pathlib.Path(__file__).with_name("check_docs.py")),
                        "--docs", a.docs, "--artifact", a.artifact, "--quiet"], check=True)
    art = pathlib.Path(a.artifact)
    if not art.is_file():
        sys.exit(f"GATE: thiếu artifact {art} — chạy check_docs.py trước (hoặc --fresh)")
    data = json.loads(art.read_text(encoding="utf-8"))
    c = data.get("counts", {})
    errs = [f for f in data.get("findings", []) if f["severity"] == "error"]
    if errs:
        print(f"DOCS GATE: BLOCKED — {len(errs)} error")
        for f in errs[:50]:
            print(f"  ✗ [{f['code']}] {f['where']}: {f['msg']}")
        sys.exit(2)
    print(f"DOCS GATE: PASS (warn={c.get('warn', 0)} info={c.get('info', 0)})")


if __name__ == "__main__":
    main()
