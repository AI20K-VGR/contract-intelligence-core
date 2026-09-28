#!/usr/bin/env python3
"""Liệt kê required-set còn thiếu theo tờ khai capabilities của module(s). Exit 0.

  python3 capability_required.py [--docs docs] [--module mod-07] [--json]

Đọc README frontmatter (capabilities) → suy ra doc bắt buộc → so file thực tế.
KHÔNG sinh file (đó là việc scaffold_doc.py); chỉ báo cáo gap.
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "_docslib"))
from docslib import load_model  # noqa: E402
from docslib.capabilities import required_docs  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[6]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default=str(REPO / "docs"))
    ap.add_argument("--module")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    model = load_model(a.docs)
    docs_root = pathlib.Path(a.docs)
    report = {}
    for m in model.modules:
        if a.module and m.id != a.module:
            continue
        req = required_docs(m.capabilities)
        missing = [r for r in req if not (docs_root / m.dir / r).is_file()]
        report[m.id] = {"dir": m.dir, "capabilities": m.capabilities,
                        "required": req, "missing": missing}
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    for mid, r in report.items():
        flag = "" if not r["capabilities"] else f" {list(r['capabilities'])}"
        print(f"{mid}{flag}")
        if r["missing"]:
            for x in r["missing"]:
                print(f"  thiếu: {x}")
        else:
            print("  ✓ đủ required-set")


if __name__ == "__main__":
    main()
