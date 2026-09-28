# Brand Asset Protocol

> Adapted from [huashu-design](https://github.com/alchaincyf/huashu-design) by alchaincyf (花叔), MIT — commit `1572d43` (2026-07-26).

Load this reference **before generating anything** when the task names a real brand or product (Stripe, Linear, Notion, DJI, Apple, an employer/client, etc.). Without real assets, image-generation subskills produce "generic tech" output that does not identify the brand.

## Why identity > spec

Ranked by identifiability, not by design-spec convention:

| Asset | Identifiability | When required |
| --- | --- | --- |
| Logo | Highest — one glance identifies the brand | ALL brands |
| Product image / render | Very high — for hardware/packaged goods, the product IS the subject | Physical products |
| UI screenshot | Very high — for digital products, the interface IS the subject | Apps, sites, SaaS |
| Color values | Medium — helps but often collides between brands | Supporting |
| Fonts | Low — needs the above to establish identity | Supporting |
| Vibe keywords | Low — self-check only | Supporting |

Rule: extracting only colors + fonts and skipping the logo / product / UI is a protocol violation. Substituting a CSS silhouette or hand-drawn SVG for a real product photo is a protocol violation ("generic tech animation, brand-agnostic"). If assets cannot be located, **stop and ask the user** — do not fabricate.

## The hard invariant

**Logo for a real brand cannot be found → STOP and ask the user. Never fabricate one, never substitute a CSS silhouette, never proceed silently.**

This is the single hard rule of the protocol. Every other guideline below is strong recommendation.

## Step 1 — Ask (batch the full asset list)

Do not open with "do you have brand guidelines?" — too vague, users don't know what to answer. Ask one batched checklist:

```
For <brand/product>, which of the following do you have? (Listed by priority.)
1. Logo — SVG or high-res PNG (REQUIRED for any brand)
2. Product image / official render — REQUIRED for physical products
3. UI screenshots — REQUIRED for digital products (main pages)
4. Color palette — hex / RGB / brand-color chart
5. Font list — display + body
6. Brand guidelines PDF / Figma design system / brand site link

Send what you have; I will search / fetch / (as last resort) generate the rest.
```

## Step 2 — Search official channels

| Asset | Search path |
| --- | --- |
| Logo | `<brand>.com/brand` · `<brand>.com/press` · `<brand>.com/press-kit` · `brand.<brand>.com` · inline SVG in the site header |
| Product image | `<brand>.com/<product>` hero + gallery · official launch video frame · official press release attachments |
| UI screenshot | App Store / Google Play product page · official screenshots section · official demo video frames |
| Colors | Site inline CSS / Tailwind config / brand guidelines PDF |
| Fonts | Site `<link rel="stylesheet">` refs · Google Fonts trace · brand guidelines |

Web-search fallback keywords when direct paths fail:

- Logo missing → `<brand> logo download SVG`, `<brand> press kit`
- Product missing → `<brand> <product> official renders`, `<brand> <product> product photography`
- UI missing → `<brand> app screenshots`, `<brand> dashboard UI`

## Step 3 — Download assets (per-type fallback chain)

### 3.1 Logo (required for every brand)

Modern brand sites are usually SPAs — direct `curl <brand>.com/logo.svg` typically returns an empty HTML shell. For known digital products / SaaS / AI tools, **icon aggregators hit first** — best success rate, clean SVGs.

Ordered by success rate:

0. **Icon aggregators** (first choice for known digital products / SaaS / AI tools):
   ```bash
   # svgl — widest AI/developer-brand coverage (Claude, Cursor, Anthropic, Vercel, ...), includes light/dark + wordmark
   curl -s "https://api.svgl.app?search=<brand>"   # returns JSON; take route(.light/.dark) SVG URL, then download
   # simpleicons — single-color glyphs, tint to the brand color at fetch
   curl -o logo.svg "https://cdn.simpleicons.org/<slug>/<hexcolor>"
   ```
1. Standalone SVG/PNG on official brand page (`<brand>.com/brand`, `/press`):
   ```bash
   curl -A "Mozilla/5.0" -L -o assets/<brand>-brand/logo.svg "<official-logo-url>"
   ```
2. Full HTML of the site, then grep out the inline `<svg>...</svg>` logo node.
3. **Google favicon service** (site-authoritative mark, almost never fails):
   ```bash
   curl -o logo.png "https://www.google.com/s2/favicons?domain=<brand-domain>&sz=256"
   ```
4. Official social-media avatar (last resort): GitHub / X / LinkedIn company avatar, typically 400×400 or 800×800 transparent PNG.

Verify every download: `file <logo>` (must be real SVG/PNG, not a 106-byte placeholder or HTML shell) and `head -c 90 <logo.svg>` (must begin `<svg`).

### 3.2 Product image (required for physical products)

Priority order:

1. **Official product-page hero** — right-click image → address, or `curl` it. Usually 2000px+.
2. **Official press kit** — `<brand>.com/press` often lists high-res product photos.
3. **Official launch video frames** — `yt-dlp` the YouTube video, `ffmpeg` a few frames.
4. **Wikimedia Commons** — public-domain sources often exist.
5. **AI-generated fallback** (e.g. nano-banana-pro) — feed the real product photo as reference so the generation stays on-brand. **Never** substitute a CSS/SVG silhouette.

### 3.3 UI screenshot (required for digital products)

- App Store / Google Play product screenshots (note: may be mockups, not real UI — compare against a live screen).
- Site "Screenshots" section.
- Product demo video frames.
- Product's official X/Twitter release posts (often the freshest UI).
- If the user has an account, ask them to screenshot the real product interface.

### 3.4 Quality bar — the 5-10-2-8 rule

Logo is exempt (see below). Every other asset goes through this bar:

| Dimension | Standard | Anti-pattern |
| --- | --- | --- |
| **5 rounds of search** | Cross-source (site / press kit / social / video frame / Wikimedia / user screenshot), not "grab the first two on page 1" | First result wins |
| **10 candidates** | Assemble at least 10 before shortlisting | Grab 2, nothing to choose from |
| **Pick the top 2** | From the 10, select 2 as final. All of them = visual overload, taste dilution | Ship everything found |
| **Every asset ≥ 8/10** | If it does not clear 8/10, **prefer to leave it out**. Use an honest placeholder (grey block + label) or AI-generate on top of an official reference. | 7/10 filler shipped |

Scoring dimensions (record in `brand-spec.md`):

1. Resolution — ≥2000px (≥3000px for print/large screen).
2. Copyright clarity — official > public domain > free stock > suspected reuse (suspected reuse = 0).
3. Fit with brand vibe — matches the keywords in the spec.
4. Light / composition / style consistency — the two chosen assets do not clash when placed side by side.
5. Independent narrative ability — carries its own role (not decoration).

**Logo exception**: any logo is better than none. Even a 6/10 logo is 10× better than no logo — identifiability is a root, not a shortlist.

## Step 4 — Verify and extract (not just grep for colors)

| Asset | Verification |
| --- | --- |
| Logo | File exists, opens as SVG/PNG, at least two variants (light-on-dark, dark-on-light), transparent background |
| Product image | ≥ 2000px, cut-out or clean background, multiple angles (hero, detail, in-scene) |
| UI screenshot | Real resolution (1× / 2×), current version, no personal / demo data leaked |
| Colors | `grep -hoE '#[0-9A-Fa-f]{6}' assets/<brand>-brand/*.{svg,html,css} \| sort \| uniq -c \| sort -rn \| head -20`, then discard grayscale |

Watch for **demo-brand contamination**: product screenshots often contain another brand's colors as demo content. When two strong colors appear, distinguish which belongs to the brand under study.

**Brand facets**: a single brand can carry different palettes across surfaces (marketing site vs product UI). Both are real — pick the facet that fits the delivery surface.

## Step 5 — Codify in `brand-spec.md`

Once assets are collected, freeze them into a spec file. All subsequent HTML/CSS references paths and CSS variables from this file — never hard-code hex codes inline.

```markdown
# <Brand> · Brand Spec
> Collected: YYYY-MM-DD
> Sources: <list download origins>
> Asset completeness: <complete / partial / inferred>

## 🎯 Core assets (first-class)

### Logo
- Primary: `assets/<brand>-brand/logo.svg`
- Reversed (on light bg): `assets/<brand>-brand/logo-white.svg`
- Usage contexts: <intro / outro / corner watermark / anywhere>
- Do-not-modify rules: <no stretching / no recoloring / no stroke>

### Product image (physical products)
- Hero: `assets/<brand>-brand/product-hero.png` (2000×1500)
- Details: `assets/<brand>-brand/product-detail-1.png` / `product-detail-2.png`
- In-scene: `assets/<brand>-brand/product-scene.png`

### UI screenshot (digital products)
- Home: `assets/<brand>-brand/ui-home.png`
- Core feature: `assets/<brand>-brand/ui-feature-<name>.png`

## 🎨 Supporting assets

### Palette
- Primary: #XXXXXX  <source>
- Background: #XXXXXX
- Ink: #XXXXXX
- Accent: #XXXXXX
- Never-use: <colors the brand explicitly avoids>

### Type
- Display: <font stack>
- Body: <font stack>
- Mono (data HUD): <font stack>

### Signature details
- <the details this brand invests 120% in>

### No-go zone
- <hard bans (e.g. "Lovart avoids blue", "Stripe avoids low-saturation warm tones")>

### Vibe keywords
- <3-5 adjectives>
```

Execution discipline once the spec exists:

- Every HTML must **reference** paths from `brand-spec.md`; never CSS-silhouette or hand-draw a substitute.
- Logo appears as `<img>` pointing at the real file — never redrawn.
- Product image appears as `<img>` — never a CSS silhouette.
- Load CSS variables from the spec: `:root { --brand-primary: ...; }` — templates only use `var(--brand-*)`.
- This turns brand consistency from "on-your-own recall" into "structural" — adding a color requires editing the spec.

## Full-flow fallback (per asset type)

| Missing | Response |
| --- | --- |
| Logo | **Stop and ask user.** The hard invariant. |
| Product image (physical product) | AI-generate on top of an official reference (nano-banana-pro or equivalent) → ask user for material → honest placeholder (grey block + "product photo TBD" label). |
| UI screenshot (digital product) | Ask user for a screenshot from their own account → official demo video frame. Do NOT fill with a mockup generator. |
| Colors | Switch to `design-workflow.md`'s "no-context fallback" — propose 3 directions with labeled assumptions. |

Forbidden: silently fill the gap with a generic gradient / CSS silhouette. **Prefer to pause and ask over filler.**

## Case studies (from huashu-design project history)

These are attributed failures documented by the upstream project. Do not restate the brand's actual color as a remembered hex; the whole point of the protocol is that agents guess wrong.

- **DJI Pocket 4 launch animation** — the agent ran an old "extract colors only" version of the
  protocol: no DJI logo pulled, no Pocket 4 product photo, product replaced with a CSS
  silhouette. Result: "generic black background + orange accent tech animation" with no DJI
  identity. Author: *"otherwise, what are we expressing?"* — triggered the protocol upgrade to
  include product images and UI as first-class assets.
- **Kimi animation** — the agent guessed Kimi's brand color from memory (assumed warm/orange). The actual color at the time was in the blue family. Full rework required.
- **Lovart design** — a product screenshot contained a demo brand's red (Heytea). The agent adopted that red as Lovart's color, nearly ruining the whole design.
- **Five-way coding-agent comparison deck** (Claude Code / Cursor / Codex / Copilot / Trae) —
  the agent classified the task as "PPT without style reference", jumped to the fallback
  direction advisor, and spawned three design paths — WITHOUT fetching any of the five product
  logos. Author: *"why did we not fetch these product logos?"* → protocol updated so trigger
  includes "design that names or lists real products in parallel" AND the fallback path never
  exempts logo collection.

## Cost of running the protocol vs. cost of skipping

| Scenario | Time |
| --- | --- |
| Run the protocol | Logo 5 min + 3–5 product/UI images 10 min + grep colors 5 min + spec 10 min = **~30 min** |
| Skip and ship generic output | 1–2 hr rework, sometimes full rebuild |

Cheapest reliability investment available — especially for commissioned / launch / client-critical work.
