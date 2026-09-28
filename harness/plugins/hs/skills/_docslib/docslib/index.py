"""Load Model — hợp nhất SSOT: frontmatter mỗi file + _index/*.yaml mỏng.

Phân tách (quyết định 1+5):
  - Intrinsic per-module (tier/axis/backbone/spine/capabilities) → README frontmatter.
  - Graph cross-module (parts/config_parts/links) → _index/modules.yaml.
  - Cross-cut (foundations/safety) → _index/{foundations,safety}.yaml.
  - Display (order/band/sections/detail) → _index/showcase.yaml.
Model = object trung tâm cho cả standardize (validate) lẫn build (generate).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml_io

from .discover import discover
from .frontmatter import Doc


def _load_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = yaml_io.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml_io.YAMLError:
        # YAML hỏng → {} thay vì crash gate/build (mirror graph._safe_yaml); validate sẽ bắt gap.
        return {}
    return data if isinstance(data, dict) else {}


@dataclass
class Module:
    id: str
    dir: str                         # rel docs_root, vd modules/core/mod-01-document-intake
    klass: str                       # core|extended (suy từ dir)
    order: int = 0                   # showcase.yaml
    band: str | None = None          # showcase.yaml
    tier: str | None = None          # frontmatter
    axis: str | None = None          # frontmatter (optional)
    backbone: bool = False
    spine: bool = False
    capabilities: dict = field(default_factory=dict)
    readme: Doc | None = None


@dataclass
class Model:
    docs_root: Path
    docs: list[Doc] = field(default_factory=list)        # mọi md ZONE-2
    modules: list[Module] = field(default_factory=list)
    parts: dict = field(default_factory=dict)
    config_parts: dict = field(default_factory=dict)
    links: list = field(default_factory=list)
    foundations: list = field(default_factory=list)
    safety: list = field(default_factory=list)
    showcase: dict = field(default_factory=dict)         # raw showcase.yaml (legacy gộp — back-compat)
    bands: dict = field(default_factory=dict)            # _index/bands.yaml (design taxonomy)
    present: dict = field(default_factory=dict)          # _present/* (presentation thuần)
    legacy_showcase: bool = False                        # True khi shim đọc từ showcase.yaml gộp (chưa migrate)

    @property
    def module_ids(self) -> set:
        return {m.id for m in self.modules}

    def module(self, mid) -> Module | None:
        return next((m for m in self.modules if m.id == mid), None)

    def docs_by_id(self) -> dict:
        out = {}
        for d in self.docs:
            if d.id:
                out.setdefault(d.id, []).append(d)
        return out


def _klass_of(rel_dir: str) -> str:
    return "extended" if "/extended/" in f"/{rel_dir}/" else "core"


def _load_present(present_dir: Path) -> dict:
    """Gộp mọi `*.yaml` trong `_present/` thành 1 dict presentation.

    Top-level scalar: file sau đè file trước (sort tên). `modules` (list per-module) nối lại.
    """
    if not present_dir.is_dir():
        return {}
    merged: dict = {}
    for f in sorted(present_dir.glob("*.yaml")):
        try:
            data = yaml_io.safe_load(f.read_text(encoding="utf-8")) or {}
        except yaml_io.YAMLError:
            continue  # file _present hỏng → bỏ qua, không crash (validate sẽ bắt gap)
        if not isinstance(data, dict):
            continue
        for k, v in data.items():
            if k == "modules" and isinstance(v, list):
                merged.setdefault("modules", [])
                merged["modules"].extend(x for x in v if isinstance(x, dict))
            else:
                merged[k] = v
    return merged


def _module_band_map(bands: dict) -> dict:
    """{module-id → band} từ bands.yaml `modules: [{id, band}]`."""
    out = {}
    for d in (bands.get("modules", []) or []):
        if isinstance(d, dict) and d.get("id"):
            out[d["id"]] = d.get("band")
    return out


def _module_order_map(present: dict) -> dict:
    """{module-id → order} từ _present `modules: [{id, order}]`."""
    out = {}
    for d in (present.get("modules", []) or []):
        if isinstance(d, dict) and d.get("id"):
            out[d["id"]] = d.get("order", 0)
    return out


def _shim_from_showcase(showcase: dict) -> tuple[dict, dict]:
    """Legacy back-compat: tách showcase.yaml gộp → (bands_dict, present_dict).

    `bands`(taxonomy) + per-module `band` → bands_dict; per-module `order` + mọi key
    presentation top-level còn lại (text_fix/sections/pages/...) → present_dict.
    """
    sc_mods = [m for m in (showcase.get("modules", []) or []) if isinstance(m, dict) and m.get("id")]
    bands_dict = {
        "bands": showcase.get("bands", []),
        "modules": [{"id": m["id"], "band": m.get("band")} for m in sc_mods],
    }
    present_dict = {k: v for k, v in showcase.items() if k not in ("bands", "modules")}
    present_dict["modules"] = [{"id": m["id"], "order": m.get("order", 0)} for m in sc_mods]
    return bands_dict, present_dict


def load_model(docs_root: str | Path) -> Model:
    docs_root = Path(docs_root)
    idx = docs_root / "_index"
    modules_yaml = _load_yaml(idx / "modules.yaml")
    showcase = _load_yaml(idx / "showcase.yaml")
    foundations = _load_yaml(idx / "foundations.yaml").get("foundations", [])
    safety = _load_yaml(idx / "safety.yaml").get("safety", [])

    # Tách design taxonomy (bands.yaml) ⟂ presentation (_present/) — nguồn mới.
    # Shim back-compat: chỉ có legacy showcase.yaml gộp → split-read tại chỗ + cờ deprecation.
    bands = _load_yaml(idx / "bands.yaml")
    present = _load_present(docs_root / "_present")
    legacy_showcase = False
    if not bands and not present and showcase:
        bands, present = _shim_from_showcase(showcase)
        legacy_showcase = True
    band_map = _module_band_map(bands)
    order_map = _module_order_map(present)

    raw_parts = modules_yaml.get("parts", {})
    raw_config_parts = modules_yaml.get("config_parts", {})
    raw_links = modules_yaml.get("links", [])
    # Phòng thủ: ép về đúng kiểu (YAML méo có thể trả về list/None thay vì dict)
    parts = raw_parts if isinstance(raw_parts, dict) else {}
    config_parts = raw_config_parts if isinstance(raw_config_parts, dict) else {}
    links = raw_links if isinstance(raw_links, list) else []

    docs = discover(docs_root)
    readme_by_dir = {}
    for d in docs:
        if d.path.name == "README.md" and "/modules/" in f"/{d.rel}":
            readme_by_dir[str(d.path.parent.relative_to(docs_root))] = d

    # khám phá module = thư mục modules/*/mod-*/ có README
    modules: list[Module] = []
    mroot = docs_root / "modules"
    if mroot.is_dir():
        for sub in sorted(mroot.glob("*/mod-*")):
            if not sub.is_dir():
                continue
            rel_dir = str(sub.relative_to(docs_root))
            readme = readme_by_dir.get(rel_dir)
            meta = readme.meta if readme else {}
            # id ưu tiên: frontmatter → regex mod-NN → tên thư mục
            if meta.get("id"):
                mid = meta["id"]
            else:
                import re
                rm = re.match(r"(mod-\d+)", sub.name)
                mid = rm.group(1) if rm else sub.name
            modules.append(Module(
                id=mid, dir=rel_dir, klass=_klass_of(rel_dir),
                order=int(order_map.get(mid, 0) or 0), band=band_map.get(mid),
                tier=meta.get("tier"), axis=meta.get("axis"),
                backbone=bool(meta.get("backbone")), spine=bool(meta.get("spine")),
                capabilities=meta.get("capabilities", {}) or {}, readme=readme,
            ))
    modules.sort(key=lambda m: (m.order or 999, m.id))

    return Model(docs_root=docs_root, docs=docs, modules=modules, parts=parts,
                 config_parts=config_parts, links=links, foundations=foundations,
                 safety=safety, showcase=showcase, bands=bands, present=present,
                 legacy_showcase=legacy_showcase)
