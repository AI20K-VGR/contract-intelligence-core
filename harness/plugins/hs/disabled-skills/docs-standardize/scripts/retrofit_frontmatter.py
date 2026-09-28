#!/usr/bin/env python3
"""ONE-SHOT: tiêm frontmatter vào doc đang thiếu. Idempotent (có FM → bỏ qua).

Nguồn dữ liệu:
  - top-docs: bảng hand-map TOP (id/type/tier/parent/owner).
  - module README: _migration/module-attrs.json (tier/axis/backbone/spine/module_class) + infer capabilities (scan features/ agents/).
  - parts: _index/modules.yaml parts[] (id=key, owner, home→parent).
  - module config README (ocr-template-config/...): type=config owner=PTSP.

KHÔNG tạo nội dung — chỉ chèn block frontmatter. version 0.1.0 status draft mặc định.
Run: python3 <this> [--docs docs]
"""
import argparse
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[6]

# yaml_io (the shared YAML reader/writer, harness/scripts/) is not on sys.path
# by default from a skill's scripts/ dir -- add it before importing.
_HARNESS_SCRIPTS = str(REPO / "harness" / "scripts")
if _HARNESS_SCRIPTS not in sys.path:
    sys.path.append(_HARNESS_SCRIPTS)
import yaml_io

# Dùng docslib.parse để kiểm FM — tránh nhầm HR `---` đầu file là frontmatter
sys.path.insert(0, str(REPO / "harness" / "plugins" / "hs" / "skills" / "_docslib"))
from docslib.frontmatter import parse as _parse_fm  # noqa: E402

TOP = {
    "overview/platform-overview.md": ("overview.platform", "overview", "L0", None, "PTNT"),
    "overview/executive-brief.md": ("overview.executive-brief", "overview", "L0", "overview.platform", "PTNT"),
    "architecture/responsibility-boundary.md": ("arch.responsibility-boundary", "sad", "L1", "overview.platform", "PTNT"),
    "architecture/c4.md": ("arch.c4", "sad", "L1", "overview.platform", "PTNT"),
    "architecture/platform-layers.md": ("arch.platform-layers", "sad", "L1", "overview.platform", "PTNT"),
    "architecture/clusters.md": ("arch.clusters", "sad", "L1", "arch.platform-layers", "PTNT"),
    "architecture/README.md": ("arch.index", "index", "L1", "overview.platform", "PTNT"),
    "quality/nfr.md": ("quality.nfr", "quality", "L1x", "overview.platform", "PTNT"),
    "quality/security.md": ("quality.security", "quality", "L1x", "overview.platform", "PTNT"),
    "governance/data-privacy.md": ("gov.data-privacy", "governance", "platform", "overview.platform", "PTNT"),
    "operations/kt50-delivery-view.md": ("ops.kt50-delivery-view", "operations", "platform", "overview.platform", "PTNT"),
    "operations/pilot-ar-hstt-delivery-plan.md": ("ops.pilot-ar-hstt-delivery-plan", "operations", "platform", "overview.platform", "PTNT"),
    "guides/dealer-claim-pilot-flow.md": ("guide.dealer-claim-pilot-flow", "guide", "L2", "overview.platform", "PTNT"),
    "modules/README.md": ("modules.index", "index", "L2", "overview.platform", "PTNT"),
}

def _fm_block(meta: dict) -> str:
    return "---\n" + yaml_io.safe_dump(meta, allow_unicode=True, sort_keys=False).rstrip() + "\n---\n\n"


def _inject(path: pathlib.Path, meta: dict) -> str:
    # Dùng docslib.parse để phát hiện frontmatter đúng (tránh nhầm HR `---` đầu file)
    doc = _parse_fm(path)
    if doc.has_frontmatter():
        return f"skip (đã có FM) {path.name}"
    text = path.read_text(encoding="utf-8")
    path.write_text(_fm_block(meta) + text, encoding="utf-8")
    return f"FM+ {path.name}"


def _ordered(id_, type_, tier, parent, owner, **extra) -> dict:
    m = {"id": id_, "type": type_, "tier": tier, "status": "draft",
         "owner": owner, "version": "0.1.0"}
    if parent:
        m["parent"] = parent
    m.update(extra)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default=str(REPO / "docs"))
    a = ap.parse_args()
    docs = pathlib.Path(a.docs)
    log = []

    # 1) top docs
    for rel, (i, t, tier, par, own) in TOP.items():
        p = docs / rel
        if p.is_file():
            log.append(_inject(p, _ordered(i, t, tier, par, own)))

    # 2) parts (từ _index)
    idx = yaml_io.safe_load((docs / "_index" / "modules.yaml").read_text(encoding="utf-8"))
    for pid, pinfo in (idx.get("parts") or {}).items():
        p = docs / pinfo["at"]
        if p.is_file():
            log.append(_inject(p, _ordered(pid, "part", "L2", pinfo["home"], pinfo.get("owner", "PTNT"))))

    # 3) module READMEs + module config readmes
    attrs = json.loads((docs / "_migration" / "module-attrs.json").read_text(encoding="utf-8"))
    mroot = docs / "modules"
    for sub in sorted(mroot.glob("*/mod-*")):
        m = re.match(r"(mod-\d+)", sub.name)
        if not m:
            continue
        mid = m.group(1)
        at = attrs.get(mid, {})
        # infer capabilities
        feats = sorted(d.name for d in (sub / "features").glob("*")) if (sub / "features").is_dir() else []
        agents = sorted(d.name for d in (sub / "agents").glob("*")) if (sub / "agents").is_dir() else []
        caps = {"exposes_api": False, "has_workers": False, "tenant_config": False,
                "has_features": feats, "owns_agents": agents}
        extra = {"module_class": at.get("module_class")}
        for k in ("axis", "backbone", "spine"):
            if at.get(k):
                extra[k] = at[k]
        extra["capabilities"] = caps
        readme = sub / "README.md"
        if readme.is_file():
            log.append(_inject(readme, _ordered(mid, "module-readme", "L2",
                                                "arch.responsibility-boundary", "PTNT", **extra)))
        # config recipe README (vd ocr-template-config/README.md) → type config, owner PTSP
        for cr in sub.glob("*/README.md"):
            if cr.parent.name == "parts":
                continue
            cid = f"{mid}.config.{cr.parent.name}"
            log.append(_inject(cr, _ordered(cid, "config", "L2", mid, "PTSP")))

    for line in log:
        print(line)
    print(f"\ntotal touched: {sum(1 for l in log if l.startswith('FM+'))}, "
          f"skipped: {sum(1 for l in log if l.startswith('skip'))}")


if __name__ == "__main__":
    main()
