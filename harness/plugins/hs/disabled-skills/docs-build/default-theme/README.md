# default-theme

Generic shell bundle for the docs-build SSG engine.  A project that has no
custom design can start a working showcase with just this theme.

## What is included

| Path | Purpose |
|------|---------|
| `assets/js/01-core-shell.js` | Lang-toggle (EN/VI), canvas#net hero (Three.js fallback to 2D), scroll-reveal, GSAP count-ups (optional), single-file hash router, sidebar mobile drawer, TOC scroll-spy. No domain data, no domain function calls. |
| `assets/css/01-base.css` | Design tokens + CSS reset. |
| `assets/css/02-components.css` | Cards, banners, badges, stat blocks. |
| `assets/css/05-layout.css` | App shell grid (header, sidebar, main, TOC rail). |
| `assets/css/06-print-a11y.css` | Print styles + accessibility overrides. |
| `assets/lib/three.min.js` | Three.js r148 — powers the 3D hero canvas. Falls back to 2D automatically. |

## Seam: shell vs domain overlay

- **shell** — this bundle (`default-theme/assets/`): self-contained starter with no domain logic.
- **content/overlay** — project assets (`docs/showcase/assets/` in the VSF project): domain JS,
  domain CSS, data-JS files, and any shell parts the project overrides.
- **adapter** (`build.py`) — concatenates (assembles) CSS and JS parts from the project's own
  `assets/` dir into assembled strings, then constructs `Ctx` with those strings before calling
  `ssg_engine.build(ctx, out)`.  All asset merging happens in `build.py`, **not** in the engine.
- **engine** (`ssg_engine`) — receives only the already-assembled `Ctx.css` / `Ctx.js` strings
  and `Ctx.assets_dir` (a single directory pointer).  The engine has no concept of `theme_dir`,
  `overlay_dir`, or `_assemble`; it never resolves parts.

A new project can either point its `asset_slots` at `default-theme/assets` directly, or copy
`default-theme/assets/` as a starting point and extend it.

Shell parts (in this bundle):
- `01-core-shell.js`, `01-base.css`, `02-components.css`, `05-layout.css`,
  `06-print-a11y.css`, `three.min.js`

Domain parts (stay in project overlay, not shipped here):
- `02-boundary-glossary.js`, `03-modules-flows.js`, data-JS files (`*-data.js`),
  `04-diagrams*.js`, `05-sims.js`, `06-dialogs.js`, `07-data-late.js`,
  `08-wire.js`, `09-search.js`
- `03-boundary-dialog.css`, `04-diagrams-sims.css`
- `gsap.min.js`, `ScrollTrigger.min.js`

## Usage

1. Copy `manifest.example.yaml` to your project root and edit it.
2. Point `asset_slots.js` at `[01-core-shell]` (no domain JS needed).
3. Point `asset_slots.css` at `[01-base, 02-components, 05-layout, 06-print-a11y]`.
4. Point `asset_slots.vendor` at `[three.min.js]`.
5. In your `build.py` adapter, call `_assemble(your_assets_dir / "css", css_parts)` and
   `_assemble(your_assets_dir / "js", js_parts)`, then pass the assembled strings to `Ctx`.
   The engine receives the final strings — it does not read asset files itself.

## Verification gate

```
python3 -m pytest harness/plugins/hs/skills/docs-build/tests/test_default_theme_standalone.py -q
```

This builds a minimal 2-page site using only default-theme parts (no overlay)
and asserts that the output contains `canvas#net`, `btn-en`, `btn-vi`, the
sidebar, and no dangling `@key@` tokens.
