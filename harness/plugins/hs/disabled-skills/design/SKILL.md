---
name: hs:design
injectable: true
description: "Design brand identity, logos, banners, and visual assets. Use for brand systems, design tokens, corporate identity programs. Not for UI code patterns."
argument-hint: "[design-type] [context]"
allowed-tools: [Bash, Read, Write, Edit, Glob, Grep, WebFetch, WebSearch]
metadata:
  compliance-tier: knowledge
---

# Design

Unified design skill: brand, tokens, UI, logo, CIP, slides, banners, social photos, icons — each sub-skill keeps commands + deep guide in `references/`; this file routes.

## When to Use

- Brand identity, voice, assets · design system tokens and specs
- Logo design + AI generation · corporate identity program (CIP) deliverables
- Presentations / pitch decks · banners (social, ads, web, print)
- Social photos (IG/FB/LinkedIn/X/Pinterest/TikTok) · SVG icons

Not for UI *code* patterns — that is `hs:ui-ux` / `hs:frontend-design`.

## Before you generate

- **The task names a real brand or product** → load `references/brand-asset-protocol.md`
  first. No shortcut: a logo the agent cannot locate is a stop-and-ask, not a guess.
- **New, vague, or externally-shipped task** → follow the batched intake and 4-pass
  sequence in `references/design-workflow.md`. Small tweaks and follow-ups may skip it.
- **Before delivery** → self-review against `references/design-critique-guide.md`.
  Concept ≤ 5 caps the total at 6.0 — fix the idea before polishing the craft.
- **Shipping UI, a demo, or a deck** → `references/handoff-gate.md` is the last check.

## Sub-skill Routing

| Task | Where | Guide |
|------|-------|-------|
| Brand identity, voice, assets | `brand` | External skill |
| Tokens, specs, CSS vars | `design-system` | External skill |
| shadcn/ui, Tailwind, code | `ui-styling` | External skill |
| Logo creation, AI generation | Logo (built-in) | `references/logo-design.md` |
| CIP mockups, deliverables | CIP (built-in) | `references/cip-design.md` |
| Presentations, pitch decks | Slides (built-in) | `references/slides-create.md` |
| Banners, covers, headers | Banner (built-in) | `references/banner-sizes-and-styles.md` |
| Social media images/photos | Social Photos (built-in) | `references/social-photos-design.md` |
| SVG icons, icon sets | Icon (built-in) | `references/icon-design.md` |
| Posters, art-directed key art | Poster (built-in) | `references/poster-design.md` |

> `brand`/`design-system`/`ui-styling`: optional sibling skills. Present → live under
> `"${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/<name>/`; absent → use built-in guides.

## Built-in Sub-skills

### Logo

55+ styles, 30 color palettes, 25 industry guides via Gemini image models. Search styles/ colors/industries, generate a design brief, then generate logos (white background). Commands + style/color/prompt guides: `references/logo-design.md`, `references/logo-style-guide.md`, `references/logo-color-psychology.md`, `references/logo-prompt-engineering.md`.

### CIP (Corporate Identity Program)

50+ deliverables, 20 styles, 20 industries. Search domains, generate a brief, render mockups (logo recommended), then an HTML presentation. Models: `flash` (default) / `pro`. Commands + guides: `references/cip-design.md`, `references/cip-deliverable-guide.md`, `references/cip-style-guide.md`, `references/cip-prompt-engineering.md`.

### Slides

Strategic HTML presentations with Chart.js, design tokens, copywriting formulas. Start with `references/slides-create.md`; patterns / template / copy / strategy in `references/slides-layout-patterns.md`, `references/slides-html-template.md`, `references/slides-copywriting-formulas.md`, `references/slides-strategies.md`.

### Banner

22 art-direction styles across social, ads, web, print. Build HTML/CSS with `hs:frontend-design`, capture to PNG at exact size. Sizes, styles, safe-zone and print rules: `references/banner-sizes-and-styles.md`.

### Social Photos

Multi-platform social images: HTML/CSS → screenshot export. Sizes, workflow, export tooling, best practices: `references/social-photos-design.md` (+ export commands in `references/social-photos-export.md`).

### Icon

15 styles, 12 categories. Gemini Pro Preview emits SVG text (no image API). Single / batch / multi-size generation: `references/icon-design.md`.

### Poster

A curated poster knowledge base (styles / palettes / layouts / textures) searched by BM25,
then a generator that emits a **model-agnostic text prompt** — style, palette, and texture
locked to preserve identity while layout, shapes, density, and rotation vary per call for a
coherent series. Paste the prompt into any image model. `analyze.py` + `cluster.py` are the
upstream data-build tools (Gemini vision + clustering) that regenerate the CSVs from reference
images. Guide + prompt engineering: `references/poster-design.md`,
`references/poster-prompt-engineering.md`.

## References

| Topic | File |
|-------|------|
| Design Routing | `references/design-routing.md` |
| Logo Design Guide | `references/logo-design.md` |
| Logo Styles | `references/logo-style-guide.md` |
| Logo Colors | `references/logo-color-psychology.md` |
| Logo Prompts | `references/logo-prompt-engineering.md` |
| CIP Design Guide | `references/cip-design.md` |
| CIP Deliverables | `references/cip-deliverable-guide.md` |
| CIP Styles | `references/cip-style-guide.md` |
| CIP Prompts | `references/cip-prompt-engineering.md` |
| Slides Overview | `references/slides.md` |
| Slides Create | `references/slides-create.md` |
| Slides Layouts | `references/slides-layout-patterns.md` |
| Slides Template | `references/slides-html-template.md` |
| Slides Copy | `references/slides-copywriting-formulas.md` |
| Slides Strategy | `references/slides-strategies.md` |
| Banner Sizes & Styles | `references/banner-sizes-and-styles.md` |
| Social Photos Guide | `references/social-photos-design.md` |
| Social Photos Export | `references/social-photos-export.md` |
| Icon Design Guide | `references/icon-design.md` |
| Poster Design Guide | `references/poster-design.md` |
| Poster Prompt Engineering | `references/poster-prompt-engineering.md` |
| Brand Asset Protocol | `references/brand-asset-protocol.md` |
| Design Critique Guide | `references/design-critique-guide.md` |
| Design Workflow (junior-designer mode) | `references/design-workflow.md` |
| Handoff & Critique Gate (`/hs:frontend-design` · `/hs:show-off` · slides) | `references/handoff-gate.md` |

## Scripts

Logo + CIP run a BM25 search engine over bundled CSV data, then call Gemini image models; Icon emits SVG text; Poster runs the same BM25 engine over its CSVs, emitting a model-agnostic text prompt (no image call). All resolve data relative to the script dir — runs wherever the plugin is installed.

| Script | Purpose |
|--------|---------|
| `scripts/logo/search.py` | Search logo styles, colors, industries |
| `scripts/logo/generate.py` | Generate logos with Gemini |
| `scripts/logo/core.py` | BM25 search engine for logo data |
| `scripts/cip/search.py` | Search CIP deliverables, styles, industries |
| `scripts/cip/generate.py` | Generate CIP mockups with Gemini |
| `scripts/cip/render-html.py` | Render HTML presentation from CIP mockups |
| `scripts/cip/core.py` | BM25 search engine for CIP data |
| `scripts/icon/generate.py` | Generate SVG icons with Gemini |
| `scripts/poster/search.py` | Search poster styles/palettes/layouts/textures (BM25) |
| `scripts/poster/generate.py` | Emit a model-agnostic poster text prompt |
| `scripts/poster/core.py` | BM25 search engine + data-build infra for poster data |
| `scripts/poster/analyze.py` | Vision-extract poster attributes from images (Gemini) |
| `scripts/poster/cluster.py` | Cluster extractions → curated poster CSVs |

## Setup

```bash
export GEMINI_API_KEY="your-key"  # https://aistudio.google.com/apikey
pip install google-genai pillow
```

## Integration

**Optional sibling skills:** brand, design-system, ui-styling.
**Related:** hs:frontend-design, hs:ui-ux, hs:ai-multimodal, hs:agent-browser, hs:chrome-profile.

## See also

- For hi-fi HTML production (clickable prototypes, animated films, HTML decks, MP4/PPTX), see the
  **huashu-design** pointer (and the wider external design-skill catalog) in `hs:ui-ux`.
