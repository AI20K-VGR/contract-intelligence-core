---
name: hs:frontend-design
injectable: true
description: Create polished frontend interfaces from designs/screenshots/videos. Use for web components, 3D experiences, replicating UI designs, quick prototypes, immersive interfaces, avoiding AI slop.
allowed-tools: [Bash, Read, Write, Edit, Glob, Grep, WebFetch, WebSearch]
argument-hint: "<brief|screenshot|video>"
metadata:
  compliance-tier: knowledge
---

Guides creation of distinctive, production-grade frontend interfaces avoiding generic "AI slop" — real working code, exceptional attention to aesthetic detail and creative choices.

**IMPORTANT**: MUST follow Design Thinking, the aesthetics + interface-writing rules in `./references/design-guidance.md`, the Asset & Analysis references, and Anti-Patterns (AI Slop) below. DO NOT skip these rules.

Handles visual direction, UI implementation, screenshot/video replication, frontend polish, and design critique. Does NOT handle backend architecture, product strategy, or deployment except where frontend delivery requires it.

## Security

- Never include secrets, private tokens, customer data, or hidden environment values in frontend assets, screenshots, fixtures, or demo copy.
- Treat uploaded screenshots/videos as user-provided private context. Do not publish, link, or reuse them outside the current task unless the user explicitly asks.
- If a brief asks to clone a third-party product, replicate layout and interaction patterns without copying protected logos, trademarked assets, private data, or proprietary text.

## Workflow Selection

| Input | Workflow | Reference |
|-------|----------|-----------|
| Screenshot | Replicate exactly | `./references/workflow-screenshot.md` |
| Video | Replicate with animations | `./references/workflow-video.md` |
| Screenshot/Video (describe only) | Document for devs | `./references/workflow-describe.md` |
| 3D/WebGL request | Three.js immersive | `./references/workflow-3d.md` |
| Quick task | Rapid implementation | `./references/workflow-quick.md` |
| Complex/award-quality | Full immersive | `./references/workflow-immersive.md` |
| Existing project upgrade | Redesign Audit | `./references/redesign-audit-checklist.md` |
| From scratch | Two-Pass Design Process below | - |

**All workflows**: Activate `hs:ui-ux` FIRST for design intelligence.

**Precedence:** When anti-slop rules conflict with `hs:ui-ux` recommendations (e.g., Inter font, AI Purple palette, Lucide-only icons), substitute alternatives from `./references/anti-slop-rules.md` unless the user explicitly requested the conflicting choice.

## Design Lead Protocol

Approach each UI as a design lead hired to create a specific visual identity, not a reusable template.

1. Ground the concept in the subject. If the brief is vague, choose one concrete subject, audience, and page/app job before designing. Use memory and project context as hints, but make the subject explicit.
2. Pull from the subject's world: materials, instruments, artifacts, vocabulary, constraints, rituals. Distinctive design starts there, not from generic SaaS patterns.
3. Take one justified aesthetic risk: a layout move, type treatment, interaction, image system, or signature component that belongs to this brief.
4. Spend boldness in one place. Let the signature element carry the risk; keep supporting UI disciplined.

## Screenshot/Video Replication (Quick Reference)

1. **Analyze** with `hs:ai-multimodal` — extract colors, fonts, spacing, effects
2. **Plan** with `@ui-ux-designer` subagent — phased implementation
3. **Implement** — match source precisely
4. **Verify** — compare to original
5. **Document** — update `./docs/design-guidelines.md` if approved

See the specific workflow files for detailed steps.

## Design Dials

Configurable parameters that drive design decisions. Set defaults at session start or let the user override via chat:

| Dial | Default | Low (1-3) | High (8-10) |
|------|---------|-----------|-------------|
| `DESIGN_VARIANCE` | 8 | Perfect symmetry, centered, equal grids | Asymmetric, masonry, empty zones, fractional grid |
| `MOTION_INTENSITY` | 6 | CSS hover/active only | Scroll reveals, spring physics, perpetual micro-animations |
| `VISUAL_DENSITY` | 4 | Art gallery — huge whitespace | Cockpit — tiny paddings, 1px dividers, mono numbers |

**Usage:** At `DESIGN_VARIANCE > 4`, force split-screen / left-aligned over centered heroes. At `MOTION_INTENSITY > 5`, embed perpetual micro-animations. At `VISUAL_DENSITY > 7`, drop generic cards for spacing/dividers. Dial-driven SaaS dashboard: `./references/bento-motion-engine.md`.

## Two-Pass Design Process

Before coding from scratch or reshaping a UI:

1. **Brainstorm a compact design plan** covering:
   - Subject (concrete subject/audience/screen-job — what problem does this solve, who uses it)
   - Tone (pick an extreme: brutally minimal, maximalist, retro-futuristic, organic, luxury, playful, editorial, brutalist, art-deco, pastel, industrial...)
   - Color (4-6 named hex tokens with roles); Type (≥2 roles, display + body, + data face when needed)
   - Layout (1-2 concepts as prose/ASCII wireframes); Signature element (the one thing someone will remember)
   - Motion (one role, or an explicit decision to stay still); Constraints (framework, performance, accessibility); Copy voice
2. **Critique the plan before building** — Ask whether any part would appear unchanged for a different client in the same category. If yes, revise palette/type/structure/copy/signature until it belongs to this subject. Only then implement, deriving color, type, spacing, motion from the revised plan.

Keep this planning mostly in analysis unless the user asks to see options.

**CRITICAL**: Choose a clear conceptual direction and execute with precision. Bold maximalism and refined minimalism both work — the key is intentionality, not intensity. Then implement working code (HTML/CSS/JS, React, Vue) that is production-grade, visually striking, cohesive, and meticulously refined.

Full aesthetics + interface-writing rules (Hero-as-Thesis, Typography, Color, Motion, Spatial, etc.): `./references/design-guidance.md`.

## Asset & Analysis References

| Task | Reference |
|------|-----------|
| Generate assets | `./references/asset-generation.md` |
| Analyze quality | `./references/visual-analysis-overview.md` |
| Extract guidelines | `./references/design-extraction-overview.md` |
| Optimization | `./references/technical-overview.md` |
| Animations | `./references/animejs.md` |
| Magic UI (80+ components) | `./references/magicui-components.md` |
| Anti-slop forbidden patterns | `./references/anti-slop-rules.md` |
| Redesign audit checklist | `./references/redesign-audit-checklist.md` |
| Premium design patterns | `./references/premium-design-patterns.md` |
| Performance guardrails | `./references/performance-guardrails.md` |
| Bento motion engine (SaaS) | `./references/bento-motion-engine.md` |

Quick start: `./references/ai-multimodal-overview.md`

## Anti-Patterns (AI Slop)

Strongly prefer alternatives to these LLM defaults. Full rules + "AI Tells" checklist: `./references/anti-slop-rules.md`.

- **Typography** — avoid Inter/Roboto/Arial; prefer trending Google Fonts with Vietnamese support (`Geist`, `Outfit`, `Cabinet Grotesk`, `Satoshi`). Input fields ≥16px font to avoid mobile zoom.
- **Color** — avoid AI purple/blue gradient, pure `#000000`, oversaturated accents. Neutral bases + one considered accent.
- **Layout** — avoid 3-column equal card rows, centered heroes at high variance, `h-screen`. Use asymmetric/split-screen, `min-h-[100dvh]`. Mobile-first is a must.
- **Content** — avoid "John Doe", "Acme Corp", round numbers, AI clichés ("Elevate", "Seamless", "Unleash"). Realistic names, organic data, plain language.
- **Effects** — avoid neon glows, custom cursors, gradient text on headers (unless asked). Use tinted inner shadows, spring physics.
- **Components** — avoid default unstyled shadcn, Lucide-only icons, generic card-border-shadow at high density. Customize; try Phosphor/Heroicons; prefer spacing over cards.

Animation/blur performance: `./references/performance-guardrails.md`. Remember: commit fully to distinctive visions.

## See also

- For hi-fi HTML production (clickable prototypes, animated films, HTML decks, MP4/PPTX), see the
  **huashu-design** pointer (and the wider external design-skill catalog) in `hs:ui-ux`.
