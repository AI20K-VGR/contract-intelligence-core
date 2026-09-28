#!/usr/bin/env python3
"""ANALYZER (lớp 1) — validate structural toàn bộ docs. Exit 0 luôn; nguồn sự thật = artifact JSON.

  python3 check_docs.py [--docs docs] [--artifact harness/state/docs-check.json] [--quiet]

KHÔNG sửa file, KHÔNG phán nội dung. Chỉ đếm/đi-graph → findings (error|warn|info).
Gate riêng (docs_gate.py) đọc artifact và quyết exit 2.
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "_docslib"))
from docslib import load_model, Findings, graph, load_manifest, validate_manifest  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[6]


def run(docs_dir: pathlib.Path) -> tuple[Findings, object]:
    model = load_model(docs_dir)
    f = Findings()
    graph.validate(model, f)
    # Ép convention content⟂_index⟂_present⟂output (chỉ khi tree đã adopt — back-compat legacy).
    graph.validate_clean_split(model, f)
    # Validate manifest site-structure (pages/categories/asset_slots/footer).
    # Nguồn presentation = _present (ưu tiên) fallback legacy showcase — để manifest validation
    # còn chạy sau khi showcase.yaml bị gỡ; shim đã nạp present cho cây legacy.
    manifest = load_manifest(model.present or model.showcase)
    if manifest.pages:  # chỉ kiểm khi manifest đã khai (repo chưa migrate vẫn pass)
        validate_manifest(manifest, docs_dir, f)
    return f, model


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default=str(REPO / "docs"))
    ap.add_argument("--artifact", default=str(REPO / "harness" / "state" / "docs-check.json"))
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    f, model = run(pathlib.Path(a.docs))
    art = pathlib.Path(a.artifact)
    art.parent.mkdir(parents=True, exist_ok=True)
    f.write_artifact(art, generated_from=str(pathlib.Path(a.docs)),
                     extra={"modules": len(model.modules), "docs": len(model.docs),
                            "parts": len(model.parts), "links": len(model.links)})
    if not a.quiet:
        f.print_summary("DOCS STANDARDIZE")
        print(f"\nartifact → {art.relative_to(REPO) if art.is_relative_to(REPO) else art}")


if __name__ == "__main__":
    main()
