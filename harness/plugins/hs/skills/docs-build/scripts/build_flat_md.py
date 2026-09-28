#!/usr/bin/env python3
"""build_flat_md.py — gộp mọi md thật trong docs/ thành dist/aiop-docs.md.

Thứ tự: theo sections[] trong showcase.yaml.
Nguồn: md thật (bỏ _inbox/_archive/_generated).
Mỗi doc: bỏ frontmatter, giữ body, ngăn bằng --- separator.
Output: dist/aiop-docs.md (cạnh repo root).
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[6]
DOCSLIB = REPO / "harness" / "plugins" / "hs" / "skills" / "_docslib"
sys.path.insert(0, str(DOCSLIB))

from docslib import load_model  # noqa: E402
from docslib.frontmatter import parse  # noqa: E402

SKIP_DIRS = {"_inbox", "_archive", "_generated", "__pycache__"}


def _glob_sorted(base: Path) -> list[Path]:
    if not base.exists():
        return []
    return sorted(p for p in base.glob("*.md")
                  if not any(seg in SKIP_DIRS for seg in p.relative_to(REPO / "docs").parts))


def _glob_rglob(base: Path) -> list[Path]:
    if not base.exists():
        return []
    return sorted(p for p in base.rglob("*.md")
                  if not any(seg in SKIP_DIRS for seg in p.relative_to(REPO / "docs").parts))


def gather_paths(model) -> list[Path]:
    """Xây danh sách file theo thứ tự sections showcase.yaml."""
    docs = REPO / "docs"
    paths: list[Path] = []

    # Thứ tự section theo showcase.yaml
    sections_order = [s["id"] for s in sorted(
        model.showcase.get("sections", []), key=lambda s: s.get("order", 99)
    )]

    section_map = {
        "overview": lambda: _glob_sorted(docs / "overview"),
        "architecture": lambda: _glob_sorted(docs / "architecture"),
        "quality": lambda: _glob_sorted(docs / "quality"),
        "governance": lambda: _glob_sorted(docs / "governance"),
        "techstack": lambda: ([docs / "techstack.md"] if (docs / "techstack.md").is_file() else []),
        "modules": lambda: _modules_paths(model, docs),
        "operations": lambda: _glob_rglob(docs / "operations"),
        "guides": lambda: _glob_rglob(docs / "guides"),
        "glossary": lambda: ([docs / "glossary.md"] if (docs / "glossary.md").is_file() else []),
        "changelog": lambda: ([docs / "change-log.md"] if (docs / "change-log.md").is_file() else []),
        "decisions": lambda: _decisions_paths(docs),
    }

    for sid in sections_order:
        fn = section_map.get(sid)
        if fn:
            paths.extend(fn())

    return paths


def _modules_paths(model, docs: Path) -> list[Path]:
    """Mỗi module theo thứ tự model.modules: README.md → design.md → parts/*.md → phần còn lại (thứ tự ổn định).
    Mở đầu = modules/README.md (index hub) trước khi duyệt từng module."""
    out: list[Path] = []
    mod_index = docs / "modules" / "README.md"
    if mod_index.is_file():
        out.append(mod_index)
    for m in model.modules:
        mdir = docs / m.dir
        already: set[Path] = set()

        readme = mdir / "README.md"
        if readme.is_file():
            out.append(readme)
            already.add(readme.resolve())

        design = mdir / "design.md"
        if design.is_file():
            out.append(design)
            already.add(design.resolve())

        parts_dir = mdir / "parts"
        if parts_dir.is_dir():
            for p in sorted(parts_dir.glob("*.md")):
                out.append(p)
                already.add(p.resolve())

        # Gom các *.md còn lại trong module dir (đệ quy) chưa được gom ở trên
        for p in sorted(mdir.rglob("*.md")):
            if p.resolve() not in already:
                out.append(p)
                already.add(p.resolve())

    return out


def _decisions_paths(docs: Path) -> list[Path]:
    out: list[Path] = []
    f = docs / "decisions.md"
    if f.is_file():
        out.append(f)
    adr_dir = docs / "decisions" / "adr"
    if adr_dir.is_dir():
        out.extend(sorted(adr_dir.glob("*.md")))
    return out


def main():
    dist = REPO / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    out_path = dist / "aiop-docs.md"

    print("[flat-md] Load model...")
    model = load_model(REPO / "docs")

    paths = gather_paths(model)
    print(f"[flat-md] {len(paths)} file cần gộp")

    chunks: list[str] = []
    included = 0
    for p in paths:
        if not p.is_file():
            continue
        doc = parse(p)
        body = doc.body.strip()
        if not body:
            continue
        chunks.append(body)
        included += 1

    content = "\n\n---\n\n".join(chunks) + "\n"
    out_path.write_text(content, encoding="utf-8")

    line_count = content.count("\n")
    print(f"[flat-md] Đã gộp {included} doc, {line_count} dòng → {out_path}")


if __name__ == "__main__":
    main()
