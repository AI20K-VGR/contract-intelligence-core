# External design skills — a see-also catalog

`hs:ui-ux` is *design intelligence* — looks up styles, palettes, typography, UX rules over CSV data. It does **not** generate opinionated visuals, audit accessibility, craft motion, or produce hi-fi HTML; the wider ecosystem has purpose-built, MIT/free skills for each.

None vendored here (pointer-not-vendor). Install on demand: clone each repo into the directory Claude Code scans for skills (your project's Claude skills folder); Claude auto-discovers each once it sits there. Pick by job:

| Skill (repo) | Reach for it when you want | Watch out for |
| --- | --- | --- |
| **frontend-design** (`anthropics/skills`) | Distinctive, opinionated aesthetic direction — palette/type/layout that don't read as templated. Strongest visual "wow". | So widely installed its output is becoming a recognizable "AI style" — easy to spot at a glance. |
| **web-design-guidelines** (`vercel-labs/agent-skills`) | Reviewing/auditing UI code for accessibility + web standards (skip-link, ARIA, focus traps, reduced-motion, tabular-nums). Wins at *acceptance*, not screenshots. | It reviews, it doesn't invent a look — pair with a visual skill. |
| **ui-ux-pro-max** (`nextlevelbuilder/ui-ux-pro-max-skill`) | The heavyweight cousin of this skill: searchable DB (84 styles / 161 palettes / 73 font pairings / 99 UX rules) with a real search script. Most *reproducible* lower bound → good for teams/mass production. | Template- and rule-heavy — can feel constraining; lower ceiling than free-play skills. |
| **taste-skill** (`leonxlnx/taste-skill`) | Anti-slop / anti-template discipline + terse copywriting (bans "revolutionary"-type filler). The least "AI-smell" output; also ships style branches (minimalist/brutalist/redesign/image-to-code). | Discipline-first: it converges hard on function pages, opens up only on creative briefs. |
| **hallmark** (`Nutlope/hallmark`) | Whole-website design that "refuses to look AI-generated": per-brief macrostructure (structurally distinct, not color-swapped), 1 of 20 themes, 57 anti-slop gates + self-critique. Verbs: **Build** / **Audit** (score code) / **Redesign** (keep copy+IA) / **Study** (design DNA). | Overlaps taste-skill on anti-slop; look is theme-driven unless custom mode. |
| **emil-design-eng** (`emilkowalski/skills`) | Motion/interaction craft — natural, professional easing (`cubic-bezier(0.23,1,0.32,1)`, `scale(0.95)` entry, staggered reveals, `:active` feedback). Same repo has `animation-vocabulary` + `review-animations`. | Value is invisible in static screenshots — you must interact to see it. Overlay it on any visual skill. |
| **impeccable** (`pbakaus/impeccable`) | Deterministic *post-*polish/audit of an existing page — `detect.mjs` runs ~45 rules without an LLM and actually strips violations; OKLCH seed colors, register discipline. | It refines, it doesn't originate — run it after a design skill, as a pre-launch gate. |
| **huashu-design** (`alchaincyf/huashu-design`) | Hi-fi HTML *production* — clickable prototypes, animated films, 1920×1080 decks, MP4/GIF/PPTX export. (See `## Reach further` in `SKILL.md` for the full install note.) | Heavy install (node/ffmpeg/playwright); instructions in Chinese. |

More design skills from the same two markets (skills.sh / skillsmp.com), narrower or reference-style:

- **frontend-design-landing-page** (`cloudflare/vibesdk`) — marketing/conversion landing references: cream base, generous whitespace, capsule CTAs.
- **frontend-design-saas** (`cloudflare/vibesdk`) — SaaS-dashboard reference in the Stripe/Linear/Vercel register, WCAG AA+.
- **sleek-design-mobile-apps** (`sleekdotdesign/agent-skills`) — mobile-app design specifically (widely installed).
- **extract-design-system** (`arvindrk/extract-design-system`) — reverse-extract a design system (tokens/hex/spacing) from an existing page or screenshot.
- **design-an-interface** (`mattpocock/skills`) — Matt Pocock's step-by-step interface-design workflow.
- **taste-skill style branches** (`leonxlnx/taste-skill` series) — same repo ships `minimalist-skill`, `brutalist-skill`, `soft-skill`, `redesign-skill`, `image-to-code-skill`, `stitch-skill`, `brandkit` for specific aesthetics/flows.

## How to choose (empirically observed)

- A design skill's real power is usually what it *forbids*, not what it teaches — negative lists (no AI fonts, no purple gradients, no centered Hero) break the model's default-output inertia harder than positive examples.
- "Good-looking" ≠ "passing": lead with a visual skill for the look, then run an audit skill (web-design-guidelines / impeccable) for acceptance.
- Motion skills need hands-on interaction to judge — screenshots undersell them.

Trade-off: external, third-party skills of varying maintenance/licensing. Verify each repo's license and current state before depending on it. The comparative verdicts above are observed opinion, not a benchmark this harness reproduces.
