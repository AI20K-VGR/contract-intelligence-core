"""Robustness guards: load_manifest và graph.validate không được crash trên input méo.

NHÓM 1 — decidable QA findings:
  - load_manifest với asset_slots là list (không phải dict) → không raise, asset_slots rỗng
  - asset_slots.js = 'three' (string scalar) → không thành ['t','h','r','e','e']
  - graph.validate trên Model méo (parts/links/safety/foundations non-dict entries) → không raise
"""
from pathlib import Path

from docslib.findings import Findings
from docslib import manifest as M
from docslib.index import Model
from docslib import graph


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_model(docs_root: Path) -> Model:
    """Model tối thiểu — không có module thật (tránh validate module-band)."""
    return Model(
        docs_root=docs_root,
        docs=[],
        modules=[],
        parts={},
        config_parts={},
        links=[],
        foundations=[],
        safety=[],
        showcase={},
    )


# ---------------------------------------------------------------------------
# Test load_manifest: asset_slots non-dict
# ---------------------------------------------------------------------------

def test_load_manifest_asset_slots_list_does_not_raise():
    """asset_slots là list (bị méo) → load_manifest không raise, trả dict rỗng các slot."""
    raw = {"pages": [{"key": "hub"}], "asset_slots": ["oops"]}
    man = M.load_manifest(raw)
    # Không raise; asset_slots phải là dict với list rỗng (non-dict input bị guard)
    assert isinstance(man.asset_slots, dict)
    assert man.asset_slots["js"] == []
    assert man.asset_slots["css"] == []
    assert man.asset_slots["vendor"] == []


def test_load_manifest_asset_slots_scalar_string_does_not_explode():
    """asset_slots.js = 'three' (string scalar) → _as_list trả [] (không thành ký tự)."""
    raw = {"pages": [{"key": "hub"}], "asset_slots": {"js": "three", "css": [], "vendor": []}}
    man = M.load_manifest(raw)
    # 'three' không phải list/tuple → phải ra [] chứ không phải ['t','h','r','e','e']
    assert man.asset_slots["js"] == [], (
        f"Expected [], got {man.asset_slots['js']!r} — _as_list bị coerce sai"
    )


def test_load_manifest_asset_slots_none_slot():
    """asset_slots.js = None → [] (không crash)."""
    raw = {"pages": [{"key": "hub"}], "asset_slots": {"js": None}}
    man = M.load_manifest(raw)
    assert man.asset_slots["js"] == []


def test_load_manifest_category_pages_scalar():
    """categories[].pages = 'bad' (scalar) → _as_list trả [] không crash."""
    raw = {
        "pages": [{"key": "hub"}],
        "categories": [{"key": "ov", "vi": "", "en": "", "pages": "bad"}],
        "asset_slots": {},
    }
    man = M.load_manifest(raw)
    assert man.categories[0].pages == [], (
        f"Expected [], got {man.categories[0].pages!r}"
    )


def test_load_manifest_category_pages_tuple():
    """categories[].pages = ('a', 'b') (tuple) → list ['a', 'b'] (OK)."""
    raw = {
        "pages": [{"key": "hub"}],
        "categories": [{"key": "ov", "vi": "", "en": "", "pages": ("a", "b")}],
        "asset_slots": {},
    }
    man = M.load_manifest(raw)
    assert man.categories[0].pages == ["a", "b"]


# ---------------------------------------------------------------------------
# Test graph.validate: Model méo (non-dict entries)
# ---------------------------------------------------------------------------

def test_validate_non_dict_part_does_not_raise(tmp_path):
    """parts dict có value không phải dict → validate không raise, ghi finding."""
    model = _minimal_model(tmp_path)
    # Thêm entry méo vào parts
    model.parts["bad-part"] = "not-a-dict"
    f = Findings()
    graph.validate(model, f, frontmatter_check=False)
    # Không raise; phải có finding về bad-part
    errors = [i for i in f.by_severity("error") if "bad-part" in i.msg or "bad-part" in i.where]
    assert errors, "Cần finding cho part non-dict"


def test_validate_non_dict_link_does_not_raise(tmp_path):
    """links list có entry không phải dict → validate không raise, ghi finding."""
    model = _minimal_model(tmp_path)
    model.links = ["not-a-dict", 42]
    f = Findings()
    graph.validate(model, f, frontmatter_check=False)
    # Không raise; phải có finding về link-shape-bad
    errors = [i for i in f.by_severity("error") if "link-shape-bad" in i.code]
    assert errors, "Cần finding link-shape-bad cho link non-dict"


def test_validate_non_dict_safety_does_not_raise(tmp_path):
    """safety list có entry không phải dict → validate không raise, ghi finding."""
    model = _minimal_model(tmp_path)
    model.safety = ["not-a-dict"]
    f = Findings()
    graph.validate(model, f, frontmatter_check=False)
    # Không raise
    errors = [i for i in f.by_severity("error") if "safety-shape-bad" in i.code]
    assert errors, "Cần finding safety-shape-bad cho safety non-dict"


def test_validate_non_dict_foundation_does_not_raise(tmp_path):
    """foundations list có entry không phải dict → validate không raise, ghi finding."""
    model = _minimal_model(tmp_path)
    model.foundations = [99]
    f = Findings()
    graph.validate(model, f, frontmatter_check=False)
    errors = [i for i in f.by_severity("error") if "foundation-shape-bad" in i.code]
    assert errors, "Cần finding foundation-shape-bad cho foundation non-dict"


def test_validate_non_dict_config_part_does_not_raise(tmp_path):
    """config_parts dict có value không phải dict → validate không raise, ghi finding."""
    model = _minimal_model(tmp_path)
    model.config_parts["bad-cp"] = ["not", "a", "dict"]
    f = Findings()
    graph.validate(model, f, frontmatter_check=False)
    errors = [i for i in f.by_severity("error") if "configpart-shape-bad" in i.code]
    assert errors, "Cần finding configpart-shape-bad cho config_part non-dict"


def test_validate_mixed_valid_invalid_links_does_not_raise(tmp_path):
    """links có cả entry hợp lệ lẫn không phải dict → validate không crash, tiếp tục."""
    model = _minimal_model(tmp_path)
    model.links = [
        "bad-string",
        {"from": "nonexistent", "uses": "nonexistent-part"},
    ]
    f = Findings()
    graph.validate(model, f, frontmatter_check=False)
    # Không raise — phải có ít nhất 2 finding (1 shape-bad + 1 link-bad-from hoặc link-dangling)
    assert len(f.by_severity("error")) >= 2
