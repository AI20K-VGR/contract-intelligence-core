---
name: hs:ui-styling
injectable: true
description: Style UIs with shadcn/ui components (Radix UI + Tailwind CSS). Use for accessible components, themes, dark mode, responsive layouts, design systems, color customization.
allowed-tools: [Bash, Read, Write, Edit, Glob, Grep, WebFetch]
argument-hint: "[component or layout]"
paths: ["**/*.css", "tailwind.config.*", "**/components/ui/**"]
metadata:
  compliance-tier: knowledge
---

# UI Styling

Build beautiful, accessible UIs: shadcn/ui (Radix UI primitives), Tailwind CSS, canvas-based visual design. This file routes; detail/code live in `references/`.

Upstream: shadcn/ui `https://ui.shadcn.com/llms.txt` · Tailwind `https://tailwindcss.com/docs`.

## When to Use

- React frameworks (Next.js, Vite, Remix, Astro), accessible components (dialogs, forms, tables, navigation), utility-first CSS, responsive mobile-first layouts
- Dark mode + theme customization, design systems with consistent tokens
- Visual designs / posters / brand materials, rapid prototyping, complex UI patterns (data tables, charts, command palettes)

## Core Stack

- **Components — shadcn/ui**: accessible Radix primitives, copy-paste (components live in your codebase), TypeScript-first, CLI-installed.
- **Styling — Tailwind CSS**: utility-first, build-time (zero runtime), mobile-first, design tokens, automatic dead-code elimination.
- **Visual — Canvas**: philosophy-driven compositions, visual-over-text, systematic patterns.

## Quick Start

```bash
npx shadcn@latest init                       # framework, TS, paths, theme prompts
npx shadcn@latest add button card dialog form
```

Component + Tailwind-only setup, form validation, responsive dark-mode layout: `references/common-patterns.md`.

## Guides

| Topic | Primary | Continued |
|-------|---------|-----------|
| shadcn components (forms, layout, overlays, display) | `references/shadcn-components.md` | `references/shadcn-components-cont.md` |
| Theming, CSS vars, dark mode, variants | `references/shadcn-theming.md` | `references/shadcn-theming-cont.md` |
| Accessibility (ARIA, keyboard, focus, screen readers) | `references/shadcn-accessibility.md` | `references/shadcn-accessibility-cont.md` |
| Tailwind utilities (layout, spacing, type, color) | `references/tailwind-utilities.md` | `references/tailwind-utilities-cont.md` |
| Responsive (mobile-first, breakpoints, container queries) | `references/tailwind-responsive.md` | `references/tailwind-responsive-cont.md` |
| Tailwind customization (@theme, custom utilities, layers) | `references/tailwind-customization.md` | `references/tailwind-customization-cont.md` |
| Canvas visual design system | `references/canvas-design-system.md` | `references/canvas-design-system-cont.md` |
| Common code patterns | `references/common-patterns.md` | — |

## Utility Scripts

```bash
python "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/ui-styling/scripts/shadcn_add.py button card dialog          # add components + deps
python "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/ui-styling/scripts/tailwind_config_gen.py --colors brand:blue --fonts display:Inter
```

## Best Practices

1. Compose complex UIs from simple primitives; extract components only for true repetition.
2. Utility-first styling; mobile-first responsive (layer responsive variants).
3. Accessibility-first: Radix primitives, focus states, semantic HTML.
4. Consistent design tokens (spacing scale, palettes, type); apply dark variants everywhere.
5. Performance: automatic CSS purging, avoid dynamic class names. TypeScript for DX.
6. Visual hierarchy: let composition guide attention; treat UI as a craft.

## Related skills

- `hs:ui-ux`: UX strategy + design-system intelligence (this skill is shadcn/Tailwind mechanics; strategy lives there).
- `hs:web-design-guidelines`: accessibility / UX guideline audit of the built UI.

## Resources

shadcn/ui `https://ui.shadcn.com` · Tailwind `https://tailwindcss.com` · Radix `https://radix-ui.com`
· Tailwind UI `https://tailwindui.com` · Headless UI `https://headlessui.com` · v0 `https://v0.dev`
