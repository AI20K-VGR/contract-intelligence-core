# Login-free preview — hs:drawio

Two preview tiers for `.drawio` files that need neither the draw.io desktop CLI nor a login account.

## Tier-0: URL fragment (encode_drawio_url.py)

```bash
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/drawio/scripts/encode_drawio_url.py input.drawio
# → https://viewer.diagrams.net/...#R<payload>

python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/drawio/scripts/encode_drawio_url.py --edit input.drawio
# → https://app.diagrams.net/...#create=<payload>  (editor mode)
```

**How it works:**
- Encodes the XML into the URL fragment (`#R...` or `#create=...`)
- The fragment is NEVER sent to the server — data stays in the browser (privacy-safe)
- `encodeURIComponent` is mandatory: without it, a diagram containing `%` or CJK characters throws "URI malformed"
- **Requires internet** to load the diagrams.net app — unusable air-gapped

**When to use Tier-0:**
- CLI unavailable but internet is available
- User wants to open the diagram in the editor (--edit) for further edits
- WSL2/Windows: `cmd.exe` drops the URL fragment → create a `.url` shortcut file instead

## Tier-1: Vendored GraphViewer (make_preview_html.py)

```bash
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/drawio/scripts/make_preview_html.py input.drawio
# → input.html  (next to input.drawio)

# Custom output path
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/drawio/scripts/make_preview_html.py input.drawio -o /tmp/preview.html
```

**How it works:**
- Generates `input.html` with the XML embedded into `<div class="mxgraph" data-mxgraph="...">`
- `<script src="../vendor/viewer.min.js">` — relative path, no CDN
- Open `file://` in a browser → GraphViewer renders fully offline
- **No internet, no CLI, no login required**

**vendor/viewer.min.js:**
- draw.io GraphViewer, Apache-2.0 (JGraph Ltd)
- Source: `https://viewer.diagrams.net/js/viewer-static.min.js`
- Vendored at `vendor/viewer.min.js` (~3.7 MB)
- Attribution: `vendor/VIEWER-LICENSE.txt`

**Degrade (viewer not found):**
- The script still generates the HTML, exit 0
- Adds a warning message to the page
- CDN URL in a comment (`<!-- CDN fallback: ... -->`)
- HTML still has the correct structure; the user can open it later once internet is available

## Comparison

| | Tier-0 URL | Tier-1 Vendored |
|---|---|---|
| Needs internet | Yes (to load the app) | No |
| Air-gap | No | Yes |
| Data sent to server | No (fragment) | No |
| CLI required | No | No |
| Login required | No | No |
| Edit diagram | Yes (--edit) | No (view only) |
| HTML file size | Small | ~3.7 MB viewer |

## Fragment privacy

For both tiers: the XML diagram is NEVER uploaded to any server.
- Tier-0: the URL fragment (`#...`) is not included in HTTP request headers
- Tier-1: the local file:// URL is never sent anywhere

Tier-0's CDN URL loads the app code from diagrams.net, but the diagram data never leaves the browser.

## Which tier to use

- **Need to edit online**: Tier-0 `--edit`
- **Air-gap / no internet**: Tier-1
- **Quick share / embed**: Tier-0
- **CI / automated check**: Tier-1 (deterministic, no network)
