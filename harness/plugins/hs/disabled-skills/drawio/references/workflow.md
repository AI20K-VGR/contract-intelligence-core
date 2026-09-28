# Workflow — hs:drawio

Full workflow Steps 0–7. SKILL.md has the condensed version; this is the detailed reference.

## Step 0 — Resolve active preset

Scan the user's message for a phrase that names a style preset: "use my `<name>` style", "with my `<name>` style", "in `<name>` mode", "in the style of `<name>`". A bare "with `<name>`" does **not** count — "draw a diagram with redis" names a component, not a style.

If no explicit match: check `~/.drawio-skill/styles/` for any file with `"default": true`. Else → no preset active; fall through to built-in color/shape/edge conventions.

Load the preset JSON from `~/.drawio-skill/styles/<name>.json`, falling back to `"${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/drawio/styles/built-in/<name>.json`. If the named preset exists in neither location, tell the user the name is unknown, list available presets, and stop — do **not** silently fall back to defaults.

When a preset loads successfully, mention it: *"Using preset `<name>`."*

## Step 1 — Check deps (resolve binary name)

Try in order:
1. `drawio --version` (canonical Homebrew/`.deb`/`.rpm`/AUR name)
2. `draw.io --version` (older builds, some distro packages)
3. macOS: `/Applications/draw.io.app/Contents/MacOS/draw.io --version`
4. Windows: `"C:\Program Files\draw.io\draw.io.exe" --version`

The first one that prints a version is your binary. Use that exact name/path for every export command. **Do not copy example commands verbatim** — substitute your resolved binary.

**Read-only kit boundary:** the draw.io skill's upstream data files (`data/catalog/*.json`, `data/shape-index.json.gz`, `data/category-colors.json`, `data/groups.json`) are **read-only vendor data**. Do not edit them — treat them as vendored reference. Use `scripts/shapesearch.py` to look up stencils; never hand-edit the index or catalog files.

## Step 2 — Plan (blueprint-first)

**Blueprint-first discipline:** sketch node positions mentally before assigning x/y coordinates. Plan a grid — identify shapes, relationships, layout direction (LR or TB), groups/swimlanes.

Grid alignment: snap all `x`, `y`, `width`, `height` values to **multiples of 10** — this ensures shapes align on draw.io's default grid.

Group related nodes in the same horizontal or vertical band. Place heavily-connected "hub" nodes centrally so edges radiate outward instead of crossing.

## Step 3 — Generate XML

### CRITICAL: Self-closing edges

Every edge `mxCell` **must** have a `<mxGeometry relative="1" as="geometry" />` child element. Self-closing edge cells (`<mxCell ... edge="1" ... />`) are **invalid** and will not render. Always use the expanded form:

```xml
<!-- WRONG — self-closing, will not render -->
<mxCell id="3" style="..." edge="1" parent="1" source="2" target="4" />

<!-- RIGHT — expanded -->
<mxCell id="3" style="..." edge="1" parent="1" source="2" target="4">
  <mxGeometry relative="1" as="geometry" />
</mxCell>
```

Three common edge patterns:

```xml
<!-- Basic directed edge -->
<mxCell id="10" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;" edge="1" parent="1" source="2" target="3">
  <mxGeometry relative="1" as="geometry" />
</mxCell>

<!-- Edge with pinned exit/entry points -->
<mxCell id="11" value="HTTP/REST" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;exitX=0.5;exitY=1;entryX=0.5;entryY=0;" edge="1" parent="1" source="2" target="4">
  <mxGeometry relative="1" as="geometry" />
</mxCell>

<!-- Edge with waypoints (routes around shapes) -->
<mxCell id="12" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;" edge="1" parent="1" source="3" target="5">
  <mxGeometry relative="1" as="geometry">
    <Array as="points">
      <mxPoint x="500" y="50" />
    </Array>
  </mxGeometry>
</mxCell>
```

### Required XML properties

Every vertex needs `vertex="1"` and `parent="1"` (unless nested in a container). Every edge needs `edge="1"`, `parent="1"`, `source` and `target` matching existing cell ids. `id="0"` and `id="1"` are the required root cells — never omit them.

Multi-line labels: use `&#xa;` for line breaks inside `value` attributes.

### Proactive trace-each-edge

Before finalizing coordinates, **trace each edge path mentally** — if it must cross an unrelated shape, either move the shape or add waypoints. This is proactive (prevents crossings) rather than the reactive self-check in Step 5.

For tree/hierarchical layouts: assign nodes to layers (rows), connect only between adjacent layers to minimize crossings.

For star/hub layouts: place the hub center, satellites around it — edges stay short and radial.

When an edge must span multiple rows/columns, route it along the outer corridor, not through the middle of the diagram.

### Containers

Children set `parent="containerId"` and use coordinates **relative to the container**.

| Type | Style | When |
|---|---|---|
| Invisible group | `group;pointerEvents=0;` | No border, no own connections |
| Titled swimlane | `swimlane;startSize=30;` | Visible title bar / has connections |
| Custom container | append `container=1;pointerEvents=0;` | Any shape as container |

### Edge style rules

- **Always** include `rounded=1;orthogonalLoop=1;jettySize=auto` — enables smart routing.
- Pin `exitX/exitY/entryX/entryY` on every edge when a node has 2+ connections.
- Add `<Array as="points">` waypoints when an edge must detour around a shape.
- **Leave room for arrowheads:** the final segment between the last bend and target must be ≥20px long. If too short, the arrowhead overlaps the bend. Fix: increase spacing or add waypoints.
- `flowAnimation=1;` animates the edge (SVG/desktop) — ideal for data-flow and pipeline diagrams.

## Step 4 — Export draft PNG

**No `-e`** (the embedded `zTXt mxGraphModel` chunk causes vision API 400).
**`--width 2000`** to stay under the 2576×2576 vision ceiling.

```bash
drawio -x -f png --width 2000 -o diagram.png input.drawio
```

## Step 5 — Self-check

Use vision capability to read the draft PNG. Check for:

| Defect | What to look for | Auto-fix |
|---|---|---|
| Overlapping shapes | Two+ shapes stacked on top of each other | Shift apart ≥200px |
| Clipped labels | Text cut off at shape boundaries | Increase shape width/height |
| Missing connections | Arrows that don't visually connect | Verify source/target ids |
| Off-canvas shapes | Shapes at negative coords or far from cluster | Move to positive coords near cluster |
| Edge-shape overlap | An edge crosses through an unrelated shape | Add waypoints or increase spacing |
| Stacked edges | Multiple edges overlap on the same path | Distribute exitX/entryX across shape perimeter |
| Edge-label overlap | Label on bent edge lands on corner/against box | Add waypoint at corridor centre with `labelBackgroundColor` |

- Max **2 self-check rounds** — if issues remain after 2 fixes, show the user.
- Re-export after each fix and re-read the new PNG.

**Temp-png hygiene:** the draft PNG in Step 4–5 is **for eyes only** (vision self-check + user review). It is a transient artifact — do not ship it as a deliverable. The final deliverable is the `.drawio.png` from Step 6.

## Step 6 — Review loop

Show the image, collect feedback, apply targeted XML edits:

| User request | XML edit action |
|---|---|
| Change color of X | Update `fillColor`/`strokeColor` in matching `mxCell` |
| Add a new node | Append `mxCell` vertex with next available `id` |
| Remove a node | Delete the `mxCell` vertex + edges with matching `source`/`target` |
| Move shape X | Update `x`/`y` in `mxGeometry` |
| Resize shape X | Update `width`/`height` in `mxGeometry` |
| Add arrow A→B | Append `mxCell` edge with `source`/`target` matching A and B |
| Change label text | Update the `value` attribute |
| Change layout direction | **Full regeneration** — rebuild XML with new orientation |

- Single-element changes: edit XML in place — preserves layout tuning.
- Layout-wide changes (swap LR↔TB, "start over"): regenerate full XML.
- Overwrite the same `diagram.png` each iteration — no `v1`, `v2`, `v3` files.
- **Safety valve:** after 5 rounds, suggest opening in draw.io desktop for fine-tuning.

## Step 7 — Final export

Once approved, export to all requested formats (default: PNG).

```bash
# Final PNG with embedded XML
drawio -x -f png -e -s 2 -o diagram.drawio.png input.drawio

# REPAIR immediately after -e PNG
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/drawio/scripts/repair_png.py diagram.drawio.png

# SVG/PDF (optional)
drawio -x -f svg -e -o diagram.svg input.drawio
drawio -x -f pdf -e -o diagram.pdf input.drawio
```

**DEC deliverable rule:** the `.drawio` + `.drawio.png` are the deliverables. The draft `.png` from Step 4–5 is a transient internal artifact — do not ship it. The `.drawio.png` double extension signals embedded XML (open in draw.io → editable).

**Auto-launch:** offer to open the `.drawio` file for fine-tuning:
- macOS: `open diagram.drawio`
- Linux: `xdg-open diagram.drawio`
- Windows: `start diagram.drawio`

Report file paths for both the `.drawio` source and exported images.

## XML skeleton

```xml
<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="drawio" version="26.0.0">
  <diagram name="Page-1">
    <mxGraphModel>
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
        <!-- user shapes start at id="2" -->
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

**Rules:**
- `id="0"` and `id="1"` are required root cells — never omit them.
- User shapes start at `id="2"`, increment sequentially.
- All text uses `html=1` in style for proper rendering.
- **Never use `--` inside XML comments** — it's illegal per XML spec.
- Escape: `&amp;`, `&lt;`, `&gt;`, `&quot;`.
