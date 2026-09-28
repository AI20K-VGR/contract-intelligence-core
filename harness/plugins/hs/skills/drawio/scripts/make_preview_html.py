#!/usr/bin/env python3
"""Generate an offline-renderable HTML preview for a .drawio diagram.

Two tiers:
  Tier-0 (encode_drawio_url.py): browser URL, needs internet to load diagrams.net app.
  Tier-1 (this script): self-contained HTML with vendored GraphViewer — renders at
    file:// with no internet, no CLI, no login.

Usage:
  python3 make_preview_html.py input.drawio [-o output.html] [--vendor-dir PATH]

The script locates vendor/viewer.min.js relative to this script file by default.
Pass --vendor-dir to override the vendor directory (used in tests and air-gap setups).

Degrade: when viewer.min.js is not found, the HTML is still generated with a warning
comment and a CDN fallback URL in an HTML comment — the script exits 0.
"""
import argparse
import html
import json
import pathlib
import sys


_CDN_FALLBACK = "https://viewer.diagrams.net/js/viewer-static.min.js"

# Default vendor dir is one level up from this script's directory
_DEFAULT_VENDOR = pathlib.Path(__file__).resolve().parent.parent / "vendor"


def _read_drawio(path: pathlib.Path) -> str:
    """Read .drawio XML content."""
    try:
        return path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"Error reading {path}: {e}", file=sys.stderr)
        sys.exit(1)


def _find_viewer(vendor_dir: pathlib.Path) -> "pathlib.Path | None":
    """Return path to viewer.min.js if present in vendor_dir, else None."""
    candidate = vendor_dir / "viewer.min.js"
    return candidate if candidate.is_file() else None


def _viewer_relative_path(html_out: pathlib.Path, viewer: "pathlib.Path | None") -> "str | None":
    """Compute the relative path from the output HTML file to viewer.min.js."""
    if viewer is None:
        return None
    try:
        rel = viewer.relative_to(html_out.parent)
        return str(rel)
    except ValueError:
        # viewer is not under html_out.parent — use absolute path as fallback
        return str(viewer)


def generate_html(drawio_path: pathlib.Path, out_path: pathlib.Path,
                  vendor_dir: pathlib.Path) -> None:
    """Generate an offline-renderable HTML file from a .drawio input."""
    xml_content = _read_drawio(drawio_path)
    viewer = _find_viewer(vendor_dir)

    # Build the mxgraph JSON data attribute value — embed the raw XML
    mxgraph_data = json.dumps({"highlight": "#0000ff", "nav": True,
                               "resize": True, "toolbar": "zoom layers tags lightbox",
                               "edit": "_blank", "xml": xml_content})

    # Determine script source
    if viewer is not None:
        rel = _viewer_relative_path(out_path, viewer)
        script_tag = f'<script type="text/javascript" src="{html.escape(rel)}"></script>'
        vendor_note = ""
    else:
        # Degrade: use CDN fallback in a comment, inline warning in the page
        script_tag = (
            f'<!-- viewer.min.js not found; CDN fallback: {_CDN_FALLBACK} -->\n'
            f'    <!-- To use offline: place viewer.min.js in the vendor/ directory -->\n'
            f'    <script type="text/javascript" src="{_CDN_FALLBACK}"></script>'
        )
        vendor_note = (
            '<div style="color:orange;font-family:monospace;padding:8px;">'
            'Warning: vendored viewer.min.js not found. Using CDN fallback '
            '(requires internet). For air-gap use, place viewer.min.js in vendor/.'
            '</div>'
        )

    # Escape the JSON for an HTML attribute value
    escaped_data = html.escape(mxgraph_data, quote=True)

    page = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
  <title>{html.escape(drawio_path.stem)} — draw.io preview</title>
  <style>
    body {{ margin: 0; padding: 8px; font-family: sans-serif; }}
    .mxgraph {{ max-width: 100%; border: 1px solid #ccc; }}
  </style>
</head>
<body>
  {vendor_note}
  <div class="mxgraph" style="max-width:100%;border:1px solid transparent;"
       data-mxgraph="{escaped_data}"></div>
  {script_tag}
</body>
</html>
"""
    try:
        out_path.write_text(page, encoding="utf-8")
    except OSError as e:
        print(f"Error writing {out_path}: {e}", file=sys.stderr)
        sys.exit(1)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Generate an offline HTML preview for a .drawio file."
    )
    ap.add_argument("input", help="Path to the .drawio XML file")
    ap.add_argument("-o", "--output", help="Output HTML path (default: <input>.html)")
    ap.add_argument(
        "--vendor-dir",
        help="Directory containing viewer.min.js (default: ../vendor relative to this script)",
    )
    args = ap.parse_args(argv)

    src = pathlib.Path(args.input).resolve()
    if not src.exists():
        print(f"Error: input file not found: {src}", file=sys.stderr)
        return 1

    if args.output:
        out = pathlib.Path(args.output).resolve()
    else:
        out = src.with_suffix(".html")

    vendor_dir = pathlib.Path(args.vendor_dir).resolve() if args.vendor_dir else _DEFAULT_VENDOR

    generate_html(src, out, vendor_dir)
    print(f"Preview written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
