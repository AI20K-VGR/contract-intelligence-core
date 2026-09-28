---
name: hs:tech-graph
injectable: true
description: Generate publish-grade static technical diagrams (SVG+PNG, 8 styles) — architecture, data flow, sequence, agent/memory, concept map — for embedding in docs or slides.
argument-hint: "<topic> [--style <1-8>] [--output <path>]"
allowed-tools: [Bash, Read, Write, Edit]
metadata:
  compliance-tier: knowledge
---

# hs:tech-graph — SVG technical diagrams

Generate SVG technical diagrams and export PNG via `rsvg-convert`. Load `references/svg-layout-best-practices.md` before writing any SVG.

**Dependency guard:** `rsvg-convert` (package `librsvg2-bin`) is external — MUST NOT be assumed available. Before the Validate step, check `command -v rsvg-convert`. If missing: still deliver the `.svg` file (primary artifact, opens in any browser), **skip Validate + Export PNG**, and report one line — install via `apt-get install librsvg2-bin` (or `brew
install librsvg`) for PNG export. Do not treat as a hard error.

## Workflow (in order)

1. **Classify** — identify diagram type (see Diagram Types below)
2. **Extract structure** — layers, nodes, edges, semantic groups from the user description
3. **Plan layout** — apply layout rules for the chosen diagram type
4. **Load style** — default `references/style-1-flat-icon.md`; if the user selects a different style, load the correspondingly numbered style file (`style-2-dark-terminal.md` … `style-8-dark-luxury.md`). Load `references/style-diagram-matrix.md` when suggesting the best style for a diagram type. Style 8 (Dark Luxury): hand-craft SVG directly, do not use the template generator.
5. **Map shapes** — use the Shape Vocabulary below. Load `references/icons.md` for concrete SVG shape templates before drawing (Azure icons: `references/icons-azure.md`).
6. **Write SVG** — Python list method (see SVG Generation below)
7. **Validate** — `rsvg-convert file.svg -o /dev/null 2>&1` (skip if the guard above reports missing `rsvg-convert`)
8. **Export PNG** — `rsvg-convert -w 1920 file.svg -o file.png` (skip if binary is missing; SVG remains the deliverable)
9. **Visual self-review** — if the runtime can read images: inspect PNG; fix if arrows cross through components, labels collide, or boxes overlap. Skip silently if images cannot be read.

## Diagram types

| Type | Primary layout |
|------|---------------|
| Architecture | Horizontal layers top→bottom; dashed `<rect>` groups; ViewBox `0 0 960 600` |
| Data Flow | Each arrow has a data-type label; wider arrows for primary path |
| Flowchart | Top-down; diamond=decision; snap to 120px grid |
| Agent Architecture | Input→Agent core→Memory→Tool→Output; cyclic loop arrows |
| Memory Architecture | Write path / read path separated; tiers: Working→Short→Long→External |
| Sequence | Vertical lifelines; horizontal messages; ViewBox height = 80+(N×50) |
| Comparison Matrix | Column=systems, Row=attrs; max 5 cols |
| Timeline / Gantt | X=time, Y=tasks; ViewBox `0 0 960 400` |
| Mind Map | Radial from cx=480,cy=280; curved bezier branches |
| Class / ER | 3-compartment class box (UML); Crow's foot notation for ER |
| Use Case | Actor (stick figure) outside boundary; ellipse use cases inside |
| State Machine | filled circle=initial; double circle=final; diamond=choice |
| Network Topology | Tiered: Internet→Edge→Core→Access→Endpoints |

## Shape vocabulary

| Concept | Shape |
|---------|-------|
| User/Human | Stick figure (circle + body path) |
| LLM/Model | Rounded rect + double border + ⚡ |
| Agent/Orchestrator | Hexagon or rounded rect + double border |
| Memory short-term | Rounded rect, dashed border |
| Memory long-term | Cylinder (database shape) |
| Vector Store | Cylinder + inner grid lines |
| Tool/Function | Rect + wrench icon |
| API/Gateway | Hexagon (single border) |
| Queue/Stream | Horizontal tube |
| Decision | Diamond |
| External Service | Rect + cloud icon or dashed border |

## Arrow semantics

| Flow | Color | Style |
|------|-------|-------|
| Primary data | `#2563eb` blue | 2px solid |
| Control/trigger | `#ea580c` orange | 1.5px solid |
| Memory read | `#059669` green | 1.5px solid |
| Memory write | `#059669` green | 1.5px dashed `5,3` |
| Async/event | `#6b7280` gray | 1.5px dashed `4,2` |
| Transform | `#7c3aed` purple | 1px solid |
| Feedback/loop | `#7c3aed` purple | 1.5px curved |

Using 2 or more arrow types requires a **legend**.

## SVG generation

**Python list method is required**:
```python
python3 << 'EOF'
lines = []
lines.append('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 600">')
lines.append('  <defs>')
# ... each line independent
lines.append('</svg>')
with open('/path/to/output.svg', 'w') as f:
    f.write('\n'.join(lines))
print("SVG generated")
EOF
```

**Pre-write checklist**:
1. Can you write COMPLETE content right now?
2. Have you checked for syntax errors?
If NO to either → STOP, prepare fully before writing.

**Common errors to avoid**: `yt-anchor`, missing `y=`, `fill=#fff` (missing quotes), missing `</svg>`.

**Error recovery**: 1 error→targeted fix; 2 errors→switch method; 3 errors→STOP, report to user.

## Batch / template mode (scripted generation)

For a repeat diagram type or regression fixture, drive the packaged generator instead of hand-writing Python-list SVG (step 6 stays default for one-off/hand-crafted diagrams; REQUIRED for Style 8 — Dark Luxury):

```bash
# Generate from a JSON spec (containers/nodes/arrows) — see fixtures/*.json for worked examples
python3 ${CLAUDE_SKILL_DIR}/scripts/generate-from-template.py <type> <output.svg> '<json-data>'

# Validate + export PNG in one step (wraps step 7-8 above)
bash ${CLAUDE_SKILL_DIR}/scripts/generate-diagram.sh -t <type> -s <style> -o <output.svg>

# Validate an existing SVG only
bash ${CLAUDE_SKILL_DIR}/scripts/validate-svg.sh <file.svg>
```

`<type>` matches the Diagram types table above (architecture, data-flow, flowchart, sequence, agent, memory, use-case, comparison, timeline, mind-map, class, state-machine, er-diagram, network-topology). `fixtures/*.json` are known-good regression inputs per style; `templates/*.svg` are reference layouts to read, not files to fill in directly.

## Styles

| # | Name | Background | Best fit |
|---|------|-----------|----------|
| 1 | Flat Icon (default) | White | Docs, blog, presentations |
| 2 | Dark Terminal | `#0f0f1a` | GitHub, dev articles |
| 3 | Blueprint | `#0a1628` | Architecture docs |
| 4 | Notion Clean | White minimal | Notion embed |
| 5 | Glassmorphism | Dark gradient | Product sites, keynotes |
| 6 | Official Warm | Cream `#f8f6f3` | Warm editorial |
| 7 | Official Minimal | Pure white | Clean tech docs |
| 8 | Dark Luxury | Deep black `#0a0a0a` | Premium editorial |

## Output

- Default: `./[derived-name].svg` + `./[derived-name].png`
- Custom: user specifies `--output /path/`
- PNG: `rsvg-convert -w 1920 file.svg -o file.png` (1920px = 2x retina)

## Boundaries

- Do not modify files outside the output path the user specifies.
- For inline diagrams in docs, combine with `hs:mermaidjs` or `hs:excalidraw`.
- For codebase architecture maps, read with `hs:understand` or `hs:repomix` first.
- For vendor-specific branded shapes (AWS/GCP/Cisco/K8s/UML/ER) or draw.io-native editing, use `hs:drawio`. Exception: Azure — this skill ships its own maintained icon catalog (`references/icons-azure.md`, loaded step 5); use it directly, skip `hs:drawio`.
