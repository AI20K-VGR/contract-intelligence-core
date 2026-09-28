#!/usr/bin/env python3
"""build_showcase.py — Bước A+B+C của P4.

Bước A: sinh 4 data-JS từ _index (ghi đè bản module-map trong docs/showcase/assets/js/).
Bước B: chạy assembler docs/showcase/build.py để tạo docs/public/.
Bước C: đồng bộ docs/public/ → public/ (chỉ index.html + pages/ + assets/).

DEBT: partials (nội dung prose) tạm còn ở docs/showcase/partials — đây là kỹ nợ kỹ thuật.
P6 (showcase redesign) sẽ chuyển nội dung sang md thật; P4 chỉ đổi nguồn data
(module-map→_index) và đưa code build vào skill, không đụng nội dung.
"""
import shutil
import subprocess
import sys
from pathlib import Path

# Đường dẫn repo (tính từ vị trí script)
REPO = Path(__file__).resolve().parents[6]  # ...skills/docs-build/scripts → ...vsf-aio-platform-showcase
DOCSLIB = REPO / "harness" / "plugins" / "hs" / "skills" / "_docslib"
sys.path.insert(0, str(DOCSLIB))

from docslib import load_model, graph  # noqa: E402
from docslib.findings import Findings  # noqa: E402
from docslib.manifest import load_manifest  # noqa: E402

# --- best-effort harness wiring (#3 encoding DRY, #2 telemetry) -------------
# Both degrade to no-ops when the script runs outside a harness tree (the skill
# stays portable: no hard dependency on harness/scripts).
_HARNESS_SCRIPTS = REPO / "harness" / "scripts"
if _HARNESS_SCRIPTS.is_dir():
    sys.path.append(str(_HARNESS_SCRIPTS))

try:
    from encoding_utils import configure_utf8_console  # noqa: E402
except Exception:  # noqa: BLE001
    def configure_utf8_console():  # fallback no-op
        return None


def _emit(record: dict) -> None:
    """Append one docs-build outcome to the telemetry sink (read by lens_docs_build).
    Fail-open + best-effort: silent no-op outside a harness install."""
    try:
        from telemetry_paths import append_event
        append_event("docs-build.jsonl", record)
    except Exception:  # noqa: BLE001 — telemetry must never break the build
        pass


def publish(src: Path, dst: Path, diag_src: Path | None = None) -> int:
    """Copy the built showcase from `src` into `dst`, returning the page count.

    `dst` holds two lifecycles: pages/, assets/ and diagram/ are regenerated
    every build, while install.sh and install.ps1 are hand-written and have no
    counterpart under `src`. So the generated subtrees are cleared individually
    — clearing `dst` wholesale deletes the hand-written files, and no later step
    copies them back.
    """
    dst.mkdir(parents=True, exist_ok=True)
    for sub in ("pages", "assets", "diagram"):
        if (dst / sub).is_dir():
            shutil.rmtree(dst / sub)

    shutil.copy2(src / "index.html", dst / "index.html")
    for sub in ("pages", "assets"):
        if (src / sub).is_dir():
            shutil.copytree(src / sub, dst / sub)
    # P6-B: md-sourced pages reference ../diagram/png/
    if diag_src is not None and diag_src.is_dir():
        shutil.copytree(diag_src, dst / "diagram" / "png")

    return len(list((dst / "pages").glob("*.html"))) if (dst / "pages").is_dir() else 0


def main():
    configure_utf8_console()
    # ------------------------------------------------------------------
    # Bước A — refresh 4 data-JS từ _index
    # ------------------------------------------------------------------
    print("[A] Load model từ docs/_index + frontmatter...")
    model = load_model(REPO / "docs")

    # Validate structural invariant trước khi sinh — abort sạch thay vì traceback
    print("[A] Validate model...")
    f = Findings()
    graph.validate(model, f)
    if f.has_errors():
        print("[A] LỖI CẤU TRÚC — dừng build:")
        errs = f.by_severity("error")
        for item in errs:
            print(f"  ERROR [{item.code}] {item.where}: {item.msg}")
        _emit({"phase": "showcase", "outcome": "failed", "stage": "validate",
               "errors": len(errs)})
        sys.exit(1)

    js_dir = REPO / "docs" / "showcase" / "assets" / "js"
    print(f"[A] Sinh data-JS → {js_dir}")
    written = graph.generate_showcase_data(model, js_dir)
    for f in written:
        print(f"    ✓ {f}")

    # ------------------------------------------------------------------
    # Bước A2 (P6-B) — render prose page TỪ md → partial (artifact sinh).
    # SSOT: pages[].source trong showcase.yaml (page_sources đã xoá — NHÓM 3).
    # Page không có source giữ nguyên partial hand-authored (backward-compat).
    # ------------------------------------------------------------------
    manifest = load_manifest(model.showcase)
    source_pages = [p for p in manifest.pages if p.source]
    if source_pages:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from render_md_page import render_fragment  # noqa: E402
        partials = REPO / "docs" / "showcase" / "partials"
        print(f"[A2] Render {len(source_pages)} prose page từ md (P6-B)...")
        for p in source_pages:
            src = REPO / "docs" / p.source
            if not src.is_file():
                print(f"    ✗ thiếu source {p.source} (page {p.key}) — bỏ qua")
                continue
            frag = render_fragment(src)
            (partials / f"{p.key}.html").write_text(frag, encoding="utf-8")
            print(f"    ✓ {p.key}.html ← {p.source}")

    # ------------------------------------------------------------------
    # Bước B — chạy assembler hiện có
    # ------------------------------------------------------------------
    # Bước B — assembler ghi TRỰC TIẾP vào public/ (repo root) từ DEC fcaf6235
    # ("build into the tree that actually gets published") — docs/public/ đã bị
    # xoá cùng .gitignore rule của nó trong chính commit đó. publish() (Bước C
    # cũ) giả định một docs/public/ trung gian không còn tồn tại; giữ hàm lại
    # cho test_showcase_publish_preserves_handwritten.py (nó tự seed src/dst
    # riêng) nhưng không gọi từ main() nữa — gọi sẽ luôn FileNotFoundError.
    build_py = REPO / "docs" / "showcase" / "build.py"
    dst = REPO / "public"
    print(f"[B] Chạy assembler: {build_py}")
    subprocess.run([sys.executable, str(build_py)], check=True)

    page_count = len(list((dst / "pages").glob("*.html"))) if (dst / "pages").is_dir() else 0
    diag_dir = dst / "diagram" / "png"
    img_count = len(list(diag_dir.glob("*"))) if diag_dir.is_dir() else 0
    print(f"[B] Assembler đã publish trực tiếp: index.html + {page_count} page(s) + assets/ → {dst}")
    print(f"    public/index.html = {(dst / 'index.html').stat().st_size} bytes")
    _emit({"phase": "showcase", "outcome": "ok", "pages": page_count,
           "diagrams": img_count, "md_sourced": len(source_pages)})


if __name__ == "__main__":
    main()
