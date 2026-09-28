#!/usr/bin/env python3
"""build_pdf.py — dist/aiop-docs.md → dist/aiop-docs.pdf (pure-Python, CI-friendly).

Pipeline: markdown → HTML → PDF bằng xhtml2pdf (pisa).
- Không cần system lib (wkhtmltopdf, chromium...).
- Nếu thiếu lib → in cảnh báo + exit 0 (pipeline không crash).
- Input: dist/aiop-docs.md (sinh bởi build_flat_md.py).
- Output: dist/aiop-docs.pdf.
"""
import sys
from pathlib import Path

# Kiểm tra lib trước — không để ImportError làm crash pipeline. Names stay
# bound (None), no sys.exit at module scope — that would make the module
# impossible to import for inspection (pytest collection aborts with
# INTERNALERROR). The "lib missing, skip" exit happens in main() instead,
# only when the build is actually invoked.
try:
    import markdown as md_lib
except ImportError:
    md_lib = None

try:
    from xhtml2pdf import pisa
except ImportError:
    pisa = None

REPO = Path(__file__).resolve().parents[6]

CSS = """
body {
    font-family: DejaVu Sans, Arial, sans-serif;
    font-size: 10pt;
    line-height: 1.5;
    color: #111;
    margin: 0;
    padding: 0;
}
h1, h2, h3 { color: #1a3a5c; page-break-after: avoid; }
h1 { font-size: 16pt; margin-top: 18pt; }
h2 { font-size: 13pt; margin-top: 14pt; }
h3 { font-size: 11pt; margin-top: 10pt; }
table {
    border-collapse: collapse;
    width: 100%;
    margin: 8pt 0;
    font-size: 8.5pt;
}
th, td {
    border: 0.5pt solid #aaa;
    padding: 3pt 5pt;
    text-align: left;
    vertical-align: top;
}
th { background: #e8eef4; font-weight: bold; }
code, pre {
    font-family: DejaVu Sans Mono, Courier New, monospace;
    font-size: 8pt;
    background: #f5f5f5;
    padding: 1pt 3pt;
}
pre { padding: 5pt; }
hr { border: 0; border-top: 0.5pt solid #ccc; margin: 10pt 0; }
blockquote { border-left: 3pt solid #aaa; margin-left: 0; padding-left: 8pt; color: #444; }
"""


def _link_callback(uri, rel):
    """Resolve ảnh/asset tương đối về file thật trên đĩa.

    flat-md gộp từ nhiều doc (mỗi doc có base dir khác) nên path ảnh kiểu
    `../_diagram/png/X.png` không resolve được từ dist/. Quy về REPO/docs:
    bỏ tiền tố `./` `../`, thử docs/<clean>; fallback theo basename trong _diagram/png.
    """
    if not uri or uri.startswith(("http://", "https://", "data:")):
        return uri
    p = Path(uri)
    if p.is_absolute() and p.exists():
        return str(p)
    clean = uri.lstrip("./")
    while clean.startswith("../"):
        clean = clean[3:]
    cand = REPO / "docs" / clean
    if cand.exists():
        return str(cand)
    cand2 = REPO / "docs" / "_diagram" / "png" / p.name      # fallback theo tên file
    if cand2.exists():
        return str(cand2)
    return uri


def _wrap_html(body_html: str, title: str = "aiop-docs") -> str:
    return (
        "<!DOCTYPE html>\n<html><head>\n"
        '<meta charset="UTF-8" />\n'
        f"<title>{title}</title>\n"
        f"<style>{CSS}</style>\n"
        "</head><body>\n"
        + body_html
        + "\n</body></html>\n"
    )


def main():
    if md_lib is None:
        print("[pdf] WARN: thư viện `markdown` chưa cài (pip install markdown). Bỏ qua build PDF.")
        sys.exit(0)
    if pisa is None:
        print("[pdf] WARN: thư viện `xhtml2pdf` chưa cài (pip install xhtml2pdf). Bỏ qua build PDF.")
        sys.exit(0)

    dist = REPO / "dist"
    md_path = dist / "aiop-docs.md"
    pdf_path = dist / "aiop-docs.pdf"

    if not md_path.is_file():
        print(f"[pdf] WARN: {md_path} chưa tồn tại — chạy build_flat_md.py trước.")
        sys.exit(0)

    print(f"[pdf] Đọc {md_path} ({md_path.stat().st_size} bytes)...")
    md_text = md_path.read_text(encoding="utf-8")

    print("[pdf] Chuyển đổi markdown → HTML...")
    body_html = md_lib.markdown(
        md_text,
        extensions=["tables", "fenced_code", "toc"],
    )
    full_html = _wrap_html(body_html)

    print(f"[pdf] Render HTML → PDF ({pdf_path})...")
    with open(pdf_path, "wb") as pdf_file:
        result = pisa.CreatePDF(full_html, dest=pdf_file, encoding="utf-8",
                                link_callback=_link_callback)

    if result.err:
        # xhtml2pdf đã cố gắng nhưng có lỗi — file có thể không hoàn chỉnh
        print(f"[pdf] WARN: xhtml2pdf báo lỗi ({result.err}) — PDF có thể không hoàn chỉnh.")
    else:
        print(f"[pdf] OK → {pdf_path} ({pdf_path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
