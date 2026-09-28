#!/usr/bin/env python3
"""Sinh skeleton doc từ template. {{token}}→giá trị/ TBD. KHÔNG ghi đè file có nội dung.

Hai chế độ:
  1) Đơn lẻ:  scaffold_doc.py --type module-design --out docs/modules/.../design.md \
               --set id=mod-07.design --set title="..." [--force]
  2) Module:  scaffold_doc.py --module mod-07 --auto         # sinh MỌI required còn thiếu

Nguyên tắc cứng: chỉ stub (frontmatter + heading + `> TBD`). Người viết nội dung thiết kế.
"""
import argparse
import datetime
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "_docslib"))
from docslib import load_model  # noqa: E402
from docslib.capabilities import required_docs  # noqa: E402

HERE = pathlib.Path(__file__).resolve()
REPO = HERE.parents[6]
TEMPLATES = HERE.parents[1] / "templates"

FILE_TYPE = {
    "README.md": "module-readme", "design.md": "module-design", "api.md": "api",
    "workers.md": "worker", "config.md": "config", "techstack.md": "techstack",
    "guide.md": "guide", "spec.md": "feature-spec", "flow.md": "feature-spec",
    "agent.md": "agent-spec", "model-card.md": "model-card", "eval.md": "eval",
    "SYSTEM.md": "prompt",
}


def _render(template_text: str, values: dict) -> str:
    """Thay {{k}} bằng values[k]; token không có giá trị → 'TBD'."""
    def sub(m):
        k = m.group(1).strip()
        return str(values.get(k, "TBD"))
    return re.sub(r"\{\{([^}]+)\}\}", sub, template_text)


def _defaults(values: dict) -> dict:
    v = {"status": "draft", "version": "0.1.0", "owner": "PTNT",
         "date": datetime.date.today().isoformat(), "title": "TBD", "parent": ""}
    v.update({k: val for k, val in values.items() if val is not None})
    return v


def scaffold(doc_type: str, out: pathlib.Path, values: dict, force=False) -> str:
    tpl = TEMPLATES / f"{doc_type}.md"
    if not tpl.is_file():
        return f"SKIP {out} — thiếu template {doc_type}.md"
    if out.exists() and out.stat().st_size > 0 and not force:
        return f"KEEP {out} — đã có nội dung (no-clobber)"
    values = _defaults({**values, "type": doc_type})
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_render(tpl.read_text(encoding="utf-8"), values), encoding="utf-8")
    return f"WROTE {out}"


def _auto_id(mid: str, rel: str) -> str:
    """rel (vd 'agents/x/model-card.md') → id dot-path dưới module."""
    rel = rel[:-3] if rel.endswith(".md") else rel
    parts = rel.split("/")
    if parts == ["README"]:
        return mid
    if parts[0] == "features" and len(parts) >= 2:
        tail = ".".join(parts[1:])
        return f"{mid}.feature.{tail}"
    if parts[0] == "agents" and len(parts) >= 2:
        tail = ".".join(parts[1:]).replace("prompt.SYSTEM", "prompt")
        return f"{mid}.agent.{tail}"
    return f"{mid}.{parts[-1]}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--type")
    ap.add_argument("--out")
    ap.add_argument("--module")
    ap.add_argument("--auto", action="store_true")
    ap.add_argument("--docs", default=str(REPO / "docs"))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--set", action="append", default=[], metavar="k=v")
    a = ap.parse_args()
    # Validate mỗi --set phải có dấu '=' (tránh ValueError thô khi split)
    for kv in a.set:
        if "=" not in kv:
            sys.exit(f"--set phải có dạng key=value, nhận được: '{kv}'")
    values = dict(kv.split("=", 1) for kv in a.set)

    if a.module and a.auto:
        model = load_model(a.docs)
        m = model.module(a.module)
        if not m:
            sys.exit(f"không thấy module {a.module}")
        docs_root = pathlib.Path(a.docs)
        for rel in required_docs(m.capabilities):
            base = pathlib.Path(rel).name
            dt = FILE_TYPE.get(base)
            if not dt:
                print(f"SKIP {rel} — không map được type"); continue
            out = docs_root / m.dir / rel
            vid = _auto_id(m.id, rel)
            owner = "PTSP" if dt == "config" else "PTNT"
            print(scaffold(dt, out, {"id": vid, "owner": owner, "parent": m.id,
                                     "title": f"{m.id.upper()} · {base}"}, a.force))
        return

    if not (a.type and a.out):
        sys.exit("cần --type + --out (đơn lẻ) hoặc --module + --auto")
    print(scaffold(a.type, pathlib.Path(a.out), values, a.force))


if __name__ == "__main__":
    main()
