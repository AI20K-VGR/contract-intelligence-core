# Pack manifest schema — build_pack.py

Manifest files (`packs/<name>/manifest.json`) drive `build_pack.py` to
regenerate `catalog/<name>.json` packs. Each manifest lists icons with one
or more resolution strategies tried in order.

## Icon object fields

| Field | Required | Description |
|---|---|---|
| `name` | yes | Unique icon key (snake_case) |
| `label` | yes | Display name shown in diagram |
| `color` | no | Background tile colour (default `#5A6B7B`) |
| `tags` | no | Search keywords (default `label.lower()`) |
| `abbr` | no | Short text for text-tile fallback |
| `file` | no | Path to vendored SVG/PNG under `packs/<pack>/` |
| `devicon` | no | devicon CDN slug (e.g. `postgresql`) |
| `url` | no | Full SVG URL (e.g. vendor logo CDN) |
| `slug` | no | simple-icons slug → monochrome glyph tile |
| `frame` | no | `false` → embed full-bleed logo as-is (for square logos) |

## Resolution priority

1. `file` — vendored local asset (network-free, highest priority)
2. `devicon` — fetch from CDN, try `original` then `plain` variant
3. `url` — fetch SVG from arbitrary URL
4. `slug` — simple-icons → brand-colour tile with white glyph
5. Text fallback — coloured square with abbreviation/label text

## Example

```json
{
  "category": "Big Data",
  "icons": [
    {
      "name": "kafka",
      "label": "Apache Kafka",
      "color": "#231F20",
      "slug": "apachekafka",
      "tags": "kafka streaming"
    }
  ]
}
```

## Rasterization

`build_pack.py` uses `cairosvg` (optional) to rasterize SVG tiles to PNG before
base64 embedding. Without cairosvg, tiles are embedded as SVG data-URIs. Install
with `pip install cairosvg`.

## Network dependency

build_pack fetches from devicon and simple-icons CDNs for non-vendored icons;
it is NOT sandbox-runnable without network. Only `file:` vendored icons are
fully offline. This tool is meant for dev regen, not runtime diagram generation.

Source: drawio-ai-kit@bda82a2 (sparklabx, MIT)
