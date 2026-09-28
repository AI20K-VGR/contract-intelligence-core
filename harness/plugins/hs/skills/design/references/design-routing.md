# Design Routing Guide

When to use each design sub-skill.

## Skill Overview

| Sub-skill | Purpose | Key Files |
|-------|---------|-----------|
| Logo (built-in) | AI logo generation (55 styles, 30 palettes) | `references/logo-design.md` + 3 refs + `scripts/logo/` |
| CIP (built-in) | Corporate Identity Program (50 deliverables) | `references/cip-design.md` + 3 refs + `scripts/cip/` |
| Slides (built-in) | HTML presentations with Chart.js | `references/slides-create.md` + 4 refs |
| Banner (built-in) | Banners for social, ads, web, print (22 styles) | `references/banner-sizes-and-styles.md` |
| Social Photos (built-in) | Multi-platform social images | `references/social-photos-design.md` + export ref |
| Icon (built-in) | SVG icon generation (15 styles) | `references/icon-design.md` + `scripts/icon/` |
| ui-styling | Component implementation (shadcn/ui, Tailwind) | External sibling skill (optional) |

## Routing by Task Type

### Implementation Tasks
**→ ui-styling** (external sibling skill, when present)

- Add shadcn/ui components
- Style with Tailwind classes
- Implement dark mode
- Create responsive layouts
- Build accessible components

### Logo Design Tasks
**→ Logo** (built-in, `references/logo-design.md`)

- Create logos with AI (Gemini Nano Banana)
- Search logo styles, color palettes, industry guidelines
- Generate design briefs
- Explore 55+ styles (minimalist, vintage, luxury, geometric, etc.)

### Corporate Identity Program Tasks
**→ CIP** (built-in, `references/cip-design.md`)

- Generate CIP deliverables (business cards, letterheads, signage, vehicles, apparel)
- Create CIP briefs with industry/style analysis
- Generate mockups with/without logo (Gemini Flash/Pro)
- Render HTML presentations from CIP mockups

### Presentation Tasks
**→ Slides** (built-in, `references/slides-create.md`)

- Create strategic HTML presentations
- Data visualization with Chart.js
- Apply copywriting formulas to slide content
- Use layout patterns and design tokens

### Banner Design Tasks
**→ Banner** (built-in, `references/banner-sizes-and-styles.md`)

- Design banners for social media (Facebook, Twitter, LinkedIn, YouTube, Instagram)
- Create ad banners (Google Ads, Meta Ads)
- Website hero banners and headers
- Print banners and covers
- 22 art direction styles (minimalist, bold typography, gradient, glassmorphism, etc.)

### Icon Design Tasks
**→ Icon** (built-in, `references/icon-design.md`)

- Generate SVG icons with AI
- Batch icon variations in multiple styles
- Multi-size export (16px, 24px, 32px, 48px)
- 15 styles: outlined, filled, duotone, rounded, sharp, gradient, etc.
- 12 categories: navigation, action, communication, media, commerce, data

## Routing by Question Type

| Question | Sub-skill |
|----------|-------|
| "How do I build a button component?" | ui-styling |
| "How do I add dark mode?" | ui-styling |
| "Create a logo for my brand" | Logo |
| "Generate business card mockups" | CIP |
| "Create a pitch deck" | Slides |
| "Design brand identity package" | CIP |
| "What logo style fits my industry?" | Logo |
| "Design a Facebook cover" | Banner |
| "Create ad banners for Google" | Banner |
| "Make a website hero banner" | Banner |
| "Generate a settings icon" | Icon |
| "Create SVG icons for my app" | Icon |
| "Design an icon set" | Icon |

## Multi-Skill Workflows

### Complete Brand Identity Package

```
1. Logo → Generate logo
   - Style, palette, industry brief

2. CIP → Generate deliverable mockups
   - Business cards, letterheads, signage (with logo)

3. Slides → Build pitch deck
   - Present the identity package
```

### Component Creation

```
1. Icon → Generate icon set
   - Style, category, multi-size export

2. ui-styling → Implement
   - Build with shadcn/ui + Tailwind
```

## Quick Commands

**Logo:**
```bash
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/design/scripts/logo/generate.py --prompt "..." --brand "..." --style minimalist
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/design/scripts/logo/search.py --list-styles
```

**CIP:**
```bash
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/design/scripts/cip/generate.py --brand "..." --set --industry technology
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/design/scripts/cip/render-html.py
```

**Icon:**
```bash
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/design/scripts/icon/generate.py --prompt "..." --style outlined --sizes 16,24,32,48
```

**Components (ui-styling sibling skill):**
```bash
npx shadcn@latest add button card input
```

## When to Use Multiple Sub-skills

Use **Logo + CIP + Slides** when:
- Complete brand identity package with deliverable mockups and a pitch deck

Use **Banner + Logo** when:
- Social media presence: branded banners across all platforms

Use **Icon + ui-styling** when:
- Custom icon set matching an existing component library
