#!/usr/bin/env python3
"""ONE-SHOT migration: đẩy graph fact từ _index/modules.yaml → frontmatter part/README.

Frontmatter-as-SSOT: leaf file tự giữ fact, modules.yaml trở thành DERIVED.
  - part-level fact (layer/note/universal_spine) → frontmatter của part doc (`at`).
  - reuse edge (link from:<module> uses:<part>) → `reuses:[{part,why}]` trên module README
    (khớp shape link thật module→part; gom theo `from`).
config_parts KHÔNG có doc home → KHÔNG migrate (giữ hand-authored trong modules.yaml/source riêng).

Idempotent: chạy lại không đổi gì (trả 0). Sau migrate, `graph.derive_modules_yaml` tái dựng
modules.yaml lossless — verify parity trước khi xoá fact tay.

Run: python3 <this> [--docs DIR] [--check]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# yaml_io (the shared YAML reader/writer, harness/scripts/) is not on sys.path
# by default from a skill's scripts/ dir -- add it before importing.
_HARNESS_SCRIPTS = str(Path(__file__).resolve().parents[5] / "scripts")
if _HARNESS_SCRIPTS not in sys.path:
    sys.path.append(_HARNESS_SCRIPTS)
import yaml_io

_DOCSLIB = Path(__file__).resolve().parents[2] / "_docslib"
sys.path.insert(0, str(_DOCSLIB))

from docslib import frontmatter as fm          # noqa: E402
from docslib.index import load_model           # noqa: E402

_PART_FIELDS = ("layer", "note", "universal_spine")


def _readme_by_module(docs_root: Path) -> dict:
    """{module-id → README path}. Key cả frontmatter-id LẪN dạng `mod-NN` từ tên dir, vì
    `links.from`/`parts.home` thường dùng `mod-NN` còn README có thể đặt frontmatter id khác →
    tránh tra trượt làm MẤT edge."""
    out = {}
    for m in load_model(docs_root).modules:
        rp = docs_root / m.dir / "README.md"
        if rp.is_file():
            out[m.id] = rp
            mm = re.search(r"(mod-\d+)", Path(m.dir).name)
            if mm:
                out.setdefault(mm.group(1), rp)
    return out


def unresolved_targets(docs_root: str | Path) -> list:
    """`links.from` không có README đích → edge sẽ MẤT khi migrate. Báo để --check fail."""
    docs_root = Path(docs_root)
    mods = yaml_io.safe_load((docs_root / "_index" / "modules.yaml").read_text(encoding="utf-8")) or {}
    readmes = _readme_by_module(docs_root)
    froms = {ln["from"] for ln in (mods.get("links", []) or [])
             if isinstance(ln, dict) and ln.get("from")}
    return sorted(f for f in froms if f not in readmes)


def migrate(docs_root: str | Path, dry_run: bool = False) -> int:
    """Đẩy fact vào frontmatter. Trả số trường (sẽ) ghi (0 = đã đồng bộ/idempotent).

    dry_run=True: chỉ ĐẾM fact chưa migrate, KHÔNG ghi file. Doc frontmatter hỏng → bỏ qua
    (KHÔNG wipe; merge_frontmatter cũng tự từ chối).
    """
    docs_root = Path(docs_root)
    mods = yaml_io.safe_load((docs_root / "_index" / "modules.yaml").read_text(encoding="utf-8")) or {}
    parts = mods.get("parts", {}) or {}
    links = mods.get("links", []) or []
    moved = 0

    # 1) part-level fact → part doc frontmatter
    for pid, p in parts.items():
        if not isinstance(p, dict) or not p.get("at"):
            continue
        at = docs_root / p["at"]
        try:
            if not at.resolve().is_relative_to(docs_root.resolve()):
                continue  # at thoát docs-root → KHÔNG ghi (chống path-traversal)
        except (OSError, ValueError):
            continue
        if not at.is_file():
            continue
        doc = fm.parse(at)
        if doc.raw_error:          # frontmatter hỏng → bỏ qua, không wipe
            continue
        fields = {k: p[k] for k in _PART_FIELDS if k in p and doc.meta.get(k) != p[k]}
        if fields:
            if not dry_run:
                fm.merge_frontmatter(at, fields)
            moved += len(fields)

    # 2) reuse edge → module README `reuses` (gom theo from-module)
    by_mod: dict = {}
    for ln in links:
        if isinstance(ln, dict) and ln.get("from") and ln.get("uses"):
            by_mod.setdefault(ln["from"], []).append({"part": ln["uses"], "why": ln.get("why", "")})
    readmes = _readme_by_module(docs_root)
    for mid, reuses in by_mod.items():
        rp = readmes.get(mid)
        if not rp:
            continue
        doc = fm.parse(rp)
        if doc.raw_error:
            continue
        if doc.meta.get("reuses") != reuses:
            if not dry_run:
                fm.merge_frontmatter(rp, {"reuses": reuses})
            moved += 1
    return moved


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Migrate graph facts modules.yaml → frontmatter.")
    ap.add_argument("--docs", default=None, help="docs root (mặc định: <repo>/docs)")
    ap.add_argument("--check", action="store_true", help="chỉ báo còn fact chưa migrate, KHÔNG ghi")
    args = ap.parse_args(argv)
    docs_root = Path(args.docs) if args.docs else Path(__file__).resolve().parents[6] / "docs"
    if not (docs_root / "_index" / "modules.yaml").is_file():
        print(f"[migrate] không thấy {docs_root}/_index/modules.yaml — bỏ qua", file=sys.stderr)
        return 0
    unresolved = unresolved_targets(docs_root)
    if args.check:
        remaining = migrate(docs_root, dry_run=True)
        if unresolved:
            print(f"[migrate] --check: {len(unresolved)} link.from KHÔNG có README đích "
                  f"(edge sẽ mất): {', '.join(unresolved)}")
        if remaining:
            print(f"[migrate] --check: còn {remaining} fact CHƯA migrate (chạy không --check để ghi).")
        if remaining or unresolved:
            return 1
        print("[migrate] --check: đã đồng bộ, không còn fact tay.")
        return 0
    if unresolved:
        # KHÔNG âm thầm bỏ edge: cảnh báo to (operator sửa id/README trước khi xoá links tay).
        print(f"[migrate] CẢNH BÁO: {len(unresolved)} link.from không có README đích — edge KHÔNG được "
              f"ghi vào frontmatter, ĐỪNG xoá `links:` tay tới khi sửa: {', '.join(unresolved)}", file=sys.stderr)
    moved = migrate(docs_root)
    print(f"[migrate] đã đẩy {moved} field vào frontmatter (0 = đã đồng bộ).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
