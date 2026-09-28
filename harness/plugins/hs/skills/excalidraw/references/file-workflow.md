# File-based workflow

Generate `.excalidraw` JSON files directly on disk — no server required; PNG render via Playwright optional (see Render section).

---

## Step 1: Design

See SKILL.md — assess depth, map concept to pattern, plan layout.

## Step 2: Generate JSON

Create the `.excalidraw` file with the standard wrapper — see `json-schema.md` § File wrapper for the exact structure.

Element templates: `element-templates.md`. Colors: `color-palette.md`.

## Step 3: Large diagram -- section-by-section

**Important**: build JSON one section at a time — output token limit blocks a single-pass full file.

1. Create the base file with wrapper + first section
2. Add one section per edit
3. Use descriptive IDs: `"trigger_rect"`, `"arrow_fan_left"`
4. Namespace seeds by section — see `json-schema.md` § Seed namespacing for the range table
5. Update cross-section bindings as sections are added

## Step 4: Validate JSON

Review directly:
- Cross-section arrows bound correctly on both ends?
- Spacing balanced?
- Every ID references an element that actually exists?

---

## Render to PNG (optional)

If a PNG image is needed, use Playwright + headless Chromium.

### Setup (first time)

```bash
pip install playwright
playwright install chromium
```

### Render script

Create `render_excalidraw.py` in the working directory:

```python
"""Render Excalidraw JSON to PNG via headless Chromium."""
import argparse, json, sys
from pathlib import Path

TEMPLATE_HTML = """<!DOCTYPE html>
<html>
<head>
  <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
  <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
  <script src="https://unpkg.com/@excalidraw/excalidraw/dist/excalidraw.production.min.js"></script>
  <style>html,body,#root{margin:0;padding:0;width:__WIDTH__px;height:__HEIGHT__px;overflow:hidden;}</style>
</head>
<body>
  <div id="root"></div>
  <script>
    const data = __DATA__;
    const App = () => React.createElement(ExcalidrawLib.Excalidraw, {
      initialData: data,
      viewModeEnabled: true,
      zenModeEnabled: true,
    });
    ReactDOM.render(React.createElement(App), document.getElementById('root'));
  </script>
</body>
</html>"""

def render(src: Path, out: Path, scale: int = 2, width: int = 1920):
    from playwright.sync_api import sync_playwright
    data = json.loads(src.read_text())
    height = 1080
    html = (TEMPLATE_HTML
            .replace("__DATA__", json.dumps(data))
            .replace("__WIDTH__", str(width))
            .replace("__HEIGHT__", str(height)))
    html_path = src.with_suffix(".html")
    html_path.write_text(html)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height},
                                device_scale_factor=scale)
        page.goto(f"file://{html_path.resolve()}")
        page.wait_for_timeout(2000)
        page.screenshot(path=str(out), full_page=False)
        browser.close()
    html_path.unlink()
    print(f"Rendered: {out}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--output")
    ap.add_argument("--scale", type=int, default=2)
    ap.add_argument("--width", type=int, default=1920)
    args = ap.parse_args()
    src = Path(args.src)
    out = Path(args.output) if args.output else src.with_suffix(".png")
    render(src, out, args.scale, args.width)
```

Run:
```bash
python render_excalidraw.py diagram.excalidraw [--output diagram.png] [--scale 2] [--width 1920]
```

Then use the **Read tool** on the PNG file to inspect the result — see SKILL.md Step 4 (Validate & fix) for the audit checklist.

---

## Technical constraints

- `fontFamily: 3` (monospace) always — see `json-schema.md` for the full attribute table
- `opacity: 100` for every element
- `roughness: 0` for modern look (unless hand-drawn is needed)
- `strokeWidth: 2` standard
- Arrow curve: use 3+ points in the `points` array
- Rounded rectangle: `"roundness": {"type": 3}`
