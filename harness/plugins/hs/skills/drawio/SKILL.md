---
name: hs:drawio
injectable: true
description: Use when the user needs polished, editable diagrams (.drawio XML) with 10,000+ branded shapes (AWS/Azure/GCP/Cisco/Kubernetes/UML/ER/network), swimlanes, strict geometry, or export to PNG/SVG/PDF. Generates .drawio files that open in draw.io desktop and diagrams.net.
argument-hint: "<diagram type or description>"
allowed-tools: [Read, Write, Edit, Bash]
metadata:
  compliance-tier: workflow
---

# hs:drawio — diagram with draw.io

Generates `.drawio` XML openable in draw.io desktop / diagrams.net; exports to PNG/SVG/PDF/JPG via draw.io CLI (optional, degrades gracefully). PNG/SVG/PDF support `--embed-diagram` (`-e`) — exported file keeps full diagram XML, so draw.io reopens it editable. Double extension (`name.drawio.png`) signals embedded XML.

---

## When to use

| Use hs:drawio when | Route elsewhere |
|---|---|
| 10,000+ branded stencils (AWS/Azure/GCP/Cisco/K8s/UML/ER) | Hand-drawn/whiteboard look → **hs:excalidraw** |
| Swimlanes, strict geometry, opaque fills | Diagrams-as-code in git/Markdown → **hs:mermaidjs** |
| Export to PNG/SVG/PDF (editable) | Code import/class graph → **hs:tech-graph** |
| Offline preview without login (vendored viewer) | Codebase-wide dependency map → **hs:graphify** |
| AWS architecture with detailed guidance | Freehand infinite-canvas → hs:excalidraw |
| Explaining systems with 3+ components, complex data flows, or relationships that benefit from visual representation | |

**Proactive trigger:** use hs:drawio when explaining a system with **3+ interacting components** or when the user describes a data flow, architecture, or relationship that is clearer as a diagram than as prose.

---

## Prerequisites (optional — degrade if missing)

- **draw.io CLI**: `drawio --version`. Install from https://github.com/jgraph/drawio-desktop/releases
  - macOS: `brew install --cask drawio`
  - Windows: download installer from https://github.com/jgraph/drawio-desktop/releases
  - Linux: download `.deb`/`.rpm` from https://github.com/jgraph/drawio-desktop/releases —
    **do not use snap** (AppArmor sandbox denies secrets/keyring on servers, causes crash)
- **Graphviz `dot`**: for `scripts/autolayout.py`. Missing → hand-place coordinates.
- **Vision-enabled model**: self-check (Step 5) requires a vision model (Claude Sonnet/Opus); gracefully skipped if unavailable.
- **macOS sandbox isolation** (e.g., codex.app): invoking draw.io CLI can crash / produce no output → treat CLI as **unavailable in this sandbox**, don't keep retrying. Prefer a non-sandboxed host for CLI export, or use browser fallback / XML-only output.
- Neither draw.io CLI nor Graphviz is required — the skill generates valid XML without them.

---

## Color palette (fillColor / strokeColor)

Used when no style preset is active:

| Color | fillColor | strokeColor | Use for |
|---|---|---|---|
| Blue | `#dae8fc` | `#6c8ebf` | services, clients |
| Green | `#d5e8d4` | `#82b366` | success, databases |
| Yellow | `#fff2cc` | `#d6b656` | queues, decisions |
| Orange | `#ffe6cc` | `#d79b00` | gateways, APIs |
| Red/Pink | `#f8cecc` | `#b85450` | errors, alerts |
| Grey | `#f5f5f5` | `#666666` | external/neutral |
| Purple | `#e1d5e7` | `#9673a6` | security, auth |

---

## Critical safety rails

**These are needed every run — not buried in references.**

- **Width ceiling 2576**: Claude Vision API rejects images exceeding 2576×2576 px. Export drafts with `--width 2000` (not `-s 2` — `-s` is for the final export step, not the draft). For tall-narrow diagrams that overshoot, use `--height 2000`. There is no short `-w` flag — `-w 2000` silently breaks input-file parsing.
- **`-e` trap / vision 400**: `-e` PNGs ship with an 8-byte IEND truncation → Vision APIs return 400 ("Could not process image"). Draft previews: export WITHOUT `-e`. Final export: always run `repair_png.py` right after `-e`.
- **Self-check cap (max 2 rounds)**: vision-review the draft PNG. Max 2 self-check rounds — if issues remain after 2 rounds, show the user. Do not loop indefinitely.
- **Review-loop safety valve (5 rounds)**: after self-check, loop on user feedback — max 5 rounds. After 5 rounds, suggest opening in draw.io desktop for fine-tuning.

---

## Workflow

**Step 0** — Resolve style preset: scan `~/.drawio-skill/styles/<name>.json` then `styles/built-in/<name>.json`.

**Step 1** — Check deps: resolve draw.io binary (try `drawio` → `draw.io` → macOS app-bundle path → Windows path). Note the real binary name.

**Step 2** — Plan: blueprint-first — sketch node positions mentally before assigning coordinates. Identify shapes, relationships, layout direction (TB or LR), groups/swimlanes.

**Step 3** — Generate `.drawio` XML. Small diagrams: hand-place. Large (>15 nodes): `scripts/autolayout.py`.
- Codebase import graphs: `scripts/pyimports.py` / `jsimports.py` / `goimports.py` / `rustimports.py`.
- Class hierarchy: `scripts/pyclasses.py`.
- Harness skill-graph: `scripts/skillgraph.py --skills a,b,c` (→`references/visualize.md`).
- Validate: `python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/drawio/scripts/validate.py <name>.drawio`.

**Step 3-alt: Edit** — targeted edits on hand-laid-out diagrams (preserve layout): `scripts/edit_drawio.py --list-cells` → generate ops → `--ops` → validate. (→`references/edit-mode.md`)

**Step 4** — Export draft PNG: **no `-e`**, `--width 2000`. Self-check via vision (max 2 rounds).

**Step 5** — Review loop with user (max 5 rounds). Apply targeted XML edits or use edit mode for laid-out files.

**Step 6** — Final export with `-e`. **Mandatory**: run `repair_png.py` on the `-e` PNG. Also export SVG/PDF if requested.

**Browser fallback** (no CLI): `scripts/encode_drawio_url.py input.drawio`.

**Offline preview** (no CLI, no internet): `scripts/make_preview_html.py input.drawio` (→`references/preview.md`).

---

## References

| File | Read when |
|---|---|
| `references/workflow.md` | Full workflow detail (Step 0–7, self-check, review loop, presets, XML rules) |
| `references/edit-mode.md` | Edit diagram at node level (incremental, preserve layout) |
| `references/export.md` | Export commands, CLI flags, repair PNG, browser fallback chain |
| `references/preview.md` | Offline `file://` preview (tier-0 URL vs tier-1 vendored viewer) |
| `references/diagram-types.md` | User names a diagram type (ERD, UML, Sequence, Architecture, ML, Flowchart) |
| `references/shapes.md` | Specific shape lookup — cloud icon, Cisco/K8s symbol, UML/BPMN/ER element |
| `references/style-presets.md` | Presets: learn/save/list/delete/rename/apply |
| `references/style-extraction.md` | Learn flow: extract style from existing diagram |
| `references/style-extraction-sample.md` | Render-a-sample template (used by learn flow for approval render) |
| `references/autolayout.md` | Large/complex diagrams (>15 nodes), Graphviz layout |
| `references/visualize.md` | Codebase import-graph or harness skill-graph visualization |
| `references/troubleshooting.md` | Export failures, vision rejection, rendering problems |
| `references/aws-architecture.md` | AWS architecture — container nesting, icon rules, layouts |
| `references/usage.md` | Example prompts, codebase visualization, shape search, edge routing |
| `references/comparison.md` | vs no-skill, proactive trigger rule, feature delta |
| `references/install.md` | OS-specific draw.io setup, WSL2, Graphviz optional |
| `references/principles.md` | Layout, sizing, color, edges, self-check rules |
| `references/style-guide.md` | Themed patterns (stage/band/endpoint), ONE visual style |
| `references/conventions.md` | GROUP_LEVEL nesting, Color=Identity, edge rounding, square frames |
| `references/catalog-icons.md` | OSS brand tiles (8 packs), shapesearch integration, adding packs |
| `references/layout-tips.md` | Spacing matrix, routing corridors, hub-centering, straight connections |

---

## Boundaries

- Skill does **not** port the Node engine or MCP server (ai-kit `src/*.mjs`) — stdlib Python only. Edit mode (`scripts/edit_drawio.py`) is a **Python re-implementation** of the id-targeted patch algorithm from next-ai-draw-io (not ported code).
- Export/autolayout/preview **degrade** when draw.io CLI / Graphviz / internet are missing.
- Style presets: user-defined at `~/.drawio-skill/styles/`; built-ins at `styles/built-in/`.
- Shape search: `python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/drawio/scripts/shapesearch.py "<keywords>"`. Now covers both official stencils (shape-index) and OSS catalog tiles (offline).
- AI/LLM brand logos: `python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/drawio/scripts/aiicons.py "<brand>"`.
- **Read-only kit boundary**: upstream vendor data files (`data/catalog/*.json`, `data/shape-index.json.gz`, `data/category-colors.json`, `data/groups.json`) are read-only — do not edit them. Treat as vendored reference data.
