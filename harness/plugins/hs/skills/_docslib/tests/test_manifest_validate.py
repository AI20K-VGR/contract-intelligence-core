"""P1 — manifest schema + validate. TDD đỏ→xanh.

Manifest = site-structure (pages/categories/asset_slots/footer_pages/theme) trong
docs/_index/showcase.yaml. validate_manifest tìm gap: source/asset thiếu, @key@ dangling,
category/footer trỏ page lạ. LESSONS L1: round-trip non-default mỗi field.
"""
import textwrap

from docslib.findings import Findings
from docslib import manifest as M


def _docs(tmp_path, *, pages_yaml, partials=None, sources=None, assets=None):
    """Dựng docs tree tối thiểu: _index/showcase.yaml + partials/sources/assets."""
    d = tmp_path / "docs"
    (d / "_index").mkdir(parents=True)
    (d / "_index" / "showcase.yaml").write_text(pages_yaml, encoding="utf-8")
    sc = d / "showcase"
    (sc / "partials").mkdir(parents=True)
    (sc / "assets" / "js").mkdir(parents=True)
    (sc / "assets" / "css").mkdir(parents=True)
    (sc / "assets" / "lib").mkdir(parents=True)
    for name, body in (partials or {}).items():
        (sc / "partials" / name).write_text(body, encoding="utf-8")
    for rel, body in (sources or {}).items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    for rel in (assets or []):
        p = sc / "assets" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("/* x */", encoding="utf-8")
    return d


_GOOD = textwrap.dedent("""\
    theme: aurora-3d
    pages:
      - {key: hub, vi: Tổng quan, en: Overview, partial: hub.html, category: overview, accent: var(--ptnt), title: "Hub — tổng quan"}
      - {key: c4, vi: C4, en: C4, source: architecture/c4.md, category: design, accent: var(--ptnt), title: "C4 — kiến trúc"}
    categories:
      - {key: overview, vi: Tổng quan, en: Overview, pages: [hub]}
      - {key: design, vi: Thiết kế, en: Design, pages: [c4]}
    asset_slots:
      js: [01-core, "@generated", 09-search]
      css: [01-base]
      vendor: [three.min.js]
    footer_pages: [hub, c4]
""")


def _good_tree(tmp_path):
    return _docs(
        tmp_path,
        pages_yaml=_GOOD,
        partials={"hub.html": '<a href="@c4@">x</a>'},
        sources={"architecture/c4.md": "# C4\n"},
        assets=["js/01-core.js", "js/09-search.js", "css/01-base.css", "lib/three.min.js"],
    )


def test_happy_path_zero_findings(tmp_path):
    docs = _good_tree(tmp_path)
    man = M.load_manifest_from_yaml(docs / "_index" / "showcase.yaml")
    f = Findings()
    M.validate_manifest(man, docs, f)
    assert not f.has_errors(), [i.msg for i in f.by_severity("error")]


def test_page_source_missing_is_error(tmp_path):
    docs = _good_tree(tmp_path)
    (docs / "architecture" / "c4.md").unlink()
    man = M.load_manifest_from_yaml(docs / "_index" / "showcase.yaml")
    f = Findings()
    M.validate_manifest(man, docs, f)
    assert f.has_errors()
    assert any("c4.md" in i.msg for i in f.by_severity("error"))


def test_asset_slot_file_missing_is_error(tmp_path):
    docs = _good_tree(tmp_path)
    (docs / "showcase" / "assets" / "js" / "09-search.js").unlink()
    man = M.load_manifest_from_yaml(docs / "_index" / "showcase.yaml")
    f = Findings()
    M.validate_manifest(man, docs, f)
    assert any("09-search" in i.msg for i in f.by_severity("error"))


def test_dangling_atkey_link_is_error(tmp_path):
    # partial trỏ @nope@ không có trong pages
    docs = _docs(
        tmp_path,
        pages_yaml=_GOOD,
        partials={"hub.html": '<a href="@nope@">x</a>'},
        sources={"architecture/c4.md": "# C4\n"},
        assets=["js/01-core.js", "js/09-search.js", "css/01-base.css", "lib/three.min.js"],
    )
    man = M.load_manifest_from_yaml(docs / "_index" / "showcase.yaml")
    f = Findings()
    M.validate_manifest(man, docs, f)
    assert any("nope" in i.msg for i in f.by_severity("error"))


def test_category_unknown_page_is_error(tmp_path):
    bad = _GOOD.replace("pages: [c4]", "pages: [c4, ghost]")
    docs = _docs(tmp_path, pages_yaml=bad,
                 partials={"hub.html": "x"},
                 sources={"architecture/c4.md": "# C4\n"},
                 assets=["js/01-core.js", "js/09-search.js", "css/01-base.css", "lib/three.min.js"])
    man = M.load_manifest_from_yaml(docs / "_index" / "showcase.yaml")
    f = Findings()
    M.validate_manifest(man, docs, f)
    assert any("ghost" in i.msg for i in f.by_severity("error"))


def test_footer_unknown_page_is_error(tmp_path):
    bad = _GOOD.replace("footer_pages: [hub, c4]", "footer_pages: [hub, ghost]")
    docs = _docs(tmp_path, pages_yaml=bad,
                 partials={"hub.html": "x"},
                 sources={"architecture/c4.md": "# C4\n"},
                 assets=["js/01-core.js", "js/09-search.js", "css/01-base.css", "lib/three.min.js"])
    man = M.load_manifest_from_yaml(docs / "_index" / "showcase.yaml")
    f = Findings()
    M.validate_manifest(man, docs, f)
    assert any("ghost" in i.msg for i in f.by_severity("error"))


def test_roundtrip_non_default_fields(tmp_path):
    """LESSONS L1: mọi field đọc lại đúng giá trị NON-DEFAULT (loader không drop)."""
    docs = _good_tree(tmp_path)
    man = M.load_manifest_from_yaml(docs / "_index" / "showcase.yaml")
    assert man.theme == "aurora-3d"                       # non-default theme
    assert [p.key for p in man.pages] == ["hub", "c4"]
    assert man.pages[1].source == "architecture/c4.md"    # source path carried
    assert man.pages[0].partial == "hub.html"             # partial carried
    assert man.pages[1].accent == "var(--ptnt)"
    assert man.asset_slots["js"] == ["01-core", "@generated", "09-search"]  # order preserved
    assert man.asset_slots["vendor"] == ["three.min.js"]
    # footer_pages chuẩn hoá thành list dict {key, vi, en}
    assert man.footer_pages == [{"key": "hub", "vi": None, "en": None},
                                 {"key": "c4", "vi": None, "en": None}]
    assert {c.key for c in man.categories} == {"overview", "design"}
    # title round-trip (NHÓM 2)
    assert man.pages[0].title == "Hub — tổng quan"
    assert man.pages[1].title == "C4 — kiến trúc"


def test_footer_override_label(tmp_path):
    """footer_pages dict {key, vi, en} override label; str vẫn fallback về page label."""
    yaml_with_override = textwrap.dedent("""\
        theme: aurora-3d
        pages:
          - {key: hub, vi: Tổng quan, en: Overview, partial: hub.html, category: overview, accent: var(--ptnt)}
          - {key: c4, vi: C4, en: C4, source: architecture/c4.md, category: design, accent: var(--ptnt)}
        categories:
          - {key: overview, vi: Tổng quan, en: Overview, pages: [hub]}
          - {key: design, vi: Thiết kế, en: Design, pages: [c4]}
        asset_slots:
          js: [01-core, "@generated", 09-search]
          css: [01-base]
          vendor: [three.min.js]
        footer_pages:
          - hub
          - {key: c4, vi: "Mô hình C4 override", en: "C4 model override"}
    """)
    docs = _docs(
        tmp_path,
        pages_yaml=yaml_with_override,
        partials={"hub.html": "x"},
        sources={"architecture/c4.md": "# C4\n"},
        assets=["js/01-core.js", "js/09-search.js", "css/01-base.css", "lib/three.min.js"],
    )
    man = M.load_manifest_from_yaml(docs / "_index" / "showcase.yaml")
    # validate không có lỗi
    f = Findings()
    M.validate_manifest(man, docs, f)
    assert not f.has_errors(), [i.msg for i in f.by_severity("error")]
    # footer_pages chuẩn hoá đúng
    assert man.footer_pages[0] == {"key": "hub", "vi": None, "en": None}
    assert man.footer_pages[1] == {"key": "c4", "vi": "Mô hình C4 override", "en": "C4 model override"}
    # footer_refs() trả label: str→fallback page; dict→dùng override
    refs = man.footer_refs()
    assert refs[0] == ("hub", "Tổng quan", "Overview")           # str entry → page label
    assert refs[1] == ("c4", "Mô hình C4 override", "C4 model override")  # dict override


def test_page_needs_source_or_partial(tmp_path):
    bad = _GOOD.replace(
        '- {key: hub, vi: Tổng quan, en: Overview, partial: hub.html, category: overview, accent: var(--ptnt), title: "Hub — tổng quan"}',
        "- {key: hub, vi: Tổng quan, en: Overview, category: overview, accent: var(--ptnt), title: 'Hub'}",
    )
    docs = _docs(tmp_path, pages_yaml=bad,
                 sources={"architecture/c4.md": "# C4\n"},
                 assets=["js/01-core.js", "js/09-search.js", "css/01-base.css", "lib/three.min.js"])
    man = M.load_manifest_from_yaml(docs / "_index" / "showcase.yaml")
    f = Findings()
    M.validate_manifest(man, docs, f)
    # page 'hub' không source cũng không partial → error (trừ khi empty:true)
    assert any("hub" in i.msg for i in f.by_severity("error"))


def test_hub_missing_is_error(tmp_path):
    """MAN_NO_HUB: manifest không có page 'hub' → error (engine hard-assume hub)."""
    no_hub = _GOOD.replace(
        '- {key: hub, vi: Tổng quan, en: Overview, partial: hub.html, category: overview, accent: var(--ptnt), title: "Hub — tổng quan"}',
        '- {key: home, vi: Tổng quan, en: Overview, partial: hub.html, category: overview, accent: var(--ptnt), title: "Home"}',
    ).replace("pages: [hub]", "pages: [home]").replace("footer_pages: [hub, c4]", "footer_pages: [home, c4]")
    docs = _docs(
        tmp_path,
        pages_yaml=no_hub,
        partials={"hub.html": "x"},
        sources={"architecture/c4.md": "# C4\n"},
        assets=["js/01-core.js", "js/09-search.js", "css/01-base.css", "lib/three.min.js"],
    )
    man = M.load_manifest_from_yaml(docs / "_index" / "showcase.yaml")
    f = Findings()
    M.validate_manifest(man, docs, f)
    errors = f.by_severity("error")
    assert any(i.code == "MAN_NO_HUB" for i in errors), [i.code for i in errors]


def test_category_mismatch_is_error(tmp_path):
    """MAN_CAT_MISMATCH: page khai category=C nhưng C.pages không liệt kê page đó → error."""
    # c4 khai category=design nhưng design.pages chỉ có [hub] không phải c4
    mismatch = _GOOD.replace(
        "- {key: design, vi: Thiết kế, en: Design, pages: [c4]}",
        "- {key: design, vi: Thiết kế, en: Design, pages: []}",
    )
    docs = _docs(
        tmp_path,
        pages_yaml=mismatch,
        partials={"hub.html": "x"},
        sources={"architecture/c4.md": "# C4\n"},
        assets=["js/01-core.js", "js/09-search.js", "css/01-base.css", "lib/three.min.js"],
    )
    man = M.load_manifest_from_yaml(docs / "_index" / "showcase.yaml")
    f = Findings()
    M.validate_manifest(man, docs, f)
    errors = f.by_severity("error")
    assert any(i.code == "MAN_CAT_MISMATCH" for i in errors), [i.code for i in errors]
