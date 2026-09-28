#!/usr/bin/env python3
"""ONE-SHOT migration: docs/modules/module-map.yaml → docs/_index/*.yaml.

Tách:
  graph (parts/config_parts/links)  → _index/modules.yaml
  cross-cut (foundations/safety)    → _index/foundations.yaml, _index/safety.yaml
  display (order/band/bands)        → _index/showcase.yaml
  intrinsic per-module (tier/axis/backbone/spine) → _migration/module-attrs.json
                                       (dùng để bơm frontmatter README)

`parts[].at` đổi prefix: core/... → modules/core/...  (relative docs_root).
Idempotent: ghi đè _index/*. KHÔNG đụng module-map.yaml gốc (bước sau mới xoá).

Run: python3 <this> [--docs DIR]
"""
import argparse
import importlib.util
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve()
REPO = HERE.parents[6]                       # .../skills/docs-standardize/scripts/<f> → repo

# yaml_io (the shared YAML reader/writer, harness/scripts/) is not on sys.path
# by default from a skill's scripts/ dir -- add it before importing.
_HARNESS_SCRIPTS = str(REPO / "harness" / "scripts")
if _HARNESS_SCRIPTS not in sys.path:
    sys.path.append(_HARNESS_SCRIPTS)
import yaml_io
DEFAULT_DOCS = REPO / "docs"


def _load_old_map(build_modules_py, map_path):
    """Tái dùng load_map của build_modules.py (xử đúng comment inline `}#`)."""
    spec = importlib.util.spec_from_file_location("build_modules", build_modules_py)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.load_map(map_path.read_text(encoding="utf-8"))


def _dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# GENERATED bởi migrate_module_map.py. Nguồn cũ: docs/modules/module-map.yaml.\n"
        + yaml_io.safe_dump(obj, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8")
    print("wrote", path.relative_to(REPO))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default=str(DEFAULT_DOCS))
    a = ap.parse_args()
    docs = pathlib.Path(a.docs)
    old_map = docs / "modules" / "module-map.yaml"
    build_py = docs / "modules" / "build_modules.py"
    if not old_map.is_file():
        sys.exit(f"không thấy {old_map}")
    if not build_py.is_file():
        sys.exit(f"không thấy {build_py}")

    modules, parts, links, foundations, config_parts, safety = _load_old_map(build_py, old_map)

    # ---- parts: đổi prefix at + ép kiểu layer giữ nguyên ----
    parts_out = {}
    for pid, p in parts.items():
        q = dict(p)
        at = q.get("at", "")
        if at and not at.startswith("modules/"):
            q["at"] = "modules/" + at
        parts_out[pid] = q

    idx = docs / "_index"
    _dump(idx / "modules.yaml", {"parts": parts_out, "config_parts": config_parts, "links": links})
    _dump(idx / "foundations.yaml", {"foundations": foundations})
    _dump(idx / "safety.yaml", {"safety": safety})

    # ---- showcase.yaml: display (order/band) + bands legend + sections ----
    disp_modules = [{"id": m["id"], "order": int(m.get("order", 0)), "band": m.get("band")}
                    for m in sorted(modules, key=lambda x: int(x.get("order", 0)))]
    bands_legend = [
        {"id": "ingest", "vi": "Thu thập", "en": "Ingest"},
        {"id": "extract", "vi": "Bóc tách", "en": "Extract"},
        {"id": "decide", "vi": "Quyết định", "en": "Decide"},
        {"id": "orchestrate", "vi": "Điều phối (Spine)", "en": "Orchestrate (Spine)"},
        {"id": "write", "vi": "Ghi sổ", "en": "Write"},
        {"id": "assist", "vi": "Trợ lý", "en": "Assist"},
        {"id": "data", "vi": "Dữ liệu", "en": "Data"},
    ]
    sections = [
        {"id": "overview", "order": 1, "detail": "full"},
        {"id": "architecture", "order": 2, "detail": "full"},
        {"id": "quality", "order": 3, "detail": "full"},
        {"id": "governance", "order": 4, "detail": "summary"},
        {"id": "modules", "order": 5, "detail": "full"},
        {"id": "operations", "order": 6, "detail": "summary"},
        {"id": "guides", "order": 7, "detail": "summary"},
        {"id": "glossary", "order": 8, "detail": "full"},
    ]
    _dump(idx / "showcase.yaml",
          {"modules": disp_modules, "bands": bands_legend, "sections": sections})

    # ---- sidecar intrinsic attrs (frontmatter README) ----
    attrs = {}
    for m in modules:
        a2 = {"tier": "L2", "module_class": m.get("tier")}  # altitude=L2; class core/extended
        for k in ("axis", "backbone", "spine"):
            if m.get(k):
                a2[k] = m[k]
        attrs[m["id"]] = a2
    mig = docs / "_migration"
    mig.mkdir(parents=True, exist_ok=True)
    (mig / "module-attrs.json").write_text(json.dumps(attrs, ensure_ascii=False, indent=2) + "\n",
                                           encoding="utf-8")
    print("wrote", (mig / "module-attrs.json").relative_to(REPO))
    print(f"OK — {len(modules)} module · {len(parts_out)} part · {len(config_parts)} config-part · "
          f"{len(links)} link · {len(foundations)} foundation · {len(safety)} safety")


if __name__ == "__main__":
    main()
