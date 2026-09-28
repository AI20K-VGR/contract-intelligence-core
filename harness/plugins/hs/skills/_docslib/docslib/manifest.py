"""Manifest = site-structure của showcase (pages/categories/asset_slots/footer/theme).

Nguồn: docs/_index/showcase.yaml. Trước P1 các bảng này là literal Python trong
docs/showcase/build.py (PAGES/CATEGORIES/JS_PARTS/CSS_PARTS/VENDOR/FOOTER_PAGES);
P1 nâng thành DATA + validate (tìm gap: source/asset thiếu, @key@ dangling, ref page lạ).

load_manifest(showcase_dict) -> Manifest        (parse, không chạm đĩa)
validate_manifest(manifest, docs_root, findings) (kiểm tồn tại file + ref toàn vẹn)

KHÔNG phán nội dung — chỉ cấu trúc (đồng pha với docs-standardize).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml_io

# @key@ link protocol (khớp docs/showcase/build.py _LINK_RE)
_ATKEY = re.compile(r"@([a-z0-9-]+)@")
# slot đặc biệt: @generated = chỗ chèn data-JS sinh bởi generate_showcase_data (không phải file tĩnh)
SPECIAL_SLOTS = {"@generated"}
# slot → (thư mục dưới docs/showcase/assets, đuôi thêm vào tên)
_ASSET_LOC = {
    "js": (("showcase", "assets", "js"), ".js"),
    "css": (("showcase", "assets", "css"), ".css"),
    "vendor": (("showcase", "assets", "lib"), ""),  # tên vendor đã gồm .js
}


@dataclass
class Page:
    key: str
    vi: str = ""
    en: str = ""
    source: str | None = None       # md SSOT (relative docs_root)
    partial: str | None = None      # partial html (dưới showcase/partials)
    category: str | None = None
    accent: str = ""
    empty: bool = False             # page rỗng (placeholder) — không cần source/partial
    title: str = ""                 # <title> element text cho trang


@dataclass
class Category:
    key: str
    vi: str = ""
    en: str = ""
    pages: list = field(default_factory=list)


@dataclass
class Manifest:
    theme: str = ""
    pages: list = field(default_factory=list)
    categories: list = field(default_factory=list)
    asset_slots: dict = field(default_factory=dict)   # {js:[...], css:[...], vendor:[...]}
    footer_pages: list = field(default_factory=list)  # list of dict {key, vi|None, en|None}

    def page_keys(self) -> set:
        return {p.key for p in self.pages}

    def footer_refs(self) -> list:
        """Trả [(key, vi_label, en_label)] — vi/en None thì lấy từ page tương ứng."""
        page_map = {p.key: p for p in self.pages}
        result = []
        for entry in self.footer_pages:
            key = entry["key"]
            vi_label = entry.get("vi")
            en_label = entry.get("en")
            if vi_label is None or en_label is None:
                page = page_map.get(key)
                if page:
                    if vi_label is None:
                        vi_label = page.vi
                    if en_label is None:
                        en_label = page.en
            result.append((key, vi_label or "", en_label or ""))
        return result


def _normalize_footer_entry(entry) -> dict:
    """Chuẩn hoá entry footer_pages: str → {key, vi:None, en:None}; dict → {key, vi|None, en|None}."""
    if isinstance(entry, str):
        return {"key": entry, "vi": None, "en": None}
    if isinstance(entry, dict):
        return {"key": str(entry.get("key", "")), "vi": entry.get("vi"), "en": entry.get("en")}
    return {"key": str(entry), "vi": None, "en": None}


def _as_list(v) -> list:
    """Coerce v thành list an toàn: list/tuple → list; mọi scalar/None → [].
    Không dùng list(str) để tránh list('three') → ['t','h','r','e','e'].
    """
    if isinstance(v, (list, tuple)):
        return list(v)
    return []


def load_manifest(showcase: dict) -> Manifest:
    """Parse block manifest từ dict showcase.yaml. Không chạm đĩa, không validate."""
    showcase = showcase or {}
    pages = [
        Page(
            key=str(p.get("key", "")),
            vi=p.get("vi", ""), en=p.get("en", ""),
            source=p.get("source"), partial=p.get("partial"),
            category=p.get("category"), accent=p.get("accent", ""),
            empty=bool(p.get("empty", False)),
            title=p.get("title", ""),
        )
        for p in (showcase.get("pages") or []) if isinstance(p, dict)
    ]
    cats = [
        Category(key=str(c.get("key", "")), vi=c.get("vi", ""), en=c.get("en", ""),
                 pages=_as_list(c.get("pages")))
        for c in (showcase.get("categories") or []) if isinstance(c, dict)
    ]
    raw_slots = showcase.get("asset_slots") or {}
    if not isinstance(raw_slots, dict):
        raw_slots = {}
    asset_slots = {k: _as_list(raw_slots.get(k)) for k in ("js", "css", "vendor")}
    raw_footer = showcase.get("footer_pages") or []
    footer_pages = [_normalize_footer_entry(e) for e in raw_footer]
    return Manifest(
        theme=showcase.get("theme", ""),
        pages=pages, categories=cats, asset_slots=asset_slots,
        footer_pages=footer_pages,
    )


def load_manifest_from_yaml(path: str | Path) -> Manifest:
    path = Path(path)
    data = yaml_io.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else {}
    return load_manifest(data or {})


def _scan_atkeys(text: str) -> set:
    return set(_ATKEY.findall(text or ""))


def _load_schema() -> dict | None:
    """Load showcase-manifest.json từ harness/schemas/ relative to this file.
    Trả None nếu không tìm thấy (graceful degradation).
    """
    schema_path = Path(__file__).parents[5] / "schemas" / "showcase-manifest.json"
    if schema_path.is_file():
        try:
            return json.loads(schema_path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def validate_manifest(manifest: Manifest, docs_root: str | Path, findings, *,
                      check_assets: bool = True) -> None:
    """Invariant cấu trúc manifest. ERROR = chặn build.

    check_assets=False để Phase trước theme-split (asset có thể nằm ở overlay/default-theme).
    """
    docs_root = Path(docs_root)
    keys = manifest.page_keys()
    cat_keys = {c.key for c in manifest.categories}
    partials_dir = docs_root / "showcase" / "partials"

    # 0. JSON Schema validation (showcase block từ _index/showcase.yaml)
    showcase_yaml = docs_root / "_index" / "showcase.yaml"
    if showcase_yaml.is_file():
        try:
            raw_showcase = yaml_io.safe_load(showcase_yaml.read_text(encoding="utf-8")) or {}
        except Exception:
            raw_showcase = {}
        # Validate chỉ block site-structure (loại trừ key khác như modules/bands)
        _SHOWCASE_KEYS = {"theme", "pages", "categories", "asset_slots", "footer_pages"}
        showcase_block = {k: raw_showcase[k] for k in _SHOWCASE_KEYS if k in raw_showcase}
        schema = _load_schema()
        if schema is not None:
            try:
                import jsonschema
                v = jsonschema.Draft202012Validator(schema)
                for err in v.iter_errors(showcase_block):
                    path_str = ".".join(str(s) for s in err.absolute_path) or "showcase"
                    findings.error("MAN_SCHEMA", path_str, err.message)
            except Exception as exc:
                findings.warn("MAN_SCHEMA_SKIP", "showcase.yaml",
                              f"jsonschema validate bỏ qua (lỗi import/runtime): {exc}")

    # 0b. MAN_NO_HUB: 'hub' phải có trong page keys (engine build hard-assume page 'hub')
    if "hub" not in keys:
        findings.error("MAN_NO_HUB", "showcase.yaml",
                       "page 'hub' không có trong manifest — ssg_engine.build yêu cầu page hub")

    # 1. mỗi page: source|partial|empty; file tồn tại; title; category two-way
    # category → pages set (để kiểm two-way)
    cat_page_sets: dict[str, set] = {c.key: set(c.pages) for c in manifest.categories}
    for p in manifest.pages:
        if not p.key:
            findings.error("MAN_PAGE_NOKEY", "showcase.yaml", "page thiếu 'key'")
            continue
        if not (p.source or p.partial or p.empty):
            findings.error("MAN_PAGE_NOSRC", f"page:{p.key}",
                           f"page '{p.key}' không có source/partial cũng không empty:true")
        if p.source:
            sp = docs_root / p.source
            if not sp.is_file():
                findings.error("MAN_SRC_MISSING", f"page:{p.key}",
                               f"source '{p.source}' không tồn tại")
        if p.partial:
            pp = partials_dir / p.partial
            if not pp.is_file():
                findings.error("MAN_PARTIAL_MISSING", f"page:{p.key}",
                               f"partial '{p.partial}' không tồn tại")
        if p.category and p.category not in cat_keys:
            findings.error("MAN_PAGE_CAT", f"page:{p.key}",
                           f"page '{p.key}' category '{p.category}' không có trong categories")
        # MAN_CAT_MISMATCH: page có category=C nhưng C.pages không chứa page.key (two-way)
        if p.category and p.category in cat_page_sets:
            if p.key not in cat_page_sets[p.category]:
                findings.error("MAN_CAT_MISMATCH", f"page:{p.key}",
                               f"page '{p.key}' khai category='{p.category}' "
                               f"nhưng category '{p.category}'.pages không liệt kê page này")
        # MAN_TITLE_EMPTY: page non-empty thiếu title
        if not p.empty and not p.title:
            findings.warn("MAN_TITLE_EMPTY", f"page:{p.key}",
                          f"page '{p.key}' không có title (nên thêm cho <title> HTML)")

    # 2. categories[].pages ⊆ page keys
    for c in manifest.categories:
        for k in c.pages:
            if k not in keys:
                findings.error("MAN_CAT_GHOST", f"category:{c.key}",
                               f"category '{c.key}' trỏ page '{k}' không tồn tại")

    # 3. footer_pages ⊆ page keys (entries chuẩn hoá thành dict {key, vi, en})
    for entry in manifest.footer_pages:
        k = entry["key"] if isinstance(entry, dict) else str(entry)
        if k not in keys:
            findings.error("MAN_FOOTER_GHOST", "footer_pages",
                           f"footer_pages trỏ page '{k}' không tồn tại")

    # 4. asset_slots: file tồn tại (bỏ @generated + slot đặc biệt)
    if check_assets:
        for slot, (subdir, ext) in _ASSET_LOC.items():
            base = docs_root.joinpath(*subdir)
            for name in manifest.asset_slots.get(slot, []):
                if name in SPECIAL_SLOTS:
                    continue
                fp = base / f"{name}{ext}"
                if not fp.is_file():
                    findings.error("MAN_ASSET_MISSING", f"asset_slots.{slot}",
                                   f"asset '{name}{ext}' không tồn tại ({base.name}/)")

    # 5. @key@ trong partials + sources phải resolve về page tồn tại
    texts = []
    for p in manifest.pages:
        if p.partial and (partials_dir / p.partial).is_file():
            texts.append((partials_dir / p.partial).read_text(encoding="utf-8"))
        if p.source and (docs_root / p.source).is_file():
            texts.append((docs_root / p.source).read_text(encoding="utf-8"))
    for t in texts:
        for k in _scan_atkeys(t):
            if k not in keys:
                findings.error("MAN_ATKEY_DANGLING", "@key@",
                               f"link @{k}@ trỏ page không tồn tại")
