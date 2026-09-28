# Design Critique Guide

> Adapted from [huashu-design](https://github.com/alchaincyf/huashu-design) by alchaincyf (花叔), MIT — commit `1572d43` (2026-07-26).
>
> Copyright (c) 2026 alchaincyf. Licensed under the MIT License. See upstream `LICENSE` for full terms.

Load this reference when reviewing a design output — self-critique before delivery, or a second pass on a previously shipped design. The rubric is universal; scoring is contextual (a slide is not a logo). Cultural sensibility varies — treat the ranges as anchors, not verdicts.

For HTML/CSS craft numerics (spacing scale, contrast ratio, font count, whitespace %, OKLCH ramps, 60/30/10), defer to `/hs:frontend-design`. This guide owns the *what to check* and *how to weigh it*; the numeric standards live in the front-end skill so a single number is not restated in two places.

This guide scores a *finished* piece. For the pre-generation gate (the one-line Design Read, and the converged failure-mode catalog — generic gradients, template card grids, fake screenshots, generic content, decorative furniture, one-note palettes), see `../../hs:frontend-design/references/design-quality-preflight.md`.

## The 6 dimensions

Concept first, then five execution dimensions. Execution is a multiplier — a great multiplier on zero is still zero.

### 0. Concept — highest weight

Ask "does this design have an idea?" before "is it well made?" Execution amplifies; amplifying a hollow concept only makes it emptier.

| Score | Standard |
| --- | --- |
| 9–10 | A unique idea that grew out of the user's content; the visual motif is not swappable |
| 7–8 | Clear intent; motif relates to content but would just barely still work for a similar topic |
| 5–6 | Style only, no concept — good-looking, says nothing |
| 3–4 | Generic template dressed up; concept layer is zero |
| 1–2 | Not even the right style — decorative pile-on |

Core questions:

- What does this design *say*? Can you name the idea in one sentence? If not, there isn't one.
- Cover every piece of text and the logo — is the subject still recognizable? If not, visuals aren't carrying the message. (Exception: type-as-motif layouts — reframe the question to "does this type treatment survive being applied to a different subject?")
- Swap the client name / product name — does it still work? **If yes, it's a template — this dimension is ≤5.**
- Does the form derive from a unique motif in the content, or was it lifted from a style library?

**Concept veto rule (hard)**: when concept ≤ 5, total score is **capped at 6.0** (upper end of "needs work"). The five execution dimensions are amplifiers — polishing a template further just makes it a shinier template.

### 1. Philosophy alignment

Does the piece stay coherent with the design philosophy / style / school it commits to?

| Score | Standard |
| --- | --- |
| 9–10 | Fully embodies the philosophy's core spirit; every detail has a reason inside it |
| 7–8 | Right overall direction; core traits present; minor detail drift |
| 5–6 | Intent visible but execution mixes in other-style elements; not pure |
| 3–4 | Surface mimicry; the philosophy's core is not understood |
| 1–2 | Basically unrelated to the stated philosophy |

Review checks:

- Does the piece use the signature moves of the designer / school it invokes?
- Do color, type, and layout choices align with that philosophy's rules?
- Any self-contradicting elements? (E.g. choosing Kenya Hara's negative-space school and then packing the frame edge-to-edge.)

### 2. Visual hierarchy

Can the viewer's eye find the entry, follow the intended path, and reach the CTA without friction?

| Score | Standard |
| --- | --- |
| 9–10 | Eye flows naturally along the designer's intended path; zero-friction information capture |
| 7–8 | Primary vs. secondary is clear; 1–2 places of hierarchy drift |
| 5–6 | Title vs. body separable; mid-level hierarchy is muddled |
| 3–4 | Information laid flat; no clear visual entry |
| 1–2 | Chaos — viewer doesn't know where to look first |

Review checks:

- Title vs. body: contrast ratio sufficient (defer to `/hs:frontend-design` for the numeric ratio)
- 3–4 distinct hierarchy levels distinguishable by size / weight / color
- Whitespace actively guiding the eye, not just filler
- **Squint test**: squint your eyes — does the hierarchy still read?

### 3. Craft quality

Alignment, spacing, color discipline, edge quality.

| Score | Standard |
| --- | --- |
| 9–10 | Pixel-precise; no visible alignment / spacing / color flaws |
| 7–8 | Polished overall; 1–2 tiny alignment / spacing issues |
| 5–6 | Basically aligned but spacing is inconsistent, color use unsystematic |
| 3–4 | Obvious alignment errors, spacing chaos, too many colors |
| 1–2 | Rough — looks like a draft |

Review checks (**numeric standards defer to `/hs:frontend-design`**):

- Uses a consistent spacing scale — not arbitrary values
- Same element types share the same spacing
- Color count controlled (bounded palette, not "whatever felt right")
- Font family count controlled — cap deferred to `/hs:frontend-design`
- Edge alignment is precise

### 4. Functionality

Does every element serve the goal, or is decoration crowding the message?

| Score | Standard |
| --- | --- |
| 9–10 | Every element serves the goal; zero redundancy |
| 7–8 | Clear function orientation; a small amount of trimmable decoration |
| 5–6 | Basically usable but decorative elements distract |
| 3–4 | Form over function; the viewer must work to find information |
| 1–2 | Drowned in decoration; lost the ability to convey information |

Review checks:

- If you delete any single element, does the design get worse? If not, delete it.
- Is the CTA / key info in the most prominent position?
- Any "added because it looked nice" elements?
- Information density matched to the medium? (A slide should not read like a PDF page.)

### 5. Originality

Freshness within the philosophy — not novelty for its own sake.

| Score | Standard |
| --- | --- |
| 9–10 | Genuinely fresh; found a unique expression inside the chosen philosophy |
| 7–8 | Has its own voice; not just template reuse |
| 5–6 | Middle-of-the-road; looks like a template |
| 3–4 | Heavy use of clichés (see below) |
| 1–2 | Pure template or stock-asset collage |

Review checks:

- Did it dodge the common clichés below?
- Personal expression present alongside philosophy adherence?
- Any "unexpected but obviously right" design decisions?

## Scene weighting — mapped to hs:design's 7 subskills

Concept dimension is not in this table — it is the first gate for every scene and is never traded off.

| Subskill | Most important | Second | Can relax |
| --- | --- | --- | --- |
| Logo | Craft quality, Originality | Philosophy alignment | Functionality (a mark carries no interaction) |
| CIP (Corporate Identity Program — business card, letterhead, signage) | Craft quality, Philosophy alignment | Functionality | Originality (fidelity to the brand system > novelty) |
| Slides | Visual hierarchy, Functionality | Craft quality | Originality (clarity first) |
| Banner (marketing / hero) | Functionality, Visual hierarchy | Originality | — (all-around requirement) |
| Social photos (e.g. Xiaohongshu / IG posts) | Originality, Visual hierarchy | Philosophy alignment | Craft quality (atmosphere first) |
| Icon | Craft quality, Functionality (semantic clarity) | Philosophy alignment | Originality (recognizability > novelty) |
| Poster | Visual hierarchy, Originality | Craft quality | Functionality (single-glance impact leads) |

Rows describe defaults; a brief that inverts the emphasis wins.

## Common issues — Top 10

Ranked by how often they show up in image-generation and mixed-medium design output. Style-based items are phrased as **default-off unless the brief demands**: the ban is against unconsidered reflex use, not against the aesthetic itself.

### 1. AI-tech clichés (image-generation slop)

- **Symptom**: gradient orbs, digital rain, blue circuit boards, robot faces, generic "neural network" node webs.
- **Why it fails**: viewer fatigue. Cannot tell one brand from another.
- **Fix**: replace literal symbols with abstract metaphors drawn from the content ("dialogue" as motif, not a chat-bubble icon).

### 2. Neon / cyberpunk reflex

- **Symptom**: deep navy background (near-black blue) + neon glow effects, used as the fallback for any "tech" brief.
- **Default-off unless the brief demands** — it is one of the most-abused looks. When a brand's identity legitimately lives here (a synthwave label, a cyberpunk game), it can be the right answer.
- **Fix (when out of scope)**: pick a palette with actual identifiability; defer numeric palette rules to `/hs:frontend-design`.

### 3. Insufficient title-vs-body contrast

- **Symptom**: title and body sizes too close.
- **Fix**: widen the contrast — for the numeric ratio, defer to `/hs:frontend-design`.

### 4. Too many colors

- **Symptom**: five or more colors with no primary/secondary structure.
- **Fix**: bounded palette with a clear primary / secondary / accent split — see `/hs:frontend-design` for the discipline.

### 5. Inconsistent spacing

- **Symptom**: element spacing feels arbitrary, no rhythm.
- **Fix**: adopt a spacing scale — see `/hs:frontend-design` for the actual scale.

### 6. Too much or too little whitespace

- **Symptom**: either edge-to-edge cram or an aimless void with no anchor.
- **Fix**: whitespace should guide the eye — defer to `/hs:frontend-design` for the ratio standard.

### 7. Too many typefaces

- **Symptom**: three or more type families competing.
- **Fix**: cap the family count and use weight/size for variation — see `/hs:frontend-design`.

### 8. Alignment mixing

- **Symptom**: left-aligned here, centered there, right-aligned somewhere else, no reason.
- **Fix**: pick one alignment discipline (usually left) and apply globally.

### 9. Decoration outweighs content

- **Symptom**: pattern / gradient / shadow / drop steals attention from the actual message.
- **Fix**: "delete this decoration — does the design get worse?" If not, delete.

### 10. Density–medium mismatch

- **Symptom**: a whole PDF page's worth of text on one slide; ten motifs stuffed into a cover.
- **Fix by medium**: slides = one point per slide; cover = one focal point; infographic = layered; PDF can be denser but needs navigation.

## Review output template

```
## Design critique

**Overall**: X.X/10 [excellent (8+) / good (6–7.9) / needs work (4–5.9) / fail (<4)]
(When concept ≤ 5, total is capped at 6.0 — fix the concept before polishing execution.)

**Dimension scores**:
- Concept: X/10 — [the idea in one sentence, or "no idea"]
- Philosophy alignment: X/10 — [one line]
- Visual hierarchy: X/10 — [one line]
- Craft quality: X/10 — [one line]
- Functionality: X/10 — [one line]
- Originality: X/10 — [one line]

### Keep
- [specific — describe in design language, not vibes]

### Fix
[sorted by severity]

**1. [problem name]** — ⚠️ critical / ⚡ important / 💡 polish
- Current: [what is there]
- Why: [why it fails]
- Fix: [specific action — for numeric standards defer to `/hs:frontend-design`]

### Quick wins (5-minute pass)
- [ ] [highest-impact fix]
- [ ] [second]
- [ ] [third]
```

## When *not* to critique this way

- Sketch / rough / thumbnail: use "does the shape work at all?" — not the 6-dim rubric.
- User-requested-cliché brief (parody, retro tribute, deliberate template): the "default-off" bans lift. Note in the review that they are lifted.
- Micro-tweak follow-up: only score the affected dimensions.

## Anti-pattern to avoid in the review itself

- Don't remembered-hex. Never restate a brand's color as a specific hex code from memory — read it off `brand-spec.md` or the source. This mistake is what `brand-asset-protocol.md`'s case studies exist to prevent.
- Don't restate craft numerics (font-count cap, whitespace %, spacing scale, OKLCH ramp, 60/30/10) — link to `/hs:frontend-design` instead. Two sources means eventual contradiction.
