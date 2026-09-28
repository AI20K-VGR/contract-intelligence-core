# Export — hs:drawio

Full guide to the export CLI, flags, PNG repair, and browser fallback.

## Two export modes

| Mode | Step | Flag `-e` | File name | Purpose |
|---|---|---|---|---|
| Preview / self-check | Step 4 | **NO** | `diagram.png` | Readable by the Vision API; `-e` produces a truncated IEND |
| Final / deliverable | Step 7 | **YES** | `diagram.drawio.png` | Embedded XML, file stays editable |

## CLI commands

```bash
# Preview PNG — NO -e, width-capped
drawio -x -f png --width 2000 -o diagram.png input.drawio

# Final PNG — WITH -e, double extension
drawio -x -f png -e -s 2 -o diagram.drawio.png input.drawio

# Repair IEND (required after every -e PNG export)
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/drawio/scripts/repair_png.py diagram.drawio.png

# SVG (final — -e is safe; SVG is text)
drawio -x -f svg -e -o diagram.svg input.drawio

# PDF (final)
drawio -x -f pdf -e -o diagram.pdf input.drawio

# macOS full path
/Applications/draw.io.app/Contents/MacOS/draw.io -x -f png --width 2000 -o diagram.png input.drawio

# Linux headless (requires xvfb-run)
export HOME=${HOME:-/tmp}
xvfb-run -a --server-args="-screen 0 1280x1024x24" \
  drawio -x -f png -e -s 2 -o diagram.drawio.png input.drawio --disable-gpu
# Root/CI: add --no-sandbox at the END (put earlier and drawio reads it as the input filename)
```

## Key flags

| Flag | Meaning |
|---|---|
| `-x` | Export mode (required) |
| `-f png/svg/pdf/jpg` | Format |
| `-e` | Embed diagram XML (PNG/SVG/PDF); skip at step 4 preview |
| `--width <px>` | Target width (use `--width 2000` for preview; do not combine with `-s` at the preview step — `-s` is for the final export step only) |
| `-s 1/2/3` | Scale (2 = final PNG; not used for preview) |
| `-o <path>` | Output file; `mkdir -p` the target dir first |
| `-b <n>` | Border width (default 0; recommend 10) |
| `-t` | Transparent background (PNG only) |
| `--page-index 0` | Export a specific page (default: all) |

## Repair PNG — repair_png.py

The draw.io CLI truncates the IEND chunk on `-e` PNG exports: the file ends with the 4-byte IEND length field but is missing the 8 bytes of `IEND` type + CRC. The Vision API and strict PNG decoders reject it with a 400. SVG/PDF are unaffected.

```bash
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/drawio/scripts/repair_png.py diagram.drawio.png
```

The script has an `endswith(IEND)` guard — idempotent, safe to run unconditionally.

## Browser fallback (no CLI needed)

```bash
# Read-only viewer URL
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/drawio/scripts/encode_drawio_url.py input.drawio

# Editable editor URL
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/drawio/scripts/encode_drawio_url.py --edit input.drawio
```

Encodes the XML into the URL fragment (`#R...`) — the fragment is never sent to a server, so no data is uploaded. `encodeURIComponent` is required: without it, a diagram containing `%` or CJK characters makes the browser throw "URI malformed".

Open URL: `open "$URL"` (macOS) / `xdg-open "$URL"` (Linux).
WSL2/Windows: `cmd.exe` drops the fragment → create a `.url` shortcut file instead (see `references/troubleshooting.md`).

## Offline preview (no CLI, no internet)

```bash
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/drawio/scripts/make_preview_html.py input.drawio
```

Generates `input.html` with the XML embedded plus a vendored GraphViewer. Open via `file://` to render offline. Details → `references/preview.md`.

## Fallback chain

| Scenario | Behavior |
|---|---|
| draw.io CLI missing, Python available | Browser fallback (encode_drawio_url.py) |
| draw.io CLI missing, Python missing | Generate `.drawio` XML only; guide the user to open it manually |
| macOS sandbox isolation | CLI unavailable; browser fallback / XML-only; ask user to run the CLI outside the sandbox |
| Vision unavailable | Skip self-check (step 5); show the PNG directly |
| Linux headless export fail | Try in order: xvfb-run → --no-sandbox (root) → --disable-gpu → tomkludy/drawio-renderer Docker |
| Linux headless missing deps | Install: `apt install libgtk-3-0 libnotify4 libnss3 libgbm1 libasound2t64 xvfb` |

## Check the binary on PATH

```bash
if command -v drawio &>/dev/null; then
  DRAWIO="drawio"
elif command -v draw.io &>/dev/null; then
  DRAWIO="draw.io"
elif [ -f "/Applications/draw.io.app/Contents/MacOS/draw.io" ]; then
  DRAWIO="/Applications/draw.io.app/Contents/MacOS/draw.io"
else
  echo "drawio not found — install from https://github.com/jgraph/drawio-desktop/releases"
fi
```
