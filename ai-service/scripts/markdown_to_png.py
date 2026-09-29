"""Render a Markdown report to PNG: one image per '## ' section and one of the whole report.

Each section is laid out as an HTML page (bordered tables, right-aligned number columns,
Vietnamese text) and captured by headless Chrome or Edge, so no browser library is needed.
Section images suit chat and slides, which shrink or crop a very tall image.

    uv run --with markdown-it-py python scripts/markdown_to_png.py \\
        reports/benchmark/test-contract/report.md --out reports/benchmark/test-contract/images

The browser is --browser, else the CHROME_PATH environment variable, else a usual
Chrome or Edge install.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
import unicodedata
from pathlib import Path

from PIL import Image

WIDTH_CSS = 1280
# Tall enough for any single section; the blank tail is cropped off.
HEIGHT_CSS = 7000
BACKGROUND = (255, 255, 255)
_BROWSERS = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome",
    "chromium",
    "chromium-browser",
    "microsoft-edge",
)

CSS = """
:root { color-scheme: light; }
html, body { margin: 0; background: #ffffff; }
body {
  font-family: "Segoe UI", system-ui, -apple-system, Roboto, Arial, sans-serif;
  font-size: 15px; line-height: 1.55; color: #1f2328;
}
main { max-width: 1180px; margin: 0 auto; padding: 36px 44px 8px; }
h1 { font-size: 26px; margin: 0 0 14px; padding-bottom: 10px; border-bottom: 2px solid #d0d7de; }
h2 { font-size: 20px; margin: 8px 0 14px; padding-bottom: 6px; border-bottom: 1px solid #d8dee4;
     color: #0b3d91; }
p, ul { margin: 0 0 14px; }
li { margin: 3px 0; }
strong { color: #0f172a; }
code {
  font-family: "Cascadia Mono", Consolas, "Courier New", monospace; font-size: 12.5px;
  background: #eff2f5; border-radius: 4px; padding: 1px 5px;
  white-space: pre-wrap; word-break: break-word;
}
table { width: 100%; border-collapse: collapse; margin: 0 0 18px; font-size: 13.5px; }
th, td { border: 1px solid #d0d7de; padding: 6px 10px; vertical-align: top; }
th { background: #f3f6f9; font-weight: 600; }
tbody tr:nth-child(even) td { background: #fafbfc; }
td[style*="right"], th[style*="right"] { font-variant-numeric: tabular-nums; white-space: nowrap; }
"""


def slug(text: str) -> str:
    """ASCII file-name part of a (Vietnamese) heading."""
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    keep = "".join(c if c.isalnum() else "-" for c in text.lower())
    return "-".join(part for part in keep.split("-") if part)[:40]


def sections(markdown: str) -> list[tuple[str, str]]:
    """(title, markdown) of every '## ' section; the '# ' title and intro join the first one."""
    chunks: list[list[str]] = [[]]
    for line in markdown.splitlines():
        if line.startswith("## ") and any(row.startswith("## ") for row in chunks[-1]):
            chunks.append([])
        chunks[-1].append(line)
    return [
        (
            next((row[3:].strip() for row in chunk if row.startswith("## ")), "report"),
            "\n".join(chunk),
        )
        for chunk in chunks
    ]


def to_html(markdown: str) -> str:
    # Imported here so the module loads without it: uv run --with markdown-it-py
    from markdown_it import MarkdownIt

    body = MarkdownIt("commonmark", {"html": True}).enable("table").render(markdown)
    return (
        '<!doctype html><html lang="vi"><head><meta charset="utf-8">'
        f"<style>{CSS}</style></head><body><main>{body}</main></body></html>"
    )


def find_browser(explicit: str | None) -> str:
    for candidate in (explicit, os.environ.get("CHROME_PATH"), *_BROWSERS):
        if not candidate:
            continue
        found = candidate if Path(candidate).is_file() else shutil.which(candidate)
        if found:
            return found
    raise SystemExit("Chrome or Edge not found: pass --browser or set CHROME_PATH")


def screenshot(browser: str, page: Path, target: Path, profile: Path, scale: int) -> None:
    """Capture ``page`` into ``target``, cropping the blank space below the content."""
    subprocess.run(
        [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--no-first-run",
            "--no-default-browser-check",
            f"--user-data-dir={profile}",
            f"--force-device-scale-factor={scale}",
            f"--window-size={WIDTH_CSS},{HEIGHT_CSS}",
            f"--screenshot={target}",
            page.resolve().as_uri(),
        ],
        check=True,
        capture_output=True,
        timeout=120,
    )
    image = Image.open(target).convert("RGB")
    width, height = image.size
    pixels = image.load()
    bottom = height - 1
    while bottom > 0 and all(pixels[x, bottom] == BACKGROUND for x in range(0, width, 4)):
        bottom -= 1
    image.crop((0, 0, width, min(height, bottom + 48 * scale))).save(target, optimize=True)


def render(report: Path, out_dir: Path, browser: str, scale: int = 2) -> list[Path]:
    """Write one PNG per section and one of the whole report; return their paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    parts = []
    # The browser can still hold its profile for a moment after it exits.
    with tempfile.TemporaryDirectory(prefix="md2png-", ignore_cleanup_errors=True) as tmp:
        work = Path(tmp)
        for index, (title, chunk) in enumerate(sections(report.read_text(encoding="utf-8")), 1):
            page = work / f"{index:02d}.html"
            page.write_text(to_html(chunk), encoding="utf-8")
            target = out_dir / f"{report.stem}-{index:02d}-{slug(title)}.png"
            screenshot(browser, page, target, work / "profile", scale)
            parts.append(target)
    images = [Image.open(path) for path in parts]
    whole = Image.new("RGB", (images[0].width, sum(i.height for i in images)), BACKGROUND)
    top = 0
    for image in images:
        whole.paste(image, (0, top))
        top += image.height
    full = out_dir / f"{report.stem}.png"
    whole.save(full, optimize=True)
    return [*parts, full]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("report", type=Path, help="Markdown file")
    parser.add_argument("--out", type=Path, help="default: an images/ folder next to the report")
    parser.add_argument("--browser", help="Chrome or Edge executable")
    parser.add_argument("--scale", type=int, default=2, help="device pixel ratio (default 2)")
    args = parser.parse_args()
    report = args.report.resolve()
    out = (args.out or report.parent / "images").resolve()
    for path in render(report, out, find_browser(args.browser), args.scale):
        print(path)


if __name__ == "__main__":
    main()
