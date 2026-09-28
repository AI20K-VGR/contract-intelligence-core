"""ssg_engine.py — Generic static-site generator engine for docs hub.

Receives a Ctx (dataclass) carrying all theme-config and assembled assets; no
hardcoded brand strings here.  Callers (e.g. docs/showcase/build.py) build Ctx
then call engine.build(ctx, out_dir).

P3 extraction: ALL structural logic ripped from docs/showcase/build.py.
Theme-specific constants (brand, desc, favicon, lang-key, chrome, gen_banner)
travel via Ctx so the engine stays generic.

Page shell (head/body/banner/chrome) and the three repeated components that
vary per page (sidebar, footer links, prev/hub/next nav) are Jinja2 templates
— genuinely a loop-per-category/loop-per-page/if-prev-if-next need, and the
shell itself is a real `{% extends %}` base with 3 call sites (hub page,
per-guide page, portable single-file) overriding head_inject/header/content/
footer/script. autoescape is OFF (see _ENV below): every string flowing
through these templates is pre-formed HTML the caller already owns — real
partials, theme config carrying deliberate markup like `brand_html=
"SDLC&nbsp;Harness"` — so turning autoescaping on would double-escape live
markup, not close a hole (contrast harness/plugins/hs/skills/design/scripts/
cip/render-html.py, which DOES have unescaped user input and DOES set
autoescape=True). Everything else here (header_slim, crumb, placeholder_body
— single-shot string interpolation, no loop or conditional) is unchanged
Python; converting those would not have bought anything.
"""
from __future__ import annotations

import base64
import pathlib
import re
import shutil
from dataclasses import dataclass, field
from typing import Any

import jinja2

# ---------------------------------------------------------------------------
# Ctx — carries everything the engine needs (no global mutable state)
# ---------------------------------------------------------------------------

@dataclass
class Ctx:
    """All site-generation context; injected by the caller (thin theme-adapter)."""
    # Page/category data (from manifest)
    pages: list          # list of tuples (key, en, vi, partial_file, title, accent, empty)
    categories: list     # list of tuples (key, en, vi, [page_keys])
    page_index: dict     # key -> page tuple

    # Assembled asset bundles (strings)
    css: str
    js: str

    # Vendor filenames in load order (e.g. ["three.min.js", ...])
    vendor: list

    # Assets directory path (Path) — for vendor_links / vendor_inline
    assets_dir: pathlib.Path

    # Partials directory (Path) — page content fragments
    partials_dir: pathlib.Path

    # Footer pages: list of (key, vi, en)
    footer_pages: list

    # --- THEME CONFIG (injected; engine never hardcodes these) ---
    brand_html: str      # HTML for brand text in header (may include &nbsp; etc.)
    brand_name: str      # plain text brand name for og:site_name meta tag
    desc: str            # <meta description>
    favicon: str         # data URI or URL
    lang_storage_key: str  # localStorage key for language preference
    gen_banner: str      # HTML comment banner inserted into each page
    chrome_html: str     # decorative background HTML (glow divs + canvas)

    # FIX-22: diagram png source dir — portable single-file inlines <img> as base64.
    # None ⇒ no inlining (multipage keeps relative <img src>).
    diagram_dir: Any = None

    # Mode-neutral state (set during build, not by caller)
    _footer_tpl: str = field(default="", init=False)


# ---------------------------------------------------------------------------
# Jinja2 templates — page shell (extends/blocks) + the 3 loop/conditional
# components (sidebar, footer links, page nav). Whitespace control is by
# hand (`{%- -%}` per tag), not global trim_blocks/lstrip_blocks: a `{% block
# %}{% endblock %}` placeholder left at default settings reproduces the old
# `+ "\n" +` string-concat exactly (the surrounding template newlines are
# literal text, untouched), which global trim_blocks would eat.
# ---------------------------------------------------------------------------

_SHELL_TPL = """<!DOCTYPE html>
<html lang="vi" class="lang-vi">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<meta name="color-scheme" content="dark" />
<link rel="icon" href="{{ ctx.favicon }}" />
<style>html{background:#070b16}</style>
<noscript><style>.reveal{opacity:1!important;transform:none!important}</style></noscript>
<script>try{if(localStorage.getItem('{{ ctx.lang_storage_key }}')==='en'){var d=document.documentElement;d.classList.remove('lang-vi');d.classList.add('lang-en');d.lang='en';}}catch(e){}</script>
<title>{{ title }}</title>
<meta name="description" content="{{ ctx.desc }}" />
<meta property="og:type" content="website" />
<meta property="og:site_name" content="{{ ctx.brand_name }}" />
<meta property="og:title" content="{{ title }}" />
<meta property="og:description" content="{{ ctx.desc }}" />
<meta name="twitter:card" content="summary" />
<meta name="twitter:title" content="{{ title }}" />
<meta name="twitter:description" content="{{ ctx.desc }}" />
{% block head_inject %}{% endblock %}
</head>
<body class="{{ body_class }}">
{{ ctx.gen_banner }}
{{ ctx.chrome_html }}
{% block header %}{% endblock %}
{% block content %}{% endblock %}
{% block footer %}{% endblock %}
{% block script %}{% endblock %}
</body>
</html>
"""

_PAGE_TPL = """{% extends "_shell.html" %}
{% block head_inject %}{{ head_inject }}{% endblock %}
{% block header %}{{ header_html }}{% endblock %}
{% block content %}{{ content_html }}{% endblock %}
{% block footer %}{{ footer_html }}{% endblock %}
{% block script %}{{ script_inject }}{% endblock %}
"""

_SIDEBAR_TPL = """<aside class="docs-side" aria-label="Mục lục">
{%- for cat in categories %}
  <div class="side-cat"><span class="en">{{ cat.cen }}</span><span class="vi">{{ cat.cvi }}</span></div>
{%- for p in cat.pages %}
  <a href="{{ p.href }}" class="side-link{{ p.active_cls }}" data-nav="{{ p.key }}">{{ p.label }}</a>
{%- endfor %}
{%- endfor %}
</aside>"""

_FOOTER_LINKS_TPL = """{%- for f in pages -%}
{{ "\n      " if not loop.first else "" }}<a href="{{ f.href }}"><span class="vi">{{ f.vi }}</span><span class="en">{{ f.en }}</span></a>
{%- endfor -%}"""

_PAGE_NAV_TPL = """<div class="page-nav" style="--ac:{{ ac }}">
{%- if has_prev -%}
<a class="pv" href="{{ prev_href }}"><span class="k">← <span class="en">Prev</span><span class="vi">Trước</span></span><span class="v">{{ prev_label }}</span></a>
{%- else -%}
<span class="pv" style="flex:1"></span>
{%- endif -%}
{%- if show_hub -%}
<a class="hb" href="{{ hub_href }}"><span class="k"><span class="en">Overview</span><span class="vi">Tổng quan</span></span><span class="v">▦</span></a>
{%- endif -%}
{%- if has_next -%}
<a class="nx" href="{{ next_href }}"><span class="k"><span class="en">Next</span><span class="vi">Sau</span> →</span><span class="v">{{ next_label }}</span></a>
{%- else -%}
<span class="nx" style="flex:1"></span>
{%- endif -%}
</div>"""

_ENV = jinja2.Environment(
    loader=jinja2.DictLoader({
        "_shell.html": _SHELL_TPL,
        "_page.html": _PAGE_TPL,
        "_sidebar.html": _SIDEBAR_TPL,
        "_footer_links.html": _FOOTER_LINKS_TPL,
        "_page_nav.html": _PAGE_NAV_TPL,
    }),
    autoescape=False,
    keep_trailing_newline=True,
)


# ---------------------------------------------------------------------------
# Asset helpers
# ---------------------------------------------------------------------------

def vendor_links(ctx: Ctx, asset_prefix: str) -> str:
    """<script src> tags for the multipage build."""
    return "\n".join(
        '<script src="%sassets/lib/%s"></script>' % (asset_prefix, v)
        for v in ctx.vendor
    )


_IMG_SRC_RE = re.compile(r'(<img\b[^>]*\bsrc=")([^"]+)("[^>]*>)', re.IGNORECASE)


def _inline_imgs(ctx: Ctx, html: str) -> str:
    """FIX-22: portable single-file — <img src=...diagram/png/X> → data:base64 từ ctx.diagram_dir.
    Bỏ qua (giữ nguyên) nếu diagram_dir None, src không phải diagram/png, hoặc file thiếu."""
    if not ctx.diagram_dir:
        return html

    def sub(m):
        mm = re.search(r"diagram/png/(.+)$", m.group(2))
        if not mm:
            return m.group(0)
        png = ctx.diagram_dir / mm.group(1)
        if not png.is_file():
            return m.group(0)
        b64 = base64.b64encode(png.read_bytes()).decode("ascii")
        return f"{m.group(1)}data:image/png;base64,{b64}{m.group(3)}"
    return _IMG_SRC_RE.sub(sub, html)


def vendor_inline(ctx: Ctx) -> str:
    """Each vendored lib inlined verbatim — for the portable single file."""
    return "\n".join(
        "<script>\n" + (ctx.assets_dir / "lib" / v).read_text(encoding="utf-8") + "\n</script>"
        for v in ctx.vendor
    )


# ---------------------------------------------------------------------------
# Partial reader
# ---------------------------------------------------------------------------

def _read_partial(ctx: Ctx, name: str) -> str:
    fp = ctx.partials_dir / name
    return fp.read_text(encoding="utf-8") if fp.exists() else f"<!-- missing partial: {name} -->"


# ---------------------------------------------------------------------------
# Cross-page link resolution
# ---------------------------------------------------------------------------

_LINK_RE = re.compile(r"@([a-z0-9-]+)@")


def resolve_links(ctx: Ctx, text: str, mode: str, nav_rel: str) -> str:
    return _LINK_RE.sub(
        lambda m: _href(ctx, m.group(1), mode, nav_rel) if m.group(1) in ctx.page_index else m.group(0),
        text,
    )


# ---------------------------------------------------------------------------
# Navigation helpers
# ---------------------------------------------------------------------------

def _label(ctx: Ctx, key: str) -> str:
    """Bilingual nav label span for a page key."""
    p = ctx.page_index[key]
    return f'<span class="en">{p[1]}</span><span class="vi">{p[2]}</span>'


def _href(ctx: Ctx, key: str, mode: str, nav_rel: str) -> str:
    """href: #hash in single-file mode, real path in multipage."""
    if mode == "single":
        return "#" + key
    if key == "hub":
        return nav_rel + "index.html"
    return nav_rel + "pages/" + key + ".html"


def _category_of(ctx: Ctx, key: str):
    """(en, vi) category labels for a page key."""
    for _ck, cen, cvi, keys in ctx.categories:
        if key in keys:
            return cen, cvi
    return "", ""


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

def footer_links(ctx: Ctx, mode: str, nav_rel: str) -> str:
    """Generate the footer 'Pages' links."""
    pages = [{"href": _href(ctx, key, mode, nav_rel), "vi": vi, "en": en}
             for key, vi, en in ctx.footer_pages]
    return _ENV.get_template("_footer_links.html").render(pages=pages)


# ---------------------------------------------------------------------------
# Layout components
# ---------------------------------------------------------------------------

def header_slim(ctx: Ctx, mode: str, nav_rel: str) -> str:
    """Slim top header: menu toggle + brand + EN/VI toggle."""
    home = ("#hub" if mode == "single" else nav_rel + "index.html")
    return (
        '<a class="skip-link" href="#main-content"><span class="vi">Bỏ qua tới nội dung</span>'
        '<span class="en">Skip to content</span></a>\n'
        '<nav class="app-header">\n  <div class="nav-in">\n'
        '    <button class="side-toggle" type="button" data-side-toggle aria-label="Menu" aria-expanded="false">'
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">'
        '<path d="M3 6h18M3 12h18M3 18h18"/></svg></button>\n'
        f'    <a href="{home}" class="brand"><span class="dot"></span>'
        f'<span>{ctx.brand_html}</span></a>\n'
        '    <button class="nav-search" type="button" data-search-open aria-label="Tìm kiếm / Search" title="Tìm kiếm (⌘/Ctrl-K)">'
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">'
        '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>'
        '<span class="ns-lab"><span class="vi">Tìm kiếm</span><span class="en">Search</span></span>'
        '<span class="ns-k">⌘K</span></button>\n'
        '    <div class="langtoggle" role="group" aria-label="language">\n'
        f'      <button id="btn-en" type="button" onclick="setLang(\'en\')">EN</button>\n'
        f'      <button id="btn-vi" type="button" onclick="setLang(\'vi\')">VI</button>\n'
        '    </div>\n  </div>\n</nav>'
    )


def sidebar(ctx: Ctx, active: str, mode: str, nav_rel: str) -> str:
    """Left docs menu bar — page links grouped by categories."""
    categories = []
    for _ck, cen, cvi, keys in ctx.categories:
        pages = [{
            "href": _href(ctx, k, mode, nav_rel),
            "active_cls": " active" if k == active else "",
            "key": k,
            "label": _label(ctx, k),
        } for k in keys]
        categories.append({"cen": cen, "cvi": cvi, "pages": pages})
    return _ENV.get_template("_sidebar.html").render(categories=categories)


def crumb(ctx: Ctx, key: str, nav_rel: str) -> str:
    home = nav_rel + "index.html"
    return (
        f'<div class="crumb"><a href="{home}"><span class="en">Home</span>'
        f'<span class="vi">Trang chủ</span></a> '
        f'<span class="sep">›</span> <span class="cur">{_label(ctx, key)}</span></div>'
    )


def page_nav(ctx: Ctx, key: str, mode: str, nav_rel: str) -> str:
    """Generated prev · hub · next footer nav."""
    idx = next(i for i, p in enumerate(ctx.pages) if p[0] == key)
    ac = ctx.pages[idx][5]

    def href(k: str) -> str:
        return _href(ctx, k, mode, nav_rel)

    prev = ctx.pages[idx - 1] if idx > 0 else None
    nxt = ctx.pages[idx + 1] if idx + 1 < len(ctx.pages) else None
    return _ENV.get_template("_page_nav.html").render(
        ac=ac,
        has_prev=prev is not None,
        prev_href=href(prev[0]) if prev else "",
        prev_label=_label(ctx, prev[0]) if prev else "",
        show_hub=key != "hub",
        hub_href=href("hub"),
        has_next=nxt is not None,
        next_href=href(nxt[0]) if nxt else "",
        next_label=_label(ctx, nxt[0]) if nxt else "",
    )


def placeholder_body(ctx: Ctx, key: str) -> str:
    """Bilingual 'đang cập nhật' placeholder for an EMPTY page."""
    cen, cvi = _category_of(ctx, key)
    return (
        '<header class="hero">\n  <div class="wrap reveal">\n'
        f'    <div class="eyebrow"><span class="vi">{cvi}</span><span class="en">{cen}</span></div>\n'
        f'    <h1>{_label(ctx, key)}</h1>\n'
        '    <p class="lead"><span class="vi">Trang đang được biên soạn — chưa có nội dung. '
        'Sẽ được bổ sung sau (chắt lọc từ tài liệu kiến trúc gốc, không sao chép nguyên file).</span>'
        '<span class="en">This page is being prepared — no content yet. It will be added later '
        '(distilled from the source architecture docs, not a wholesale copy).</span></p>\n'
        '  </div>\n</header>\n'
        '<section>\n  <div class="wrap reveal">\n'
        '    <div class="banner">\n'
        '      <h3><span class="pin"></span><span class="vi">Đang cập nhật</span><span class="en">Coming soon</span></h3>\n'
        '      <p class="faint" style="margin:6px 0 0"><span class="vi">Chưa có nội dung cho mục này.</span>'
        '<span class="en">No content for this section yet.</span></p>\n'
        '    </div>\n  </div>\n</section>'
    )


def page_body(ctx: Ctx, key: str, mode: str, nav_rel: str) -> str:
    """Page content = real partial (or placeholder if EMPTY) + generated prev/next nav."""
    _k, _en, _vi, pf, _t, _ac, empty = ctx.page_index[key]
    body = placeholder_body(ctx, key) if empty else resolve_links(ctx, _read_partial(ctx, pf), mode, nav_rel)
    return body + '\n<div class="wrap">' + page_nav(ctx, key, mode, nav_rel) + "</div>"


def docs_layout(ctx: Ctx, active: str, mode: str, nav_rel: str, main_inner: str) -> str:
    """Guide layout: scrim + grid(sidebar | main | TOC)."""
    return (
        '<div class="scrim" data-scrim></div>\n'
        '<div class="docs-layout">\n'
        + sidebar(ctx, active, mode, nav_rel) + "\n"
        + '<main class="docs-main" id="main-content" tabindex="-1">\n' + main_inner + "\n</main>\n"
        + '<nav class="toc" data-toc aria-label="On this page"></nav>\n'
        + "</div>"
    )


# ---------------------------------------------------------------------------
# HTML shell
# ---------------------------------------------------------------------------

def shell(ctx: Ctx, title: str, head_inject: str, body_cls: str, header_html: str,
          content_html: str, footer: str, script_inject: str) -> str:
    """Full HTML document — `_page.html` `{% extends %}`s `_shell.html`; the 3
    build() call sites (hub, per-guide page, single-file) each override
    head_inject/header/content/footer/script, sharing the doctype/meta/banner/
    chrome shell exactly once."""
    return _ENV.get_template("_page.html").render(
        ctx=ctx, title=title, body_class=body_cls,
        head_inject=head_inject, header_html=header_html,
        content_html=content_html, footer_html=footer, script_inject=script_inject,
    )


# ---------------------------------------------------------------------------
# Main build entry point
# ---------------------------------------------------------------------------

def build(ctx: Ctx, out_dir: pathlib.Path) -> list:
    """Generate the full docs site into out_dir.

    Returns list of written paths (relative to out_dir).
    """
    footer_tpl = _read_partial(ctx, "_footer.html")
    written = []

    # Rebuild the generated site dir from scratch, then copy assets verbatim.
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True)
    shutil.copytree(ctx.assets_dir, out_dir / "assets",
                    ignore=shutil.ignore_patterns("js", "css"))
    (out_dir / "assets" / "showcase.css").write_text(ctx.css, encoding="utf-8")
    (out_dir / "assets" / "showcase.js").write_text(ctx.js, encoding="utf-8")

    # ---------- multipage: hub (index.html, view-home, no sidebar) ----------
    link = '<link rel="stylesheet" href="assets/showcase.css" />'
    script = vendor_links(ctx, "") + '\n<script src="assets/showcase.js"></script>'
    footer = footer_tpl.replace("{FOOTER_LINKS}", footer_links(ctx, "multi", ""))
    hub_main = '<main id="main-content" tabindex="-1">\n' + page_body(ctx, "hub", "multi", "") + "\n</main>"
    out = shell(ctx, ctx.page_index["hub"][4], link, "view-home",
                header_slim(ctx, "multi", ""), hub_main, footer, script)
    (out_dir / "index.html").write_text(out, encoding="utf-8")
    written.append("index.html")

    # ---------- multipage: pages/<k>.html (view-guide, sidebar) ----------
    (out_dir / "pages").mkdir(exist_ok=True)
    link2 = '<link rel="stylesheet" href="../assets/showcase.css" />'
    script2 = vendor_links(ctx, "../") + '\n<script src="../assets/showcase.js"></script>'
    footer2 = footer_tpl.replace("{FOOTER_LINKS}", footer_links(ctx, "multi", "../"))
    for key, en, vi, pf, title, ac, empty in ctx.pages[1:]:
        content = crumb(ctx, key, "../") + "\n" + docs_layout(ctx, key, "multi", "../",
                                                               page_body(ctx, key, "multi", "../"))
        out = shell(ctx, title, link2, "view-guide",
                    header_slim(ctx, "multi", "../"), content, footer2, script2)
        (out_dir / "pages" / (key + ".html")).write_text(out, encoding="utf-8")
        written.append(f"pages/{key}.html")

    # ---------- portable single file (one docs-layout, router toggles view) ----------
    style_inline = "<style>\n" + ctx.css + "\n</style>"
    script_inline = vendor_inline(ctx) + "\n<script>\n" + ctx.js + "\n</script>"
    footer_single = footer_tpl.replace("{FOOTER_LINKS}", footer_links(ctx, "single", ""))
    panels = []
    for key, en, vi, pf, title, ac, empty in ctx.pages:
        body = _inline_imgs(ctx, page_body(ctx, key, "single", ""))
        panels.append(f'<div class="route" data-route="{key}">\n{body}\n</div>')
    content_single = docs_layout(ctx, "hub", "single", "", "\n".join(panels))
    out = shell(ctx, ctx.page_index["hub"][4], style_inline, "view-home",
                header_slim(ctx, "single", ""), content_single, footer_single, script_inline)
    (out_dir / "vsf-aio-platform-showcase.html").write_text(out, encoding="utf-8")
    written.append("vsf-aio-platform-showcase.html")

    return written
