#!/usr/bin/env python3
"""render_md_page.py — md (frontmatter + body song ngữ) → showcase partial fragment.

P6-B: nội dung showcase sống ở md vật lý; partial prose trở thành ARTIFACT sinh từ md
(giữ nguyên build.py/shell/theme). Bilingual qua block `:::lang vi` / `:::lang en`:

    :::lang vi
    Đoạn tiếng Việt (markdown đầy đủ).
    :::
    :::lang en
    English paragraph.
    :::

→ `<div class="vi">…</div><div class="en">…</div>` (CSS toggle `.lang-vi/.lang-en` ẩn .en/.vi).
Đoạn KHÔNG bọc `:::lang` = trung tính (hiện ở cả 2 chế độ): bảng số liệu, code, sơ đồ.

Hàm chính: render_fragment(md_path) -> str (HTML fragment cho PARTIALS/).
CLI: render_md_page.py <doc.md> [--out partial.html]
"""
import argparse
import re
import sys
from pathlib import Path

try:
    import markdown as md_lib
except ImportError:
    print("[render] cần `pip install markdown`", file=sys.stderr)
    raise

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_docslib"))
from docslib import parse  # noqa: E402

_MD_EXT = ["tables", "fenced_code", "attr_list", "sane_lists"]
_LANG_RE = re.compile(r"^:::lang\s+(vi|en)\s*$")
GEN = "<!-- GENERATED từ md (P6-B render_md_page.py). Sửa nội dung ở doc .md, KHÔNG sửa file này. -->"


def _md(text: str) -> str:
    return md_lib.markdown(text.strip(), extensions=_MD_EXT) if text.strip() else ""


def _segments(body: str):
    """Tách body thành [(lang|None, text)]. lang ∈ {vi,en} cho block :::lang; None=trung tính."""
    segs, buf, cur = [], [], None
    lines = body.splitlines()
    i = 0
    while i < len(lines):
        m = _LANG_RE.match(lines[i].strip())
        if m:
            if buf:
                segs.append((cur, "\n".join(buf))); buf = []
            lang = m.group(1)
            i += 1
            blk = []
            while i < len(lines) and lines[i].strip() != ":::":
                blk.append(lines[i]); i += 1
            i += 1  # bỏ dòng ':::'
            segs.append((lang, "\n".join(blk)))
            cur = None
            continue
        buf.append(lines[i]); i += 1
    if buf:
        segs.append((cur, "\n".join(buf)))
    return segs


def render_body(body: str) -> str:
    """Body md song ngữ → HTML (div.vi/div.en cho block lang, neutral cho phần còn lại)."""
    out = []
    for lang, text in _segments(body):
        html = _md(text)
        if not html:
            continue
        if lang in ("vi", "en"):
            out.append(f'<div class="{lang}">{html}</div>')
        else:
            out.append(html)
    return "\n".join(out)


# FIX-21: link cross-doc trỏ file nguồn (.md/.yaml/.yml/.json) KHÔNG host trong showcase
# → 404 khi click. De-link: bỏ <a>, giữ text (showcase = output read-only, link sang nguồn vô nghĩa).
_DEAD_LINK_RE = re.compile(r'<a\b[^>]*\bhref="([^"]+)"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
_DEAD_EXT = (".md", ".yaml", ".yml", ".json")


def _delink_dead(html: str) -> str:
    def sub(m):
        path = m.group(1).split("#")[0].split("?")[0].lower()
        if path.startswith(("http://", "https://", "mailto:", "tel:", "//")):
            return m.group(0)
        return m.group(2) if path.endswith(_DEAD_EXT) else m.group(0)
    return _DEAD_LINK_RE.sub(sub, html)


_IMG_SRC_RE = re.compile(r'(<img[^>]*\bsrc=")([^"]*)(")')


def _rewrite_img(html: str) -> str:
    """Quy img src về path resolve được trong showcase build (public/pages/ → public/diagram/png/).
    Mọi `..*/_diagram/png/X` hoặc `_diagram/png/X` → `../diagram/png/X` (build_showcase copy png sang public/diagram/png)."""
    def sub(m):
        src = m.group(2)
        mm = re.search(r"_diagram/png/(.+)$", src)
        if mm:
            return f"{m.group(1)}../diagram/png/{mm.group(1)}{m.group(3)}"
        return m.group(0)
    return _IMG_SRC_RE.sub(sub, html)


def render_fragment(md_path: str | Path) -> str:
    """1 doc md → fragment showcase (hero từ H1+lead nếu có; phần còn lại 1 section)."""
    doc = parse(md_path)
    body = doc.body
    title = doc.meta.get("title") or _first_h1(body) or doc.meta.get("id", "")
    inner = _delink_dead(_rewrite_img(render_body(body)))
    return (
        f"{GEN}\n"
        f'<section>\n  <div class="wrap reveal">\n'
        f'    <div class="eyebrow">{_esc(title)}</div>\n'
        f"    {inner}\n"
        f"  </div>\n</section>\n"
    )


def _first_h1(body: str) -> str | None:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("md")
    ap.add_argument("--out")
    a = ap.parse_args()
    frag = render_fragment(a.md)
    if a.out:
        Path(a.out).write_text(frag, encoding="utf-8")
        print(f"[render] {a.md} → {a.out} ({len(frag)} bytes)")
    else:
        print(frag)


if __name__ == "__main__":
    main()
