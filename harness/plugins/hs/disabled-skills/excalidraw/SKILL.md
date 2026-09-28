---
name: hs:excalidraw
injectable: true
description: Generate editable `.excalidraw` JSON files on canvas (architecture, data flow, system design). Choose when the diagram still needs further editing or an editable source is required.
argument-hint: "<concept|repo to diagram>"
allowed-tools: [Read, Write, Edit, Bash]
metadata:
  compliance-tier: knowledge
---

# hs:excalidraw — diagram with reasoning

Generate `.excalidraw` JSON files directly on disk. A good diagram **reasons visually** — structure communicates the concept on its own, not just labeled boxes.

Runtime path: **file-based** (JSON → `.excalidraw`). Rendering to PNG via Playwright is optional (see `references/file-workflow.md`).

---

## Three tests before drawing

- **Isomorphism**: Remove all text — does the structure still communicate the concept?
- **Education**: What does the viewer learn specifically, or do they just see labeled boxes?
- **Container**: Which boxes can be removed so the text stands on its own? If any — remove them.

Default to free-floating text. Add containers only when the shape carries meaning.
Goal: < 30% of text inside containers.

---

## Workflow

### Step 0: Assess depth

| Simple / Conceptual | Detailed / Technical |
|---|---|
| Abstract shapes, relationships | Concrete examples, code snippets, real data |
| Mental model, philosophy | System, architecture, tutorial |
| ~30-second explanation | ~2-3 minutes of teaching |

Technical diagram: research the real spec before drawing (see `references/design-methodology.md`).

### Step 1: Map concept to visual pattern

| Concept behavior | Pattern |
|---|---|
| Produces many outputs | **Fan-out** (radial arrows) |
| Merges many inputs into one | **Convergence** (funnel) |
| Hierarchy / nesting | **Tree** (lines + text, no boxes) |
| Step sequence | **Timeline** (line + dots + labels) |
| Loop / improvement | **Spiral/Cycle** |
| Abstract state | **Cloud** (overlapping ellipses) |
| Transform input to output | **Assembly line** |
| Compare two things | **Side-by-side** |

Each major concept uses a **different pattern** — not a uniform card grid.

### Step 2: Plan layout

Eye direction: left to right or top to bottom. Important elements get more whitespace.

### Step 3: Generate JSON

Create the `.excalidraw` file with the standard structure (see `references/file-workflow.md`).
Element templates: `references/element-templates.md`.
Colors: `references/color-palette.md`.

### Step 4: Validate & fix

Use the Read tool on the PNG file (if rendered) or review the JSON:
1. Does the structure match the design?
2. Text clipped? Overlapping? Arrow pointing wrong way? Uneven spacing?
3. Fix JSON and re-render (typically 2-4 rounds).

---

## Auto-diagram (zero-config)

When the user says "diagram this repo", "visualize the architecture", or "auto diagram":

Load `references/auto-diagram-guide.md` — full pipeline including:
1. Detect project type + framework
2. Discover components (max 15 tool calls)
3. Map connections (max 10 tool calls)
4. Verify with user before drawing
5. Choose layout pattern
6. Generate the `.excalidraw` file

Limit: max 12 components, 20 arrows per diagram. Group if exceeded.

---

## Color

Full color palette (platform-agnostic, AWS/Azure/GCP/K8s): `references/color-palette.md`.

Quick rules: same role = same color; max 3-4 fill colors per diagram; stroke always darker than fill.

---

## References (load when needed)

| File | Contents |
|---|---|
| `references/file-workflow.md` | JSON generation, section-by-section, optional rendering |
| `references/design-methodology.md` | Research mandate, evidence artifacts, multi-zoom, large diagram |
| `references/auto-diagram-guide.md` | Auto-diagram codebase pipeline |
| `references/color-palette.md` | Full color palette (platform-agnostic, AWS/Azure/GCP/K8s) |
| `references/element-templates.md` | Copy-paste JSON templates for each element type |
| `references/json-schema.md` | Excalidraw JSON format reference |
| `references/visual-specs.md` | Sizing table (box/gap/font) + aesthetics (roughness/stroke/opacity) |

## Boundaries — choosing excalidraw vs another diagram skill

excalidraw and `hs:tech-graph` descriptions overlap ("draw architecture / data flow") — anchor on **target artifact**, not subject:

- **excalidraw** — `.excalidraw` JSON file that is **reopenable and hand-editable** on canvas; preferred when the diagram needs further editing.
- **`hs:tech-graph`** — **SVG/PNG publish-grade** one-shot (8 styles, via `rsvg-convert`); static image embedded in docs/slides.
- **`hs:mermaidjs`** — **inline markdown** diagram, renders natively on GitHub/GitLab.
- **`hs:preview`** — **explains** a change or architecture; does not deliver a diagram file.
- **`hs:drawio`** — branded stencils (AWS/Azure/GCP/Cisco/K8s/UML/ER), strict geometry, editable `.drawio` export, offline preview; prefer when the diagram needs vendor-specific shapes or must be opened in draw.io.

SVG layout rules (spacing, arrow routing, label placement, z-index, anti-patterns): see
`hs:tech-graph` — apply when reviewing exported SVG from Excalidraw.

Need to understand the codebase before diagramming: `hs:understand` or `hs:repomix`.
