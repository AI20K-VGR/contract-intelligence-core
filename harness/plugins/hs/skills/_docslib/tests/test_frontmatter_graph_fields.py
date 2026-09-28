"""C3 — frontmatter-as-SSOT: part docs sở hữu layer/note/reuses → derive modules.yaml.

Multi-touch (LESSONS): schema (frontmatter validate) + loader (parse) + derive (generator) +
writer (merge_frontmatter) cùng mang field mới, round-trip giá-trị-non-default.
"""
from pathlib import Path

import yaml_io

from docslib import frontmatter as fm
from docslib.findings import Findings
from docslib.index import load_model
from docslib import graph


def _write(p: Path, payload) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(payload if isinstance(payload, str) else yaml_io.safe_dump(payload, allow_unicode=True),
                 encoding="utf-8")


def _readme(docs: Path, rel_dir: str, mid: str) -> None:
    _write(docs / rel_dir / "README.md",
           f"---\nid: {mid}\ntype: module-readme\nstatus: stable\nowner: PTNT\nversion: 1.0.0\n---\n# {mid}\n")


def _part(docs: Path, rel_dir: str, pid: str, *, owner="PTNT", layer=None, note=None,
          reuses=None, universal_spine=None) -> None:
    meta = {"id": pid, "type": "part", "status": "stable", "owner": owner, "version": "1.0.0"}
    if layer is not None:
        meta["layer"] = layer
    if note is not None:
        meta["note"] = note
    if reuses is not None:
        meta["reuses"] = reuses
    if universal_spine is not None:
        meta["universal_spine"] = universal_spine
    fmtext = "---\n" + yaml_io.safe_dump(meta, allow_unicode=True, sort_keys=False) + "---\n# " + pid + "\n"
    _write(docs / rel_dir / "parts" / f"{pid}.md", fmtext)


def _tree(docs: Path) -> None:
    _readme(docs, "modules/core/mod-01-intake", "mod-01")
    _readme(docs, "modules/core/mod-02-validate", "mod-02")
    # mod-01 owns two parts; one is universal spine + note + layer
    _part(docs, "modules/core/mod-01-intake", "vision-llm", note="extractor family", layer="L3")
    _part(docs, "modules/core/mod-01-intake", "audit-spine", universal_spine=True, note="57/60 case")
    # mod-02 owns one part that reuses a mod-01 part
    _part(docs, "modules/core/mod-02-validate", "rule-eval",
          reuses=[{"part": "vision-llm", "why": "pre-issuance check"}])


# ---- schema validate ------------------------------------------------------

def test_schema_accepts_graph_fields_on_part(tmp_path):
    _part(tmp_path, "modules/core/mod-01-intake", "p1", layer="L3", note="n", reuses=[{"part": "x", "why": "w"}])
    doc = fm.parse(tmp_path / "modules/core/mod-01-intake/parts/p1.md")
    f = Findings()
    fm.validate(doc, f)
    assert not f.has_errors(), [i.msg for i in f.by_severity("error")]
    assert doc.meta["layer"] == "L3"
    assert doc.meta["note"] == "n"
    assert doc.meta["reuses"] == [{"part": "x", "why": "w"}]


def test_schema_rejects_bad_layer(tmp_path):
    _part(tmp_path, "modules/core/mod-01-intake", "p1", layer="L9")
    doc = fm.parse(tmp_path / "modules/core/mod-01-intake/parts/p1.md")
    f = Findings()
    fm.validate(doc, f)
    assert any("layer" in i.msg.lower() for i in f.by_severity("error"))


def test_schema_rejects_bad_reuses_shape(tmp_path):
    _part(tmp_path, "modules/core/mod-01-intake", "p1", reuses=["not-a-dict"])
    doc = fm.parse(tmp_path / "modules/core/mod-01-intake/parts/p1.md")
    f = Findings()
    fm.validate(doc, f)
    assert any("reuses" in i.msg.lower() for i in f.by_severity("error"))


# ---- derive parts+links ---------------------------------------------------

def test_derive_parts_from_frontmatter(tmp_path):
    _tree(tmp_path)
    model = load_model(tmp_path)
    derived = graph.derive_part_graph(model)
    parts = derived["parts"]
    assert set(parts) == {"vision-llm", "audit-spine", "rule-eval"}
    assert parts["vision-llm"]["home"] == "mod-01"
    assert parts["vision-llm"]["layer"] == "L3"
    assert parts["vision-llm"]["note"] == "extractor family"
    assert parts["vision-llm"]["at"] == "modules/core/mod-01-intake/parts/vision-llm.md"
    assert parts["audit-spine"]["universal_spine"] is True


def test_derive_links_from_reuses(tmp_path):
    _tree(tmp_path)
    model = load_model(tmp_path)
    derived = graph.derive_part_graph(model)
    links = derived["links"]
    assert {"from": "mod-02", "uses": "vision-llm", "why": "pre-issuance check"} in links


def test_single_edit_propagates(tmp_path):
    _tree(tmp_path)
    # edit reuses on the consumer part — derived links must change with NO second edit
    _part(tmp_path, "modules/core/mod-02-validate", "rule-eval",
          reuses=[{"part": "audit-spine", "why": "guardrail"}])
    model = load_model(tmp_path)
    links = graph.derive_part_graph(model)["links"]
    assert {"from": "mod-02", "uses": "audit-spine", "why": "guardrail"} in links
    assert not any(ln["uses"] == "vision-llm" for ln in links)


def test_derived_modules_yaml_preserves_config_parts(tmp_path):
    _tree(tmp_path)
    model = load_model(tmp_path)
    cp = {"extraction-schema": {"home": "mod-01", "owner": "PTSP", "vi": "x", "en": "y"}}
    out = graph.derive_modules_yaml(model, config_parts=cp)
    assert out["config_parts"] == cp           # pass-through (no doc home → hand-authored)
    assert "vision-llm" in out["parts"]
    assert out["links"]


def test_derive_modules_yaml_default_config_parts(tmp_path):
    """không truyền config_parts → lấy từ model; rỗng → bỏ key."""
    _tree(tmp_path)
    model = load_model(tmp_path)
    model.config_parts = {"cp1": {"home": "mod-01", "owner": "PTSP", "vi": "a", "en": "b"}}
    out = graph.derive_modules_yaml(model)               # default → model.config_parts
    assert out["config_parts"] == model.config_parts
    model.config_parts = {}
    out2 = graph.derive_modules_yaml(model)
    assert "config_parts" not in out2                    # rỗng → omit


def test_migration_roundtrips_universal_spine(tmp_path):
    """universal_spine (1 trong 3 _PART_FIELDS) round-trip qua migrate→derive."""
    import importlib.util
    docs = tmp_path / "docs"
    _readme(docs, "modules/core/mod-04-spine", "mod-04")
    _part(docs, "modules/core/mod-04-spine", "audit-spine")
    _write(docs / "_index" / "modules.yaml", {"parts": {
        "audit-spine": {"home": "mod-04", "at": "modules/core/mod-04-spine/parts/audit-spine.md",
                        "owner": "PTNT", "universal_spine": True, "note": "57/60"}}})
    script = (Path(__file__).resolve().parents[2]
              / "docs-standardize" / "scripts" / "migrate_facts_to_frontmatter.py")
    spec = importlib.util.spec_from_file_location("migrate_facts_us", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.migrate(docs)
    parts = graph.derive_part_graph(load_model(docs))["parts"]
    assert parts["audit-spine"]["universal_spine"] is True
    assert parts["audit-spine"]["note"] == "57/60"


def test_derived_graph_validates_clean(tmp_path):
    """Derived graph nạp ngược vào Model phải pass validate (lossless, không orphan)."""
    _tree(tmp_path)
    model = load_model(tmp_path)
    out = graph.derive_modules_yaml(model)
    model.parts = out["parts"]
    model.links = out["links"]
    f = Findings()
    graph.validate(model, f, frontmatter_check=False)
    # band thiếu (chưa set) sẽ báo module-missing-band; lọc chỉ kiểm part/link clean
    graph_errs = [i for i in f.by_severity("error") if i.code.startswith(("part-", "link-"))]
    assert not graph_errs, [i.msg for i in graph_errs]


# ---- writer round-trip (multi-touch) --------------------------------------

def test_derive_links_from_module_readme_reuses(tmp_path):
    """Link thật là module→part → reuse cũng tác giả được trên module README (from = module)."""
    _readme(tmp_path, "modules/core/mod-01-intake", "mod-01")
    # README mod-02 mang reuses module-level
    _write(tmp_path / "modules/core/mod-02-validate" / "README.md",
           "---\nid: mod-02\ntype: module-readme\nstatus: stable\nowner: PTNT\nversion: 1.0.0\n"
           "reuses:\n- {part: vision-llm, why: pre-issuance}\n---\n# mod-02\n")
    _part(tmp_path, "modules/core/mod-01-intake", "vision-llm")
    model = load_model(tmp_path)
    links = graph.derive_part_graph(model)["links"]
    assert {"from": "mod-02", "uses": "vision-llm", "why": "pre-issuance"} in links


def test_migration_roundtrip_parity(tmp_path):
    """migrate đẩy fact modules.yaml → frontmatter; derive lại == graph gốc (lossless)."""
    import importlib.util
    docs = tmp_path / "docs"
    _readme(docs, "modules/core/mod-01-intake", "mod-01")
    _readme(docs, "modules/core/mod-02-validate", "mod-02")
    _part(docs, "modules/core/mod-01-intake", "vision-llm")
    _part(docs, "modules/core/mod-02-validate", "rule-eval")
    original = {
        "parts": {
            "vision-llm": {"home": "mod-01", "at": "modules/core/mod-01-intake/parts/vision-llm.md",
                           "owner": "PTNT", "layer": "L3", "note": "extractor family"},
            "rule-eval": {"home": "mod-02", "at": "modules/core/mod-02-validate/parts/rule-eval.md",
                          "owner": "PTNT"},
        },
        "links": [{"from": "mod-02", "uses": "vision-llm", "why": "pre-issuance check"}],
    }
    _write(docs / "_index" / "modules.yaml", original)

    script = (Path(__file__).resolve().parents[2]
              / "docs-standardize" / "scripts" / "migrate_facts_to_frontmatter.py")
    spec = importlib.util.spec_from_file_location("migrate_facts", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    moved = mod.migrate(docs)
    assert moved > 0
    # derive lại từ frontmatter == graph gốc (parits+links semantic)
    derived = graph.derive_modules_yaml(load_model(docs))
    assert derived["parts"] == original["parts"]
    assert sorted(derived["links"], key=lambda l: (l["from"], l["uses"])) == \
           sorted(original["links"], key=lambda l: (l["from"], l["uses"]))
    # idempotent: chạy lại không đổi
    assert mod.migrate(docs) == 0


def test_merge_frontmatter_refuses_malformed_block(tmp_path):
    """frontmatter cũ malformed (list/scalar/yaml-error) → KHÔNG ghi đè mất content."""
    import pytest
    p = tmp_path / "bad.md"
    _write(p, "---\n- a\n- b\n---\nbody giữ lại\n")   # frontmatter là list → not mapping
    with pytest.raises(ValueError):
        fm.merge_frontmatter(p, {"layer": "L3"})
    # nguyên trạng — không bị wipe
    assert "- a" in p.read_text(encoding="utf-8")
    assert "body giữ lại" in p.read_text(encoding="utf-8")


def test_migration_skips_malformed_part_doc(tmp_path):
    """migrate gặp part doc malformed → bỏ qua, KHÔNG wipe, vẫn migrate phần còn lại."""
    import importlib.util
    docs = tmp_path / "docs"
    _readme(docs, "modules/core/mod-01-intake", "mod-01")
    # part doc có frontmatter HỎNG (list)
    _write(docs / "modules/core/mod-01-intake/parts/broken.md", "---\n- x\n---\nkeep\n")
    _write(docs / "modules/core/mod-01-intake/parts/ok.md",
           "---\nid: ok\ntype: part\nstatus: stable\nowner: PTNT\nversion: 1.0.0\n---\n# ok\n")
    _write(docs / "_index" / "modules.yaml", {"parts": {
        "broken": {"home": "mod-01", "at": "modules/core/mod-01-intake/parts/broken.md", "note": "n"},
        "ok": {"home": "mod-01", "at": "modules/core/mod-01-intake/parts/ok.md", "layer": "L3"},
    }})
    script = (Path(__file__).resolve().parents[2]
              / "docs-standardize" / "scripts" / "migrate_facts_to_frontmatter.py")
    spec = importlib.util.spec_from_file_location("migrate_facts2", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    moved = mod.migrate(docs)   # KHÔNG raise dù có doc hỏng
    assert moved == 1           # chỉ đếm doc ok, KHÔNG đếm doc hỏng
    assert "- x" in (docs / "modules/core/mod-01-intake/parts/broken.md").read_text(encoding="utf-8")
    assert fm.parse(docs / "modules/core/mod-01-intake/parts/ok.md").meta["layer"] == "L3"


def test_migrate_dry_run_reports_without_writing(tmp_path):
    """dry_run đếm fact chưa migrate, KHÔNG ghi file."""
    import importlib.util
    docs = tmp_path / "docs"
    _readme(docs, "modules/core/mod-01-intake", "mod-01")
    _part(docs, "modules/core/mod-01-intake", "p1")
    _write(docs / "_index" / "modules.yaml", {"parts": {
        "p1": {"home": "mod-01", "at": "modules/core/mod-01-intake/parts/p1.md", "layer": "L3"}}})
    before = (docs / "modules/core/mod-01-intake/parts/p1.md").read_text(encoding="utf-8")
    script = (Path(__file__).resolve().parents[2]
              / "docs-standardize" / "scripts" / "migrate_facts_to_frontmatter.py")
    spec = importlib.util.spec_from_file_location("migrate_facts3", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    n = mod.migrate(docs, dry_run=True)
    assert n > 0                                                  # báo còn fact chưa migrate
    assert (docs / "modules/core/mod-01-intake/parts/p1.md").read_text(encoding="utf-8") == before  # KHÔNG ghi


def test_derive_no_none_from_link_for_orphan_part(tmp_path):
    """part ngoài mọi module dir → KHÔNG emit link from:None."""
    _readme(tmp_path, "modules/core/mod-01-intake", "mod-01")
    _part(tmp_path, "orphans", "lonely", reuses=[{"part": "x", "why": "y"}])  # 'orphans' không phải module
    model = load_model(tmp_path)
    links = graph.derive_part_graph(model)["links"]
    assert all(ln["from"] is not None for ln in links)


def test_derive_refuses_duplicate_part_id(tmp_path):
    """F5: 2 part trùng id ở 2 module → derive TỪ CHỐI (last-wins âm thầm = mất part)."""
    import pytest
    _readme(tmp_path, "modules/core/mod-01-intake", "mod-01")
    _readme(tmp_path, "modules/core/mod-02-validate", "mod-02")
    _part(tmp_path, "modules/core/mod-01-intake", "dup")
    _part(tmp_path, "modules/core/mod-02-validate", "dup")
    with pytest.raises(ValueError):
        graph.derive_part_graph(load_model(tmp_path))


def test_validate_flags_at_escape(tmp_path):
    """F4: part.at thoát docs-root → part-at-escape (không phải part-missing-file)."""
    _readme(tmp_path, "modules/core/mod-01-intake", "mod-01")
    model = load_model(tmp_path)
    model.parts = {"evil": {"home": "mod-01", "at": "../outside/victim.md"}}
    f = Findings()
    graph.validate(model, f, frontmatter_check=False)
    assert any(i.code == "part-at-escape" for i in f.by_severity("error"))


def test_migrate_refuses_at_outside_docsroot(tmp_path):
    """F4: migrate KHÔNG ghi vào file ngoài docs-root qua at:../"""
    import importlib.util
    docs = tmp_path / "docs"
    outside = tmp_path / "outside" / "victim.md"
    _write(outside, "---\nid: v\ntype: part\nstatus: stable\nowner: PTNT\nversion: 1.0.0\n---\nSECRET\n")
    _readme(docs, "modules/core/mod-01-intake", "mod-01")
    _write(docs / "_index" / "modules.yaml", {"parts": {
        "evil": {"home": "mod-01", "at": "../outside/victim.md", "note": "inject"}}})
    script = (Path(__file__).resolve().parents[2]
              / "docs-standardize" / "scripts" / "migrate_facts_to_frontmatter.py")
    spec = importlib.util.spec_from_file_location("migrate_facts_f4", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.migrate(docs)
    assert "SECRET" in outside.read_text(encoding="utf-8")
    assert "inject" not in outside.read_text(encoding="utf-8")   # KHÔNG bị ghi note


def _load_migrate_mod():
    import importlib.util
    script = (Path(__file__).resolve().parents[2]
              / "docs-standardize" / "scripts" / "migrate_facts_to_frontmatter.py")
    spec = importlib.util.spec_from_file_location("migrate_facts_f1", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_migrate_dir_alias_preserves_edge(tmp_path):
    """F1: README frontmatter id ≠ mod-NN nhưng link.from dùng mod-NN → dir-alias tìm được README,
    edge KHÔNG mất (reuses được ghi)."""
    docs = tmp_path / "docs"
    _write(docs / "modules/core/mod-01-intake" / "README.md",
           "---\nid: document-intake\ntype: module-readme\nstatus: stable\nowner: PTNT\nversion: 1.0.0\n---\n# m\n")
    _part(docs, "modules/core/mod-01-intake", "p1")
    _write(docs / "_index" / "modules.yaml", {
        "parts": {"p1": {"home": "document-intake", "at": "modules/core/mod-01-intake/parts/p1.md"}},
        "links": [{"from": "mod-01", "uses": "p1", "why": "w"}]})
    mod = _load_migrate_mod()
    assert mod.unresolved_targets(docs) == []        # mod-01 resolve qua dir-alias
    mod.migrate(docs)
    readme_meta = fm.parse(docs / "modules/core/mod-01-intake/README.md").meta
    assert readme_meta.get("reuses") == [{"part": "p1", "why": "w"}]   # edge GHI, không mất


def test_migrate_check_reports_unresolved_from(tmp_path):
    """F1: link.from không có module nào → unresolved_targets báo (--check fail)."""
    docs = tmp_path / "docs"
    _readme(docs, "modules/core/mod-01-intake", "mod-01")
    _part(docs, "modules/core/mod-01-intake", "p1")
    _write(docs / "_index" / "modules.yaml", {
        "parts": {"p1": {"home": "mod-01", "at": "modules/core/mod-01-intake/parts/p1.md"}},
        "links": [{"from": "mod-99", "uses": "p1", "why": "w"}]})   # mod-99 không tồn tại
    mod = _load_migrate_mod()
    assert "mod-99" in mod.unresolved_targets(docs)


def test_merge_frontmatter_roundtrips_new_fields(tmp_path):
    p = tmp_path / "x.md"
    _write(p, "---\nid: p1\ntype: part\nstatus: stable\nowner: PTNT\nversion: 1.0.0\n---\n# body\nkeep me\n")
    fm.merge_frontmatter(p, {"layer": "L4", "note": "migrated", "reuses": [{"part": "q", "why": "z"}]})
    doc = fm.parse(p)
    assert doc.meta["layer"] == "L4"
    assert doc.meta["note"] == "migrated"
    assert doc.meta["reuses"] == [{"part": "q", "why": "z"}]
    # original required fields + body preserved
    assert doc.meta["id"] == "p1"
    assert "keep me" in doc.body
