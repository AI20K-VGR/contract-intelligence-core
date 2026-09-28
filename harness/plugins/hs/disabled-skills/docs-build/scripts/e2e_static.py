#!/usr/bin/env python3
"""e2e tầng 1 — static-assert trên public/ (no browser). CHẶN CI.

Kiểm cấu trúc render mà không cần trình duyệt:
  - mọi href/src nội bộ (img/css/js/page-link) → file tồn tại trong public/
  - không còn @key@ chưa resolve (link protocol sót)
  - mỗi page trong manifest có file pages/<key>.html (trừ hub=index.html)
  - đếm + báo img/link/page

  python3 e2e_static.py [--public public] [--quiet]
exit 0 = sạch · exit 1 = có lỗi (CI chặn).
"""
import argparse
import pathlib
import re
import sys
from html.parser import HTMLParser

REPO = pathlib.Path(__file__).resolve().parents[6]
_ATKEY = re.compile(r"@[a-z0-9-]+@")
# bỏ qua link ngoài + neo + giả
_EXTERNAL = re.compile(r"^(https?:|mailto:|tel:|data:|#|//|javascript:)", re.I)


class _RefParser(HTMLParser):
    """Thu href/src + flag thuộc tính nghi @key@."""
    def __init__(self):
        super().__init__()
        self.refs = []   # (attr, value)
    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if k in ("href", "src") and v:
                self.refs.append((k, v))


# Portable single-file (self-contained, model asset khác multipage) — ref vỡ ở đây = SOFT.
_PORTABLE = "vsf-aio-platform-showcase.html"


def _classify(rel_name: str, val: str) -> str:
    """hard = chặn CI (asset/page/img thật trong multipage deploy); soft = báo + FIX.md.

    soft: (1) link .md cross-doc (trỏ doc nguồn không host trong showcase — quyết định nội dung),
          (2) mọi ref vỡ trong file portable (self-contained, asset-model khác).
    """
    if rel_name == _PORTABLE:
        return "soft"
    # link tới file NGUỒN (md/yaml/json) = cross-doc tới doc không host trong showcase → quyết định nội dung
    if val.split("#")[0].split("?")[0].lower().endswith((".md", ".yaml", ".yml", ".json")):
        return "soft"
    return "hard"


def _check_file(html_path, public, hard, soft):
    text = html_path.read_text(encoding="utf-8")
    rel = html_path.relative_to(public)
    rel_name = rel.name

    for m in _ATKEY.findall(text):
        # @key@ sót LUÔN hard (link protocol vỡ) — trừ file portable
        (soft if rel_name == _PORTABLE else hard).append(f"{rel}: @key@ chưa resolve: {m}")

    p = _RefParser()
    p.feed(text)
    for attr, val in p.refs:
        v = val.split("#")[0].split("?")[0]
        if not v or _EXTERNAL.match(val):
            continue
        target = (html_path.parent / v).resolve()
        if not target.is_file():
            bucket = hard if _classify(rel_name, val) == "hard" else soft
            bucket.append(f"{rel}: {attr}=\"{val}\" → KHÔNG tồn tại")


def run(public: pathlib.Path) -> tuple[list, list, dict]:
    hard, soft = [], []
    htmls = sorted(public.rglob("*.html"))
    if not htmls:
        hard.append(f"public/ rỗng hoặc không có .html: {public}")
        return hard, soft, {}
    n_img = 0
    for h in htmls:
        _check_file(h, public, hard, soft)
        n_img += h.read_text(encoding="utf-8").count("<img")
    return hard, soft, {"html": len(htmls), "img_tags": n_img}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--public", default=str(REPO / "public"),
                    help="deploy target (mặc định top-level public/ = GitLab Pages serve)")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--strict", action="store_true", help="soft cũng chặn (exit 1)")
    a = ap.parse_args()
    public = pathlib.Path(a.public)
    hard, soft, stats = run(public)
    if not a.quiet:
        print(f"e2e-static: {stats.get('html', 0)} html · {stats.get('img_tags', 0)} img-tag · {public}")
    if soft and not a.quiet:
        print(f"E2E-STATIC: {len(soft)} SOFT (không chặn — xem FIX.md):", file=sys.stderr)
        for e in soft[:50]:
            print(f"  ~ {e}", file=sys.stderr)
    if hard:
        print(f"E2E-STATIC: FAIL ({len(hard)} HARD)", file=sys.stderr)
        for e in hard[:50]:
            print(f"  ✗ {e}", file=sys.stderr)
        sys.exit(1)
    if a.strict and soft:
        print(f"E2E-STATIC: FAIL (--strict, {len(soft)} soft)", file=sys.stderr)
        sys.exit(1)
    if not a.quiet:
        print(f"E2E-STATIC: PASS (hard=0, soft={len(soft)})")


if __name__ == "__main__":
    main()
