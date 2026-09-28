#!/usr/bin/env python3
"""build_pack.py — build a base64 icon pack from packs/<name>/manifest.json → catalog/<name>.json.

Each manifest icon resolves a square tile one of five ways:
  - "file": <path>           → vendored local SVG/PNG (highest priority, network-free)
  - "devicon": <slug>        → authentic full-colour logo from devicon CDN
  - "url": <svg url>          → embed the SVG AS-IS (coloured logo, e.g. Databricks)
  - "slug": <simple-icons slug> → monochrome glyph on brand-colour square
  - neither                   → coloured text tile (fallback) using "abbr" or "label"

Rasterization: cairosvg (cross-platform, optional) replaces upstream qlmanage
(macOS-only). Without cairosvg, tiles are embedded as SVG data-URIs; with it,
they are rasterized to PNG first (smaller, draw.io-compatible). Regen still
needs network for devicon/simple-icons fetch — only file: icons are offline.

catalog/*.json packs are merged by core.loadCatalog/shapesearch, making icons
searchable alongside official stencils.

Source: drawio-ai-kit@bda82a2 (sparklabx, MIT)
Ported with cairosvg rasterize adaptation. Usage:
  python3 scripts/build_pack.py <pack>   (default: bigdata)
"""
import sys, json, base64, re, shutil, subprocess, tempfile
import httpx
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIMPLE_ICONS = "https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/{}.svg"
DEVICON = "https://raw.githubusercontent.com/devicons/devicon/master/icons/{n}/{n}-{v}.svg"
STYLE = ("sketch=0;html=1;outlineConnect=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;"
         "fontColor=#232F3E;aspect=fixed;shape=image;image={};")


def fetch(url):
    # follow_redirects: the raw.githubusercontent sources 30x to a CDN host, and
    # unlike urllib httpx does not follow by default — without it every fetch
    # returns an empty 302 body and the pack silently rebuilds as blank.
    for _ in range(3):
        try:
            r = httpx.get(url, timeout=25, follow_redirects=True,
                          headers={"User-Agent": "drawio-ai-kit"})
            if r.status_code == 200:
                # not r.text: that decodes with the server-declared charset, and the
                # original pinned utf-8 regardless of what the header claims.
                return r.content.decode("utf-8", "replace")
        except Exception:
            pass
    return None


def fg(color):
    c = color.lstrip("#")
    if len(c) != 6:
        return "#ffffff"
    r, g, b = (int(c[i:i + 2], 16) for i in (0, 2, 4))
    lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
    return "#232F3E" if lum > 0.6 else "#ffffff"


def tile_logo(color, paths):
    inner = "".join(f'<path d="{d}"/>' for d in paths)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
            f'<rect width="64" height="64" fill="{color}"/>'
            f'<g transform="translate(14 14) scale(1.5)" fill="{fg(color)}">{inner}</g></svg>')


def tile_text(color, text):
    fs = 18 if len(text) <= 3 else (13 if len(text) <= 6 else 10)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
            f'<rect width="64" height="64" fill="{color}"/>'
            f'<text x="32" y="33" font-family="Arial,Helvetica,sans-serif" font-size="{fs}" font-weight="700" '
            f'fill="{fg(color)}" text-anchor="middle" dominant-baseline="central">{text}</svg>')


def _inner_and_viewbox(svg):
    m = re.search(r"<svg\b([^>]*)>(.*)</svg>", svg, flags=re.S)
    attrs, body = (m.group(1), m.group(2)) if m else ("", svg)
    vb = re.search(r'viewBox="([^"]+)"', attrs)
    if vb:
        vb = vb.group(1)
    else:
        w, h = re.search(r'\bwidth="([\d.]+)', attrs), re.search(r'\bheight="([\d.]+)', attrs)
        vb = f"0 0 {w.group(1)} {h.group(1)}" if w and h else "0 0 24 24"
    ns = " ".join(re.findall(r'xmlns:[\w-]+="[^"]*"', attrs))
    return body, vb, ns


def as_is(svg):
    head = svg.split(">", 1)[0]
    if "xmlns" not in head:
        svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    return svg


def tile_framed(logo_svg):
    body, vb, ns = _inner_and_viewbox(logo_svg)
    return ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 64 64">'
            '<rect x="0.75" y="0.75" width="62.5" height="62.5" fill="#FFFFFF" stroke="#E1E5EA" stroke-width="1.5"/>'
            f'<svg {ns} x="10" y="10" width="44" height="44" viewBox="{vb}" preserveAspectRatio="xMidYMid meet">{body}</svg>'
            '</svg>')


def png_tile(png_bytes, framed=True):
    b64 = base64.b64encode(png_bytes).decode("ascii")
    rect = ('<rect x="0.75" y="0.75" width="62.5" height="62.5" fill="#FFFFFF" stroke="#E1E5EA" stroke-width="1.5"/>'
            if framed else "")
    x, wh = (10, 44) if framed else (2, 60)
    return ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 64 64">'
            f'{rect}<image x="{x}" y="{x}" width="{wh}" height="{wh}" preserveAspectRatio="xMidYMid meet" '
            f'xlink:href="data:image/png;base64,{b64}"/></svg>')


def rasterize(svg, size=256):
    """Rasterize SVG tile to PNG via cairosvg (cross-platform optional dep).

    Replaces upstream qlmanage (macOS-only). Without cairosvg, tiles remain
    SVG data-URIs (functional but larger).
    """
    try:
        import cairosvg
    except ImportError:
        sys.stderr.write("build_pack: cairosvg not installed — SVG tiles will not be rasterized.\n"
                         "  pip install cairosvg\n")
        return None
    try:
        return cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=size, output_height=size)
    except Exception as exc:
        sys.stderr.write(f"build_pack: rasterize failed: {exc}\n")
        return None


def data_uri(svg):
    # drawio splits style tokens on ";", so the usual "data:image/png;base64," breaks the image=
    # value. drawio's own convention drops ";base64" — "data:image/<type>,<base64>" (comma) — and
    # assumes base64. Match it.
    png = rasterize(svg)
    if png:
        return "data:image/png," + base64.b64encode(png).decode("ascii")
    return "data:image/svg+xml," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def main(pack):
    man = json.loads((ROOT / "packs" / pack / "manifest.json").read_text())
    icons = []
    for t in man["icons"]:
        svg = src = None
        # frame:false → embed the logo as-is (for logos that are already a full-bleed square, e.g. ClickHouse)
        wrap = as_is if t.get("frame") is False else tile_framed
        # 0) vendored local asset (PNG/SVG under packs/<pack>/), highest priority — user-supplied exact logo
        if t.get("file"):
            fp = ROOT / "packs" / pack / t["file"]
            if fp.is_file():
                if fp.suffix.lower() == ".svg":
                    svg, src = wrap(fp.read_text()), "file"
                else:
                    svg, src = png_tile(fp.read_bytes(), framed=t.get("frame") is not False), "file"
        # 1) devicon: authentic full-colour symbol → white square tile (or as-is if frame:false)
        if svg is None and t.get("devicon"):
            for v in ("original", "plain"):
                raw = fetch(DEVICON.format(n=t["devicon"], v=v))
                if raw:
                    svg, src = wrap(raw), "devicon"
                    break
        # 2) explicit full-colour logo URL
        if svg is None and t.get("url"):
            raw = fetch(t["url"])
            if raw:
                svg, src = wrap(raw), "asis"
        # 3) simple-icons monochrome glyph → contrast colour on a brand-colour tile
        if svg is None and t.get("slug"):
            raw = fetch(SIMPLE_ICONS.format(t["slug"]))
            if raw:
                svg, src = tile_logo(t["color"], re.findall(r'<path[^>]*\bd="([^"]+)"', raw)), "logo"
        # 4) coloured text tile (last resort)
        if svg is None:
            svg, src = tile_text(t.get("color", "#5A6B7B"), t.get("abbr", t["label"])), "text"
        icons.append({
            "name": t["name"], "label": t["label"], "category": man.get("category", "Big Data"),
            "color": t.get("color", "#5A6B7B"), "w": 48, "h": 48,
            "tags": t.get("tags", t["label"].lower()), "style": STYLE.format(data_uri(svg)), "src": src,
        })
    out = {"meta": {"pack": pack, "source": man.get("note", ""),
                    "generator": "scripts/build_pack.py (cairosvg rasterize, ported from drawio-ai-kit@bda82a2)"},
           "categoryColors": {}, "groups": [], "icons": icons}
    (ROOT / "catalog" / f"{pack}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"wrote catalog/{pack}.json ({len(icons)} icons: {dict(Counter(i['src'] for i in icons))})")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "bigdata")
