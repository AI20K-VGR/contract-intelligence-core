---
name: hs:ui-ux
injectable: true
description: "UI/UX design intelligence for web and mobile: style, color, typography, layout, accessibility, interaction, responsive behavior, forms, charts, design systems — framework-agnostic (React, Vue, Svelte, SwiftUI, Flutter, Tailwind, HTML/CSS); only React Native has a dedicated stack dataset (`--stack react-native`). Use when designing, styling, or reviewing UI/UX."
allowed-tools: [Bash, Read, Write, Edit, Glob, Grep]
argument-hint: "<query> [--domain <name>] [--design-system] [-f markdown]"
metadata:
  compliance-tier: knowledge
---

# UI/UX — Design Intelligence

Design guide for web and mobile applications — 50+ styles, 161 color palettes, 57 font pairings, 161 product types w/ reasoning rules, 99 UX guidelines, 25 chart types, plus React Native stack guidance (`--stack react-native`). Searchable, priority-ranked recommendations.

## When to Apply

This Skill should be used when the task involves **UI structure, visual design decisions, interaction patterns, or user experience quality control**.

### Must Use

This Skill must be invoked in the following situations:

- Designing new pages (Landing Page, Dashboard, Admin, SaaS, Mobile App)
- Creating or refactoring UI components (buttons, modals, forms, tables, charts, etc.)
- Choosing color schemes, typography systems, spacing standards, or layout systems
- Reviewing UI code for user experience, accessibility, or visual consistency
- Implementing navigation structures, animations, or responsive behavior
- Making product-level design decisions (style, information hierarchy, brand expression)
- Improving perceived quality, clarity, or usability of interfaces

### Recommended

Recommended when:

- UI looks "not professional enough" but the reason is unclear
- Receiving feedback on usability or experience
- Pre-launch UI quality optimization
- Aligning cross-platform design (Web / iOS / Android)
- Building design systems or reusable component libraries

### Skip

Skip when:

- Pure backend logic development
- Only involving API or database design
- Performance optimization unrelated to the interface
- Infrastructure or DevOps work
- Non-visual scripts or automation tasks

**Decision criteria**: If the task will change how a feature **looks, feels, moves, or is interacted with**, this Skill should be used.

## Rule Categories by Priority

*Human/AI reference: follow priority 1→10 for focus order; `--domain <Domain>` queries details on demand. Scripts skip this table.*

| Priority | Category | Impact | Domain | Key Checks (Must Have) | Anti-Patterns (Avoid) |
|----------|----------|--------|--------|------------------------|------------------------|
| 1 | Accessibility | CRITICAL | `ux` | Contrast 4.5:1, Alt text, Keyboard nav, Aria-labels | Removing focus rings, Icon-only buttons without labels |
| 2 | Touch & Interaction | CRITICAL | `ux` | Min size 44×44px, 8px+ spacing, Loading feedback | Reliance on hover only, Instant state changes (0ms) |
| 3 | Performance | HIGH | `ux` | WebP/AVIF, Lazy loading, Reserve space (CLS &lt; 0.1) | Layout thrashing, Cumulative Layout Shift |
| 4 | Style Selection | HIGH | `style`, `product` | Match product type, Consistency, SVG icons (no emoji) | Mixing flat & skeuomorphic randomly, Emoji as icons |
| 5 | Layout & Responsive | HIGH | `ux` | Mobile-first breakpoints, Viewport meta, No horizontal scroll | Horizontal scroll, Fixed px container widths, Disable zoom |
| 6 | Typography & Color | MEDIUM | `typography`, `color` | Base 16px, Line-height 1.5, Semantic color tokens | Text &lt; 12px body, Gray-on-gray, Raw hex in components |
| 7 | Animation | MEDIUM | `ux` | Duration 150–300ms, Motion conveys meaning, Spatial continuity | Decorative-only animation, Animating width/height, No reduced-motion |
| 8 | Forms & Feedback | MEDIUM | `ux` | Visible labels, Error near field, Helper text, Progressive disclosure | Placeholder-only label, Errors only at top, Overwhelm upfront |
| 9 | Navigation Patterns | HIGH | `ux` | Predictable back, Bottom nav ≤5, Deep linking | Overloaded nav, Broken back behavior, No deep links |
| 10 | Charts & Data | LOW | `chart` | Legends, Tooltips, Accessible colors | Relying on color alone to convey meaning |

## How to Use

**REQUIRED:** Always run `--design-system` first to generate the design system baseline before narrower `--domain` searches.

Search domains via the CLI tool below.

---

## Prerequisites

Check if Python is installed:

```bash
python3 --version || python --version
```

If Python is not installed, install it based on user's OS:

**macOS:**
```bash
brew install python3
```

**Ubuntu/Debian:**
```bash
sudo apt update && sudo apt install python3
```

**Windows:**
```powershell
winget install Python.Python.3.12
```

---

## Output Formats

`--design-system` supports two output formats:

```bash
# ASCII box (default) - best for terminal display
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/ui-ux/scripts/search.py "fintech crypto" --design-system

# Markdown - best for documentation
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/ui-ux/scripts/search.py "fintech crypto" --design-system -f markdown
```

---


## References

| Topic | File |
|-------|------|
| Quick Reference (§1-7: accessibility -> animation) | `references/quick-reference.md` |
| Quick Reference continued (§8-10: forms, nav, charts) | `references/quick-reference-forms-nav-data.md` |
| How to Use This Skill | `references/how-to-use-this-skill.md` |
| Search Reference | `references/search-reference.md` |
| Example Workflow | `references/example-workflow.md` |
| Tips for Better Results | `references/tips-for-better-results.md` |
| Common Rules for Professional UI | `references/common-rules.md` |
| Pre-Delivery Checklist | `references/pre-delivery-checklist.md` |
| External design skills (see-also catalog) | `references/external-design-skills.md` |

Scripts: `scripts/search.py` (BM25 search over 13 CSV datasets), `scripts/core.py`, `scripts/design_system.py`. Data resolves script-relative.

## Reach further: hi-fi HTML production

This skill is design *intelligence* (style/palette/rule lookup). For hi-fi HTML *production* beyond it — clickable prototypes, animated launch films, 1920×1080 HTML decks, MP4/GIF/PPTX export — the external MIT skill **huashu-design** (alchaincyf/huashu-design) is purpose-built. It is intentionally NOT vendored here (31MB assets + node/ffmpeg/playwright + optional ByteDance TTS key;
instructions in Chinese).

Install on demand — clone into the directory Claude Code scans for skills (your project's Claude skills folder), then install Node deps:

    git clone https://github.com/alchaincyf/huashu-design
    # move ./huashu-design into your Claude Code skills directory, then:
    cd huashu-design && npm install    # ffmpeg required for video/audio

Claude Code auto-discovers it once it sits in the skills directory. Strong at three things this lookup skill doesn't:

- **design-context-first** — grows a design from your existing tokens/codebase, reading exact hex + spacing rather than inventing them.
- **40 HTML-native styles** — a broad catalog of production-ready HTML aesthetics to pick from.
- **concept-first critique** — a rubric that judges the idea/message before the pixels.

## See also: external design skills

huashu-design (above) is one of a wider ecosystem of external MIT/free design skills — opinionated visuals, accessibility audits, motion craft, searchable design databases — doing jobs this lookup skill deliberately doesn't. Full catalog (per-skill "reach for it when" / "watch out for" + how-to-choose) lives in `references/external-design-skills.md`. None vendored here (pointer-not-vendor).
