# Worked examples — rough idea → finished prompt

The quality bar, shown not told. Each example is `user input → the prompt to emit → the strategy line`. These define what "every word load-bearing" looks like; calibrate your output against them. (First two adapted from the original prompt-master README, MIT.)

---

## Example 1 — Image generation (external target: Midjourney)

**User:** "write me a midjourney prompt for a realistic samurai standing in the rain at night"

**Emit:**
```
<prompt_payload>
lone samurai standing in heavy rain at night, traditional armor,
neon reflections on wet cobblestone street, cinematic lighting,
dramatic shadows, fog, ultra detailed, photorealistic,
shallow depth of field --ar 16:9 --v 6 --style raw

negative: blurry, low quality, watermark, cartoon, anime, extra limbs
</prompt_payload>
```
🎯 Target: Midjourney · 💡 Comma-separated descriptors over prose; lighting and mood anchored early; aspect ratio and version locked; negative prompt prevents style drift.

---

## Example 2 — Agentic coding (external target: Claude Code)

**User:** "build a claude code prompt for a landing page for a business dashboard that looks and feels exactly like notion — smooth animations, clean ui"

**Emit** (abridged shape — every vague cue turned into an exact spec):
```
<prompt_payload>
Objective: production-quality static landing page for a business dashboard, matching Notion's
exact aesthetic — clean, minimal, typographic, smooth animations throughout.

Stack: single HTML file, embedded CSS + vanilla JS. No frameworks. Google Fonts (Inter) only.

Design spec — match exactly:
- Background #ffffff · primary text #1a1a1a · secondary #6b7280 · border #e5e7eb · accent #000000
- Inter 400/500/600/700 · base spacing 8px · radius 6px cards / 4px buttons
- Shadows: 0 1px 3px rgba(0,0,0,0.08) only — no dramatic shadows

Sections in order: navbar (sticky, border-bottom on scroll) · hero (left-aligned, 2 CTAs) ·
logos bar · features (3-col, hover translateY(-2px) 200ms) · how-it-works (alternating) ·
pricing (2 tiers) · CTA banner · footer.

Animations: fade-in + translateY(20px→0) on scroll via IntersectionObserver (threshold 0.15,
500ms ease-out); 100ms stagger on feature cards; smooth scroll on anchors.

Constraints: single file, no external files, gray div placeholders for images, pixel-perfect at
375px and 1440px, no CSS frameworks.

Done when: all sections render at both breakpoints · animations trigger without layout shift ·
navbar sticks + border appears on scroll · hover states work · zero console errors.
</prompt_payload>
```
🎯 Target: Claude Code · 💡 Every vague Notion cue translated to exact hex + pixel specs so the agent cannot guess wrong; animations defined with exact timing, method, and trigger.

---

## Example 3 — Internal target (harness-aware enrichment)

**User:** "write me a prompt to get a second-engine review of my auth refactor before I merge"

*Locus check:* the user wants text to hand to a second engine → paste-elsewhere → write it. *Discover:* `disabled_skills.py --status gemini` → `live` (if `disabled`, advise enabling, do not run).

**Emit:**
```
<prompt_payload>
Adversarially review the auth refactor in src/auth/** before merge. As a red-teamer, find the
failure mode the happy path and the author both missed. For each finding: the concrete scenario
(inputs/state → wrong outcome) and a fix. Rank by severity. Return findings only — no preamble,
no restating the diff.
</prompt_payload>
```
🎯 Target: gemini partner lane (`hs:gemini`) · Route: gemini adversarial-review — matched: *"carry an adversarial-review request to the gemini partner lane"* · 💡 Names the real local capability instead of a generic "review this"; scoped to the diff; output contract kills preamble.

*(Contrast — DEFER: "just fix the auth bug" wants work RUN here → do NOT write a prompt; reply "run `/hs:plan`".)*
