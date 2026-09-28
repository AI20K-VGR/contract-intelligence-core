"""C2 — build output rời cây nguồn: derived-output SSOT + generate ghi đúng out-dir.

- `is_derived_output` phân loại đúng output dẫn xuất (gitignore/cấm-commit) vs nguồn.
- `generate_showcase_data` CHỈ ghi vào out_dir truyền vào, KHÔNG ghi ngược `docs/`.
"""
from pathlib import Path

from docslib.derived import is_derived_output, DERIVED_OUTPUT_GLOBS
from docslib.index import Model
from docslib import graph


def test_derived_classifies_build_output():
    assert is_derived_output("public/index.html")
    assert is_derived_output("public/pages/x.html")
    assert is_derived_output("showcase/assets/js/module-m4-data.js")
    assert is_derived_output("showcase/assets/js/ptnt-clusters-data.js")
    assert is_derived_output("_diagram/png/overview.png")


def test_derived_glob_does_not_cross_slash():
    """`*-data.js` chỉ khớp 1 segment, KHÔNG nuốt thư mục con (tránh false-pos JS tay lồng sâu)."""
    assert is_derived_output("showcase/assets/js/module-m4-data.js")
    assert not is_derived_output("showcase/assets/js/vendor/chart-data.js")
    assert not is_derived_output("showcase/assets/js/sub/deep/x-data.js")


def test_derived_glob_case_insensitive():
    """F2: biến thể hoa (`.JS`, `SHOWCASE/`, `INDEX.html`) vẫn là output dẫn xuất."""
    assert is_derived_output("showcase/assets/js/x-data.JS")
    assert is_derived_output("SHOWCASE/assets/js/x-data.js")
    assert is_derived_output("public/INDEX.html")
    assert is_derived_output("_DIAGRAM/png/x.png")


def test_source_not_classified_derived():
    # Nguồn KHÔNG bị nhận nhầm là derived (tránh git-rm content tay)
    assert not is_derived_output("modules/core/mod-01/README.md")
    assert not is_derived_output("_index/modules.yaml")
    assert not is_derived_output("_index/bands.yaml")
    assert not is_derived_output("_present/present.yaml")
    assert not is_derived_output("_diagram/puml/overview.puml")          # puml = nguồn
    assert not is_derived_output("showcase/assets/js/09-search.js")      # JS tay (không -data.js)
    assert not is_derived_output("showcase/partials/hub.html")           # CỐ Ý loại (mixed) — xem BACKLOG


def test_derived_globs_are_documented_set():
    # SSOT có đúng 3 nhóm an toàn; partials KHÔNG nằm trong (quyết định người dùng)
    assert "public/**" in DERIVED_OUTPUT_GLOBS
    assert "showcase/assets/js/*-data.js" in DERIVED_OUTPUT_GLOBS
    assert "_diagram/png/**" in DERIVED_OUTPUT_GLOBS
    assert not any("partials" in g for g in DERIVED_OUTPUT_GLOBS)


def _minimal_model(docs_root: Path) -> Model:
    return Model(
        docs_root=docs_root, docs=[], modules=[], parts={}, config_parts={},
        links=[], foundations=[], safety=[], showcase={},
    )


def test_generate_showcase_data_writes_only_to_outdir(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    out = tmp_path / "build-out"
    model = _minimal_model(docs)
    written = graph.generate_showcase_data(model, out)
    # 4 data-JS sinh ra, tất cả NẰM trong out, KHÔNG file nào ghi vào docs/
    assert set(written) == {
        "module-m4-data.js", "ptnt-layers-data.js",
        "ptnt-clusters-data.js", "part-modref-data.js",
    }
    for name in written:
        assert (out / name).is_file()
    # docs/ tuyệt đối không có file derived sau build
    assert not list(docs.rglob("*-data.js"))
    assert not list(docs.rglob("*.js"))
