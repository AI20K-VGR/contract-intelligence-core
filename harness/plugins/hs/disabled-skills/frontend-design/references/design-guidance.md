# Frontend Design — Aesthetics & Interface Writing

Detailed guidance split out of `SKILL.md` to keep the core thin. These rules are load-bearing: follow them alongside the SKILL's Design Thinking and Anti-Patterns sections.

## Frontend Aesthetics Guidelines

Focus on:
- **Hero as Thesis**: For web pages, the hero must express the core subject. Open with the most characteristic thing in that world: image, live demo, animation, strong headline, interactive moment, or product state. Avoid default metric/stat hero blocks unless the brief makes them truly central.
- **Typography**: Avoid generic fonts like Arial and Inter; choose distinctive, characterful fonts. Pair a distinctive display font with a refined body font.
- **Color & Theme**: Commit to a cohesive aesthetic. Use CSS variables for consistency. Dominant colors with sharp accents outperform timid, evenly-distributed palettes.
- **Structure as Information**: Use numbering, dividers, labels, eyebrows, and section mechanics only when they encode real hierarchy, sequence, status, or comparison. Do not add `01 / 02 / 03` markers unless order matters.
- **Motion**: Use animations for effects and micro-interactions. Prioritize CSS-only solutions for HTML. Use Motion library for React when available. Focus on high-impact moments: one well-orchestrated page load with staggered reveals (animation-delay) creates more delight than scattered micro-interactions. Use scroll-triggering and hover states that surprise.
- **Spatial Composition**: Unexpected layouts. Asymmetry. Overlap. Diagonal flow. Grid-breaking elements. Generous negative space OR controlled density.
- **Backgrounds & Visual Details**: Create atmosphere/depth via contextual effects and textures matching the aesthetic, not flat solid colors. Apply creative forms like gradient meshes, noise textures, geometric patterns, layered transparencies, dramatic shadows, decorative borders, custom cursors, and grain overlays.
- **Interface Writing**: Treat words as design material. Use plain active verbs, consistent action names, specific labels, directional empty states, and errors that explain what happened plus how to recover.

NEVER use generic AI-generated aesthetics — predictable, cookie-cutter layouts/components lacking context-specific character. Forbidden fonts/colors: `./anti-slop-rules.md` (canonical list).

Interpret creatively and make unexpected choices that feel genuinely designed for the context. No design should be the same. Vary between light and dark themes, different fonts, different aesthetics. NEVER converge on common choices (Space Grotesk, for example) across generations.

**IMPORTANT**: Match implementation complexity to the aesthetic vision. Maximalist designs need elaborate code with extensive animations and effects. Minimalist/refined designs need restraint, precision, careful spacing/typography/detail — elegance comes from executing well.

**Restraint Check**: After the first build pass, remove one decorative element that does not support the brief. Boldness without editing reads as generated clutter.

**Implementation Check**: Watch CSS specificity and selector overlap. Avoid generic class names that cancel each other out across sections, especially around padding, margin, and CTA styles.

**Remember:** Claude is capable of extraordinary creative work. Don't hold back, show what can truly be created when thinking outside the box and committing fully to a distinctive vision.

**Assets**: Generate images with `hs:ai-multimodal`, process with `hs:media-processing`.

## Writing For Interfaces

When the brief lacks real copy, write only what helps the user understand and act.

- Name controls by what people recognize and control, not implementation internals.
- Prefer specific active labels: "Save changes", "Publish", "Invite reviewer".
- Keep action vocabulary consistent across buttons, toasts, dialogs, and docs.
- Error text must state what happened and how to fix it; do not apologize or stay vague.
- Empty states should invite the next useful action.
- Let each element do one job: label labels, hint explains, example demonstrates.
